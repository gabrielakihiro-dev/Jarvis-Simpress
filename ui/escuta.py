"""Escuta ativa: chama o Jarvis por duas palmas ou por "Hey Jarvis", e grava a pergunta.

Um único microfone (QAudioSource) alimenta tudo, em blocos de 50 ms, 16 kHz mono:
- ouvindo: o detector de palmas, o openwakeword ("Hey Jarvis") e o Vosk ("cancelar"; o nome, se o
  openwakeword faltar) rodam offline, só neste computador;
- gravando: o áudio vai para um buffer que para sozinho no silêncio e vira WAV.
Só o áudio gravado depois de chamar o Jarvis sai do computador (para a transcrição).
"""

import io
import json
import os
import queue
import time
import wave
from array import array
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal
from PyQt6.QtMultimedia import QAudioFormat, QAudioSource, QMediaDevices
from PyQt6.QtWidgets import QApplication

from ui.palavra_chave import PalavraChaveWorker

TAXA = 16000
BLOCO_MS = 50
BLOCO_BYTES = TAXA * BLOCO_MS // 1000 * 2
MODELO_VOZ = Path(__file__).resolve().parent.parent / "modelos_voz" / "vosk-model-small-pt-0.3"
# "jarvis" não existe no vocabulário do modelo pt; "Jarvis" falado sai como "jarbas" ("árvores" pegava "abertos")
PALAVRAS = {"jarbas", "cancelar"}
# iscas: sem elas, "cancelei"/"cancelada" da própria fala do Jarvis viram "cancelar"
GRAMATICA = ["jarbas", "cancelar", "cancelei", "cancelada", "cancelado", "cancelou", "cancelamento", "[unk]"]
MICROFONE_MUDO = 0.001  # pico máximo de uma gravação inteira abaixo disso: microfone mudo, não pessoa calada
DEPURAR = os.environ.get("JARVIS_PALMAS_DEBUG") == "1"
LOG_PALMAS = Path(__file__).resolve().parent.parent / "data" / "palmas_debug.log"  # data/ fica fora do Git


