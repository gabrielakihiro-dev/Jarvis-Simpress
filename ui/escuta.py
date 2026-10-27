"""Escuta ativa: chama o Jarvis por duas palmas ou pela palavra "Jarvis", e grava a pergunta.

Um único microfone (QAudioSource) alimenta tudo, em blocos de 50 ms, 16 kHz mono:
- ouvindo: o detector de palmas e o Vosk (offline) rodam só neste computador;
- gravando: o áudio vai para um buffer que para sozinho no silêncio e vira WAV.
Só o áudio gravado depois de chamar o Jarvis sai do computador (para a transcrição).
"""

import io
import json
import os
import queue
import wave
from array import array
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QObject, QThread, pyqtSignal
from PyQt6.QtMultimedia import QAudioFormat, QAudioSource, QMediaDevices
from PyQt6.QtWidgets import QApplication

TAXA = 16000
BLOCO_MS = 50
BLOCO_BYTES = TAXA * BLOCO_MS // 1000 * 2
MODELO_VOZ = Path(__file__).resolve().parent.parent / "modelos_voz" / "vosk-model-small-pt-0.3"
# "jarvis" não existe no vocabulário do modelo pt; "Jarvis" falado sai como "jarbas" ("árvores" pegava "abertos")
PALAVRAS = {"jarbas"}
GRAMATICA = ["jarbas", "[unk]"]
MICROFONE_MUDO = 0.001  # pico abaixo disso em 3 s seguidos: silêncio digital, não sala quieta


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

    Palma: 1 ou 2 blocos altos, com silêncio antes. Entre as duas: 120 a 700 ms.
    Dispara depois de 700 ms de calma após a 2ª (uma 3ª palma cancela).
    """

    CALIBRACAO_MS = 2000

    def __init__(self, limiar: Optional[float] = None):
        self.limiar = limiar if limiar is not None else float(os.environ.get("JARVIS_PALMAS_LIMIAR") or 0.25)
        self.ruido = 0.0
        self.t = 0
        self._alto = 0
        self._quieto_ms = 0
        self._quieto_antes = 0
        self._palmas: list = []

    def limpar(self) -> None:
        self._palmas.clear()
        self._alto = self._quieto_ms = 0

    def alimentar(self, p: float) -> bool:
        self.t += BLOCO_MS
        if p >= max(self.limiar, self.ruido * 6):
            if self._alto == 0:
                self._quieto_antes = self._quieto_ms
            self._alto += 1
            self._quieto_ms = 0
            if self._alto == 3:  # som longo (voz, batida de porta): não é palma
                self._palmas.clear()
            return False
        self.ruido = p if self.ruido == 0 else self.ruido * 0.95 + p * 0.05
        blocos, self._alto = self._alto, 0
        self._quieto_ms += BLOCO_MS
        if 1 <= blocos <= 2:
            self._palma(self.t - BLOCO_MS * (blocos + 1))
        if self._palmas and self.t - self._palmas[-1] > 700:
            duas = len(self._palmas) == 2 and self.t > self.CALIBRACAO_MS
            self._palmas.clear()
            return duas
        return False

    def _palma(self, inicio: int) -> None:
        if self._palmas and inicio - self._palmas[-1] < 120:
            return  # eco da mesma palma
        if self._palmas:
            self._palmas.append(inicio)
        elif self._quieto_antes >= 150:
            self._palmas.append(inicio)


class CorteSilencio:
    """Diz quando parar a gravação: "fim" após 1,2 s de silêncio depois da voz, "vazio" sem voz em 5 s."""

    def __init__(self, ruido: float = 0.0, silencio_ms: int = 1200, max_ms: int = 20000, espera_ms: int = 5000):
        self.minimo = max(0.04, ruido * 3)
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


# --- Qt --------------------------------------------------------------------

class VoskWorker(QThread):
    """Reconhece a palavra de chamada fora da thread da tela, com gramática mínima."""

    ouviu = pyqtSignal()
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
            if PALAVRAS & set(texto.split()):
                rec.Reset()
                self.ouviu.emit()


class Escuta(QObject):
    acordou = pyqtSignal(str)     # "palmas" | "nome"
    gravando = pyqtSignal(bool)
    gravou = pyqtSignal(bytes)    # WAV 16 kHz mono
    aviso = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
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

    @property
    def esta_gravando(self) -> bool:
        return self._gravando

    def ligar(self, ligar: bool) -> bool:
        self.ligada = ligar
        if not ligar:
            if not self._gravando:
                self._fechar()
            return True
        self._detector = DetectorPalmas()
        if self._vosk is None:
            self._vosk = VoskWorker(self)
            self._vosk.ouviu.connect(lambda: self._acordar("nome"))
            self._vosk.falhou.connect(lambda m: self.aviso.emit(f"Chamar pelo nome desligado: {m}. Palmas e clique no orbe continuam."))
            self._vosk.start()
        if not self._abrir():
            self.ligada = False
        return self.ligada

    def pausar(self, motivo: str, ativo: bool) -> None:
        """Fala do Jarvis, espera da IA e cartão de confirmação pausam a escuta."""
        antes = bool(self._pausas)
        (self._pausas.add if ativo else self._pausas.discard)(motivo)
        if antes and not self._pausas:
            self._esfriar()

    def gravar(self) -> bool:
        if self._gravando:
            return True
        if not self._abrir():
            return False
        self._gravando, self._buf = True, bytearray()
        self._corte = CorteSilencio(self._detector.ruido)
        QApplication.beep()
        self.gravando.emit(True)
        return True

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
        if len(dados) < 8000:  # menos de 0,25 s: clique sem fala
            self.aviso.emit("Não ouvi nada. Fale logo depois do bipe.")
            return
        self.gravou.emit(wav(dados))

    def encerrar(self) -> None:
        if self._vosk is not None:
            self._vosk.requestInterruption()
            self._vosk.wait(2000)
        self._gravando = False
        self._fechar()

    # --- interno -----------------------------------------------------------

    def _esfriar(self) -> None:
        self._ignorar = 500 // BLOCO_MS  # bipe e fim da fala não podem acordar o Jarvis
        self._detector.limpar()
        if self._vosk is not None:
            self._vosk.zerar()

    def _acordar(self, motivo: str) -> None:
        if not self.ligada or self._gravando or self._pausas or self._ignorar:
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
        self._checar, self._max_inicio = 3000 // BLOCO_MS, 0.0  # 3 s para ver se o microfone entrega som
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
        p = pico(bloco)
        if self._checar:
            self._max_inicio = max(self._max_inicio, p)
            self._checar -= 1
            if not self._checar and self._max_inicio < MICROFONE_MUDO:
                self.aviso.emit("O microfone está entregando silêncio (mudo, volume zero ou bloqueado no Windows). "
                                "Palmas, “Jarvis” e o 🎤 não vão funcionar até ele captar som.")
        if self._gravando:
            self._buf += bloco
            fim = self._corte.alimentar(p)
            if fim == "fim":
                self.parar(True)
            elif fim == "vazio":
                self.parar(False)
                self.aviso.emit("Não ouvi nada. Chame de novo e fale logo depois do bipe.")
            return
        if not self.ligada or self._pausas:
            return
        if self._ignorar:
            self._ignorar -= 1
            return
        if self._detector.alimentar(p):
            self._acordar("palmas")
        elif self._vosk is not None:
            self._vosk.alimentar(bloco)