def _depurar(msg: str) -> None:
    """JARVIS_PALMAS_DEBUG=1: anota em data/palmas_debug.log o que o detector viu (só picos, sem áudio)."""
    if not DEPURAR:
        return
    try:
        LOG_PALMAS.parent.mkdir(exist_ok=True)
        with LOG_PALMAS.open("a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
    except OSError:
        pass


# --- lógica pura (testada sem microfone) -----------------------------------

def pico(bloco: bytes) -> float:
    a = array("h", bloco)
    return max(map(abs, a)) / 32768 if a else 0.0


def para_mono_16k(dados: bytes, canais: int, taxa: int, flutuante: bool = False) -> bytes:
    """Converte PCM do formato do microfone para 16 kHz mono Int16. `dados` deve ter quadros inteiros."""
    a = array("f" if flutuante else "h", dados)
    if canais > 1:
        a = a[0::canais]  # shortcut: usa só o 1º canal; misturar canais só se algum microfone gravar mudo nele
    if taxa != TAXA:
        passo = taxa / TAXA
        # shortcut: reamostragem por vizinho mais próximo, sem filtro; basta para fala
        a = a[::int(passo)] if passo == int(passo) else array(a.typecode, (a[int(i * passo)] for i in range(int(len(a) / passo))))
    if flutuante:
        a = array("h", (max(-32768, min(32767, int(v * 32767))) for v in a))
    return a.tobytes()


def suavizar_nivel(anterior: float, p: float) -> float:
    """Nível 0..1 do microfone para a tela: sobe rápido com a voz e cai devagar no silêncio."""
    alvo = min(1.0, p / 0.3)  # fala comum fica entre 0,05 e 0,3 de pico
    return anterior + (alvo - anterior) * (0.6 if alvo > anterior else 0.15)


def wav(pcm: bytes) -> bytes:
    bio = io.BytesIO()
    with wave.open(bio, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(TAXA)
        w.writeframes(pcm)
    return bio.getvalue()


class DetectorPalmas:
    """Recebe o pico de cada bloco de 50 ms e diz quando ouviu exatamente duas palmas.

    Palma: sequência de até 6 blocos acima do limiar (a cauda de eco/AGC do microfone dura 150-250 ms)
    que começa forte e decai, depois de silêncio. Voz sustentada ou plana não decai: não conta.
    Entre as duas: 120 a 700 ms. Dispara 400 ms depois da 2ª (uma 3ª palma cancela).
    """

    CALIBRACAO_MS = 2000
    MAX_BLOCOS = 6          # acima de 300 ms é voz ou barulho, não palma
    ESPERA_TERCEIRA_MS = 400

    def __init__(self, limiar: Optional[float] = None):
        self.limiar = limiar if limiar is not None else float(os.environ.get("JARVIS_PALMAS_LIMIAR") or 0.2)
        self.ruido = 0.0
        self.t = 0
        self._alto = 0
        self._quieto_ms = 0
        self._quieto_antes = 0
        self._inicio = 0
        self._primeiro = self._pico = self._ultimo = 0.0
        self._palmas: list = []

    def limpar(self) -> None:
        self._palmas.clear()
        self._alto = self._quieto_ms = 0

    def alimentar(self, p: float) -> bool:
        self.t += BLOCO_MS
        efetivo = max(self.limiar, min(self.ruido * 6, 0.8))  # teto: microfone com ganho alto não pode tornar a palma impossível
        if DEPURAR and (p >= 0.02 or self._alto):
            _depurar(f"bloco t={self.t} pico={p:.3f} limiar={efetivo:.3f} ruido={self.ruido:.3f} "
                     f"{'ALTO' if p >= efetivo else 'baixo'} seguidos={self._alto + (p >= efetivo)}")
        if p >= efetivo:
            if self._alto == 0:
                self._quieto_antes, self._inicio = self._quieto_ms, self.t
                self._primeiro = self._pico = p
            self._alto += 1
            self._quieto_ms = 0
            self._pico, self._ultimo = max(self._pico, p), p
            if self._alto == self.MAX_BLOCOS + 1:  # som longo (voz, batida de porta): não é palma
                _depurar(f"descartado: som longo (mais de {self.MAX_BLOCOS} blocos altos)")
                self._palmas.clear()
            return False
        self.ruido = p if self.ruido == 0 else self.ruido * 0.95 + p * 0.05
        blocos, self._alto = self._alto, 0
        self._quieto_ms += BLOCO_MS
        if 1 <= blocos <= self.MAX_BLOCOS:
            self._palma(blocos)
        espera = self.ESPERA_TERCEIRA_MS if len(self._palmas) >= 2 else 700
        if self._palmas and self.t - self._palmas[-1] > espera:
            duas = len(self._palmas) == 2 and self.t > self.CALIBRACAO_MS
            _depurar(f"fim da janela: {len(self._palmas)} palma(s), calibrando={self.t <= self.CALIBRACAO_MS} -> {'DISPARA' if duas else 'nada'}")
            self._palmas.clear()
            return duas
        return False

    def _palma(self, blocos: int) -> None:
        if blocos > 1 and not (self._primeiro >= 0.6 * self._pico and self._ultimo <= 0.75 * self._pico):
            _depurar(f"rejeitado: não decai (1º={self._primeiro:.2f} pico={self._pico:.2f} último={self._ultimo:.2f})")
            return
        if self._palmas and self._inicio - self._palmas[-1] < 120:
            _depurar("ignorado: eco da mesma palma")
            return
        minimo = BLOCO_MS if self._palmas else 2 * BLOCO_MS
        if self._quieto_antes < minimo:
            _depurar(f"rejeitada: só {self._quieto_antes} ms de silêncio antes (precisa {minimo})")
            return
        self._palmas.append(self._inicio)
        _depurar(f"palma {len(self._palmas)} aceita ({blocos} blocos, pico {self._pico:.2f})")


class CorteSilencio:
    """Diz quando parar a gravação: "fim" após 2 s de silêncio depois da voz, "vazio" sem voz em 5 s."""

    def __init__(self, ruido: float = 0.0, silencio_ms: int = 2000, max_ms: int = 20000, espera_ms: int = 5000):
        self.minimo = min(max(0.04, ruido * 3), 0.3)  # teto: sala barulhenta não pode esconder a voz
        self.silencio_ms, self.max_ms, self.espera_ms = silencio_ms, max_ms, espera_ms
        self.t = self._ultimo = 0
        self.voz = False

    def alimentar(self, p: float) -> Optional[str]:
        self.t += BLOCO_MS
        if self.t > 300 and p >= self.minimo:  # os primeiros 300 ms têm o bipe
            self.voz, self._ultimo = True, self.t
        if self.voz and (self.t - self._ultimo >= self.silencio_ms or self.t >= self.max_ms):
            return "fim"
        if not self.voz and self.t >= min(self.espera_ms, self.max_ms):
            return "vazio"
        return None


class Conversa:
    """Conversa contínua: depois de chamar o Jarvis ele segue ouvindo até ficar `espera_ms` sem você falar."""

    ESPERA_MS = 120_000

    def __init__(self, espera_ms: int = ESPERA_MS, relogio=time.monotonic):
        self.espera_ms, self._relogio = espera_ms, relogio
        self.acordada, self._marca = False, 0.0

    def acordar(self) -> None:
        self.acordada = True
        self.reiniciar()

    def reiniciar(self) -> None:
        self._marca = self._relogio()

    def dormir(self) -> None:
        self.acordada = False

    def venceu(self) -> bool:
        return self.acordada and (self._relogio() - self._marca) * 1000 >= self.espera_ms


# --- Qt --------------------------------------------------------------------

class VoskWorker(QThread):
    """Reconhece a palavra de chamada fora da thread da tela, com gramática mínima."""

    ouviu = pyqtSignal(str)       # "jarbas" | "cancelar"
    falhou = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fila: queue.Queue = queue.Queue(maxsize=100)
        self._zerar = False

    def alimentar(self, bloco: bytes) -> None:
        try:
            self._fila.put_nowait(bloco)
        except queue.Full:
            pass

    def zerar(self) -> None:
        self._zerar = True

    def run(self) -> None:
        if not MODELO_VOZ.is_dir():
            self.falhou.emit("modelo de voz ausente em modelos_voz/")
            return
        try:
            import vosk
            vosk.SetLogLevel(-1)
            rec = vosk.KaldiRecognizer(vosk.Model(str(MODELO_VOZ)), TAXA, json.dumps(GRAMATICA, ensure_ascii=False))
        except Exception as e:
            self.falhou.emit(f"Vosk indisponível ({e})")
            return
        while not self.isInterruptionRequested():
            try:
                bloco = self._fila.get(timeout=0.2)
            except queue.Empty:
                continue
            if self._zerar:
                self._zerar = False
                rec.Reset()
                continue
            if rec.AcceptWaveform(bloco):
                texto = json.loads(rec.Result()).get("text", "")
            else:
                texto = json.loads(rec.PartialResult()).get("partial", "")
            achou = PALAVRAS & set(texto.split())
            if achou:
                rec.Reset()
                self.ouviu.emit("cancelar" if "cancelar" in achou else "jarbas")


class Escuta(QObject):
    acordou = pyqtSignal(str)     # "palmas" | "nome"
    gravando = pyqtSignal(bool)
    gravou = pyqtSignal(bytes)    # WAV 16 kHz mono
    aviso = pyqtSignal(str)
    cancelou = pyqtSignal()       # disse “cancelar” enquanto o Jarvis pensava, falava ou pedia confirmação
    dormiu = pyqtSignal()         # 2 min sem você falar: volta a esperar por palmas ou pelo nome
    nivel = pyqtSignal(float)     # 0..1 suavizado, a cada bloco de 50 ms (para o orbe)
    mudou_mudo = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.conversa = Conversa()
        self._silenciosa = False  # gravação reaberta sozinha pela conversa contínua: sem bipe nem aviso
        self._sono = QTimer(self)
        self._sono.setInterval(5000)
        self._sono.timeout.connect(self._conferir_sono)
        self.ligada = False
        self._fonte: Optional[QAudioSource] = None
        self._dev = None
        self._fmt: Optional[QAudioFormat] = None
        self._cru = b""
        self._resto = b""
        self._gravando = False
        self._buf = bytearray()
        self._corte: Optional[CorteSilencio] = None
        self._pausas: set = set()
        self._ignorar = 0
        self._detector = DetectorPalmas()
        self._vosk: Optional[VoskWorker] = None
        self._wake: Optional[PalavraChaveWorker] = None
        self._wake_ok = False  # "Hey Jarvis" carregou: o nome pelo Vosk (plano B) fica de fora para não chamar duas vezes
        self._dbg_pico, self._dbg_n = 0.0, 0
        self._nivel = 0.0
        self.mudo = False  # só em memória: ao abrir o Jarvis o microfone volta ligado

    @property
    def esta_gravando(self) -> bool:
        return self._gravando

    def ligar(self, ligar: bool) -> bool:
        self.ligada = ligar
        if not ligar:
            self._sono.stop()
            self.conversa.dormir()
            if not self._gravando:
                self._fechar()
            return True
        self._detector = DetectorPalmas()
        self._sono.start()
        if self._vosk is None:
            self._vosk = VoskWorker(self)
            self._vosk.ouviu.connect(self._ouviu)
            self._vosk.falhou.connect(lambda m: self.aviso.emit(f"Chamar pelo nome desligado: {m}. Palmas e clique no orbe continuam."))
            self._vosk.start()
        if self._wake is None:
            self._wake = PalavraChaveWorker(self)
            self._wake_ok = True
            self._wake.ouviu.connect(lambda: self._acordar("nome"))
            self._wake.falhou.connect(self._wake_falhou)
            self._wake.start()
        if not self._abrir():
            self.ligada = False
        return self.ligada

    def _wake_falhou(self, motivo: str) -> None:
        self._wake_ok = False
        self.aviso.emit(f"{motivo}. Chamar por “Jarvis” (modelo de voz) e clicar no orbe continuam.")

    def pausar(self, motivo: str, ativo: bool) -> None:
        """Fala do Jarvis, espera da IA e cartão de confirmação pausam a escuta."""
        antes = bool(self._pausas)
        (self._pausas.add if ativo else self._pausas.discard)(motivo)
        if antes and not self._pausas:
            self._esfriar()
            self.conversa.reiniciar()  # o Jarvis acabou de falar: a vez é sua
            self._retomar_depois()

    def gravar(self, silenciosa: bool = False) -> bool:
        if self._gravando:
            return True
        if self.mudo:  # cobre clique, palmas/nome ainda na fila do Vosk e a retomada da conversa
            return False
        if not self._abrir():
            return False
        self._silenciosa = silenciosa
        if self.ligada and not silenciosa:
            self.conversa.acordar()
        self._gravando, self._buf = True, bytearray()
        self._corte = CorteSilencio(self._detector.ruido)
        if not silenciosa:
            QApplication.beep()
        self.gravando.emit(True)
        return True

    def definir_mudo(self, mudo: bool) -> None:
        """Mudo descarta o áudio: sem palmas, nome, gravação nem nível. Desmutar volta à espera, sem acordar."""
        if mudo == self.mudo:
            return
        self.mudo = mudo
        if mudo:
            if self._gravando:
                self.parar(False)
            self.dormir()
            if self._vosk is not None:
                self._vosk.zerar()
            self._nivel = 0.0
            self.nivel.emit(0.0)
        else:
            self._esfriar()
        self.mudou_mudo.emit(mudo)

    def dormir(self) -> None:
        """Encerra a conversa contínua (sem aviso): “cancelar” ou parar uma gravação sem fala."""
        self.conversa.dormir()

    def parar(self, enviar: bool = True) -> None:
        if not self._gravando:
            return
        self._gravando = False
        dados, self._buf = bytes(self._buf), bytearray()
        self.gravando.emit(False)
        self._esfriar()
        if not self.ligada:
            self._fechar()
        if not enviar:
            return
        if len(dados) < 8000:  # menos de 0,25 s: clique sem fala, quer sair da conversa
            if not self._silenciosa:
                self.aviso.emit("Não ouvi nada. Fale logo depois do bipe.")
            self.dormir()
            return
        self.conversa.reiniciar()
        self.gravou.emit(wav(dados))

    def encerrar(self) -> None:
        self._sono.stop()
        if self._vosk is not None:
            self._vosk.requestInterruption()
            self._vosk.wait(2000)
        if self._wake is not None:
            self._wake.requestInterruption()
            self._wake.wait(2000)
        self._gravando = False
        self._fechar()

    # --- interno -----------------------------------------------------------

    def _esfriar(self) -> None:
        self._ignorar = 500 // BLOCO_MS  # bipe e fim da fala não podem acordar o Jarvis
        self._detector.limpar()
        if self._vosk is not None:
            self._vosk.zerar()
        if self._wake is not None:
            self._wake.zerar()

    def _retomar_depois(self) -> None:
        QTimer.singleShot(500, self._retomar)  # espera o esfriamento do bipe e da fala

    def _retomar(self) -> None:
        if self.ligada and self.conversa.acordada and not self._gravando and not self._pausas:
            self.gravar(silenciosa=True)

    def _conferir_sono(self) -> None:
        if self.conversa.venceu() and not self._pausas:
            if self._gravando:
                self.parar(False)
            self.dormir()
            self.dormiu.emit()

    def _ouviu(self, palavra: str) -> None:
        if palavra != "cancelar":
            if not self._wake_ok:
                self._acordar("nome")
        elif self.ligada and self._pausas and not self._gravando and not self.mudo:
            self.cancelou.emit()

    def _acordar(self, motivo: str) -> None:
        # mudo: um "jarbas" que ainda estava na fila do Vosk não acorda
        if not self.ligada or self.mudo or self._gravando or self._pausas or self._ignorar:
            return
        self.acordou.emit(motivo)
        self.gravar()

    def _abrir(self) -> bool:
        if self._fonte is not None:
            return True
        entrada = QMediaDevices.defaultAudioInput()
        if entrada.isNull():
            self.aviso.emit("Nenhum microfone encontrado. Conecte um e tente de novo.")
            return False
        fmt = QAudioFormat()
        fmt.setSampleRate(TAXA)
        fmt.setChannelCount(1)
        fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        if not entrada.isFormatSupported(fmt):
            fmt = entrada.preferredFormat()
        if fmt.sampleFormat() not in (QAudioFormat.SampleFormat.Int16, QAudioFormat.SampleFormat.Float):
            self.aviso.emit("O microfone usa um formato de áudio que o Jarvis ainda não lê.")
            return False
        self._fmt, self._cru, self._resto = fmt, b"", b""
        _depurar(f"microfone: {entrada.description()} {fmt.sampleRate()} Hz, {fmt.channelCount()} canal(is), {fmt.sampleFormat().name}")
        self._fonte = QAudioSource(entrada, fmt, self)
        self._dev = self._fonte.start()
        self._dev.readyRead.connect(self._ler)
        return True

    def _fechar(self) -> None:
        if self._fonte is not None:
            self._fonte.stop()
            self._fonte = self._dev = None

    def _ler(self) -> None:
        if self._dev is None:
            return
        f = self._fmt
        quadro = f.bytesPerFrame()
        dados = self._cru + bytes(self._dev.readAll())
        corte = len(dados) - len(dados) % quadro
        self._cru = dados[corte:]
        pcm = self._resto + para_mono_16k(dados[:corte], f.channelCount(), f.sampleRate(),
                                          f.sampleFormat() == QAudioFormat.SampleFormat.Float)
        while len(pcm) >= BLOCO_BYTES:
            bloco, pcm = pcm[:BLOCO_BYTES], pcm[BLOCO_BYTES:]
            self._bloco(bloco)
        self._resto = pcm

    def _bloco(self, bloco: bytes) -> None:
        if self.mudo:
            self.nivel.emit(0.0)
            return
        p = pico(bloco)
        self._nivel = suavizar_nivel(self._nivel, p)
        self.nivel.emit(self._nivel)
        if DEPURAR:  # 1 linha por segundo: o que o microfone entrega e em que estado a escuta está
            self._dbg_pico, self._dbg_n = max(self._dbg_pico, p), self._dbg_n + 1
            if self._dbg_n >= 20:
                _depurar(f"1s: pico_max={self._dbg_pico:.4f} ligada={self.ligada} gravando={self._gravando} "
                         f"pausas={sorted(self._pausas)} esfriando={self._ignorar}")
                self._dbg_pico, self._dbg_n = 0.0, 0
        if self._gravando:
            self._buf += bloco
            fim = self._corte.alimentar(p)
            if self._corte.voz:
                self.conversa.reiniciar()  # falando agora: não dorme no meio da frase
            if fim == "fim":
                self.parar(True)
            elif fim == "vazio":
                mudo = pico(bytes(self._buf)) < MICROFONE_MUDO
                silenciosa = self._silenciosa
                self.parar(False)
                if not silenciosa:
                    self.aviso.emit("O microfone entregou só silêncio (mudo ou volume zero no Windows)." if mudo
                                    else "Não ouvi nada. Chame de novo e fale logo depois do bipe.")
                self._retomar_depois()  # conversa contínua: segue ouvindo até dormir
            return
        if not self.ligada:
            return
        if self._pausas:  # pausada, só “cancelar” vale: palmas e nome ficam de fora
            if DEPURAR and p >= 0.1:
                _depurar(f"som ignorado: escuta pausada por {sorted(self._pausas)}")
            if self._vosk is not None:
                self._vosk.alimentar(bloco)
            return
        if self._ignorar:
            if DEPURAR and p >= 0.1:
                _depurar("som ignorado: esfriando depois de bipe/fala")
            self._ignorar -= 1
            return
        if self._detector.alimentar(p):
            self._acordar("palmas")
        else:
            if self._wake is not None and self._wake_ok:
                self._wake.alimentar(bloco)
            if self._vosk is not None:
                self._vosk.alimentar(bloco)
