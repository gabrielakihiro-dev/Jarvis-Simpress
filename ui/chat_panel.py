"""Painel de chat com a IA: mensagens, ações rápidas e cartão de confirmação."""

import html
import io
import os
import wave
from typing import Callable, Optional

from PyQt6.QtCore import QBuffer, QIODevice, Qt, QThread, QUrl, pyqtSignal
from PyQt6.QtMultimedia import QAudioFormat, QAudioOutput, QAudioSource, QMediaDevices, QMediaPlayer
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

import voice
from llm_client import MODELOS_CATALOGO, LLMClient, Resposta, listar_modelos_ao_vivo
from ui import theme
from ui.widgets import CartaoConfirmacao, botao, renderizar

ACOES_RAPIDAS = [
    ("Totais do cadastro", "Quantos equipamentos há no cadastro oficial?"),
    ("Chamados abertos", "Quais chamados estão abertos?"),
    ("Pendências de hoje", "Quais são as pendências operacionais de hoje?"),
    ("Chamados parados", "Quais ordens de serviço estão paradas há mais tempo?"),
    ("Relatório do mês", "Resuma o relatório mensal do mês atual."),
    ("Automação", "Qual é o estado da automação agora?"),
    ("Última comparação", "Resuma a última comparação de planilhas."),
    ("Prontidão", "O sistema está pronto para as rotinas? Mostre a prontidão."),
]


class AgentWorker(QThread):
    """Roda uma chamada ao LLM fora da thread da tela, para a janela nunca congelar."""

    status = pyqtSignal(str)
    pronto = pyqtSignal(object)

    def __init__(self, tarefa: Callable[[Callable[[str], None]], Resposta], parent=None):
        super().__init__(parent)
        self._tarefa = tarefa

    def run(self) -> None:
        try:
            self.pronto.emit(self._tarefa(self.status.emit))
        except Exception as e:  # a tela nunca deve ficar presa em "pensando"
            self.pronto.emit(Resposta(texto=f"Erro inesperado: {e}"))


class ModelosWorker(QThread):
    """Busca a lista de modelos do OpenRouter fora da tela."""

    pronto = pyqtSignal(list)

    def run(self) -> None:
        self.pronto.emit(listar_modelos_ao_vivo())


class FalaWorker(QThread):
    """Gera o mp3 da fala fora da tela; o painel toca com QMediaPlayer."""

    pronto = pyqtSignal(str)

    def __init__(self, texto: str, parent=None):
        super().__init__(parent)
        self._texto = texto

    def run(self) -> None:
        self.pronto.emit(voice.gerar_mp3(self._texto) or "")


class TranscreveWorker(QThread):
    """Envia o áudio gravado ao modelo de transcrição sem travar a tela."""

    pronto = pyqtSignal(str)

    def __init__(self, llm: LLMClient, wav: bytes, parent=None):
        super().__init__(parent)
        self._llm, self._wav = llm, wav

    def run(self) -> None:
        self.pronto.emit(self._llm.transcrever_audio(self._wav))


class ChatPanel(QFrame):
    ir_para = pyqtSignal(str)       # pedido de abrir uma tela
    mudou_estado = pyqtSignal()     # modelo ou voz mudaram

    def __init__(self, llm: LLMClient, parent=None):
        super().__init__(parent)
        self.setObjectName("chat")
        self.llm = llm
        self._worker: Optional[AgentWorker] = None
        self._fala: Optional[FalaWorker] = None
        self._transcricao: Optional[TranscreveWorker] = None
        self._mic: Optional[QAudioSource] = None
        self._mic_buf: Optional[QBuffer] = None
        self._mic_fmt = None
        self._player = QMediaPlayer(self)
        self._saida = QAudioOutput(self)
        self._player.setAudioOutput(self._saida)
        self._player.mediaStatusChanged.connect(self._fim_fala)
        self._mp3_atual = ""

        lay = QVBoxLayout(self)
        lay.setContentsMargins(*(theme.SP["md"],) * 4)
        lay.setSpacing(theme.SP["sm"])

        topo = QHBoxLayout()
        titulo = QLabel("Assistente")
        titulo.setObjectName("titulo")
        self.combo = QComboBox()
        self.combo.setAccessibleName("Modelo de IA")
        self.combo.setEditable(False)
        self.combo.setMaxVisibleItems(15)
        self._preencher_modelos([(s, s) for s, _ in MODELOS_CATALOGO.values()])
        self.combo.currentIndexChanged.connect(self._trocar_modelo)
        self._modelos = ModelosWorker(self)
        self._modelos.pronto.connect(self._modelos_ao_vivo)
        self._modelos.start()
        self.btn_voz = botao("", "fantasma")
        self.btn_voz.setCheckable(True)
        self.btn_voz.clicked.connect(self._alternar_voz)
        self.btn_limpar = botao("Nova conversa", "fantasma", "Apaga a memória da conversa atual")
        self.btn_limpar.clicked.connect(self._limpar)
        topo.addWidget(titulo, 1)
        topo.addWidget(self.btn_voz)
        lay.addLayout(topo)
        lay.addWidget(self.combo)

        self.texto = QTextBrowser()
        self.texto.setOpenLinks(False)
        self.texto.setAccessibleName("Conversa com o assistente")
        lay.addWidget(self.texto, 1)

        self.cartao = CartaoConfirmacao()
        self.cartao.decidido.connect(self._decidiu)
        lay.addWidget(self.cartao)

        chips = QWidget()
        cl = QGridLayout(chips)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(theme.SP["xs"])
        self._chips = []
        for i, (rotulo, pergunta) in enumerate(ACOES_RAPIDAS):
            b = botao(rotulo, "chip", pergunta)
            b.clicked.connect(lambda _=False, p=pergunta: self.enviar(p))
            self._chips.append(b)
            cl.addWidget(b, i // 2, i % 2)
        lay.addWidget(chips)

        entrada = QHBoxLayout()
        self.campo = QLineEdit()
        self.campo.setPlaceholderText("Pergunte sobre equipamentos, chamados, automação…")
        self.campo.setAccessibleName("Mensagem para o assistente")
        self.campo.returnPressed.connect(self._enviar_campo)
        self.btn_mic = botao("🎤", "fantasma", "Falar com o Jarvis: clique para gravar e clique de novo para enviar", "Falar com o Jarvis")
        self.btn_mic.setCheckable(True)
        self.btn_mic.clicked.connect(self._alternar_mic)
        self.btn_enviar = botao("Enviar", "primario")
        self.btn_enviar.clicked.connect(self._enviar_campo)
        entrada.addWidget(self.campo, 1)
        entrada.addWidget(self.btn_mic)
        entrada.addWidget(self.btn_enviar)
        lay.addLayout(entrada)

        self.rodape = QLabel("")
        self.rodape.setObjectName("secundario")
        self.rodape.setWordWrap(True)
        self.rodape.setAccessibleName("Estado do assistente")
        lay.addWidget(self.rodape)
        lay.addWidget(self.btn_limpar, 0, Qt.AlignmentFlag.AlignLeft)

        self.setTabOrder(self.combo, self.texto)
        self.setTabOrder(self.texto, self.campo)
        self._atualizar_voz()
        self._mensagem("Jarvis", "Pronto. Pergunte ou use uma ação rápida. Alterações só acontecem depois da sua confirmação.")
        if not llm.client:
            self._rodape("A chave do OpenRouter não foi configurada. Edite o arquivo .env e reinicie.", erro=True)

    # --- interface --------------------------------------------------------

    def _mensagem(self, quem: str, texto: str, eu: bool = False) -> None:
        cor = theme.CYAN if not eu else theme.TEXT_SECONDARY
        corpo = html.escape(texto).replace("\n", "<br>") if eu else renderizar(texto)
        self.texto.append(f"<p><span style='color:{cor}'><b>{html.escape(quem)}</b></span><br>{corpo}</p>")

    def _rodape(self, msg: str, erro: bool = False) -> None:
        cor = theme.ERROR if erro else theme.TEXT_SECONDARY
        self.rodape.setText(f"<span style='color:{cor}'>{html.escape(msg)}</span>")

    def _ocupado(self, ocupado: bool) -> None:
        for w in (self.campo, self.btn_enviar, self.btn_mic, self.combo, self.btn_limpar, *self._chips):
            w.setEnabled(not ocupado)
        self.btn_enviar.setText("Pensando…" if ocupado else "Enviar")

    def focar_entrada(self) -> None:
        self.campo.setFocus()

    # --- ações ------------------------------------------------------------

    def _preencher_modelos(self, modelos: list) -> None:
        """Favoritos (catálogo) no topo, depois o resto; o modelo atual sempre fica na lista."""
        favoritos = [s for s, _ in MODELOS_CATALOGO.values()]
        rotulo = dict(modelos)
        atual = self.llm.modelo_principal
        ordem = [s for s in favoritos if s in rotulo] + [s for s in rotulo if s not in favoritos]
        if atual not in ordem:
            ordem.insert(0, atual)
        self.combo.blockSignals(True)
        self.combo.clear()
        for s in ordem:
            self.combo.addItem(("★ " if s in favoritos else "") + rotulo.get(s, s), s)
        self.combo.setCurrentIndex(ordem.index(atual))
        self.combo.blockSignals(False)

    def _modelos_ao_vivo(self, modelos: list) -> None:
        if modelos:  # sem rede, fica o catálogo fixo
            self._preencher_modelos(modelos)

    def _trocar_modelo(self, _indice: int) -> None:
        slug = self.combo.currentData()
        if slug:
            self.llm.trocar_modelo(slug)
            self.mudou_estado.emit()

    def _alternar_voz(self) -> None:
        voice.alternar_voz()
        self._atualizar_voz()
        self.mudou_estado.emit()

    def _atualizar_voz(self) -> None:
        ligada = voice.HABILITAR_VOZ
        self.btn_voz.setChecked(ligada)
        self.btn_voz.setText("🔊 Voz ligada" if ligada else "🔇 Voz desligada")
        self.btn_voz.setAccessibleName(f"Voz {'ligada' if ligada else 'desligada'}. Clique para alternar.")

    def _limpar(self) -> None:
        self.llm.limpar_historico()
        self.cartao.hide()
        self._ocupado(False)
        self.texto.clear()
        self._mensagem("Jarvis", "Conversa reiniciada.")

    def _enviar_campo(self) -> None:
        texto = self.campo.text().strip()
        if texto:
            self.campo.clear()
            self.enviar(texto)

    def enviar(self, texto: str) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        self._mensagem("Você", texto, eu=True)
        self._iniciar(lambda cb: self.llm.enviar_mensagem(texto, callback_status=cb))

    def _decidiu(self, confirmado: bool) -> None:
        self._mensagem("Você", "Confirmei a alteração." if confirmado else "Cancelei a alteração.", eu=True)
        self._iniciar(lambda cb: self.llm.resolver_confirmacao(confirmado, callback_status=cb))

    def _iniciar(self, tarefa) -> None:
        self._ocupado(True)
        self._rodape("Pensando…")
        self._worker = AgentWorker(tarefa, self)
        self._worker.status.connect(self._rodape)
        self._worker.pronto.connect(self._recebeu)
        self._worker.start()

    def _recebeu(self, r: Resposta) -> None:
        self._ocupado(False)
        if r.pendente:
            self._mensagem("Jarvis", "Preciso da sua confirmação para continuar.")
            self._ocupado(True)  # nada de nova pergunta até confirmar ou cancelar
            self.btn_enviar.setText("Enviar")
            self.cartao.mostrar(r.pendente["descricao"])
            self._rodape("Aguardando sua confirmação.")
            return
        self._mensagem("Jarvis", r.texto)
        usadas = ", ".join(r.ferramentas)
        erro = r.texto.startswith(("Erro", "A chave"))
        self._rodape(f"Ferramentas usadas: {usadas}" if usadas else ("Falhou — veja a mensagem acima." if erro else "Pronto."), erro=erro)
        if r.texto_voz and voice.HABILITAR_VOZ:
            self._falar(r.texto_voz)
        self.campo.setFocus()

    # --- voz: saída (fala) e entrada (microfone) ---------------------------

    def _falar(self, texto: str) -> None:
        self._player.stop()
        self._fala = FalaWorker(texto, self)
        self._fala.pronto.connect(self._tocar)
        self._fala.start()

    def _tocar(self, caminho: str) -> None:
        if not caminho:
            self._rodape("Não consegui gerar a voz (sem internet para o Edge-TTS?). A resposta está no texto.", erro=True)
            return
        self._apagar_mp3()
        self._mp3_atual = caminho
        self._player.setSource(QUrl.fromLocalFile(caminho))
        self._saida.setVolume(1.0)
        self._player.play()

    def _fim_fala(self, estado) -> None:
        if estado in (QMediaPlayer.MediaStatus.EndOfMedia, QMediaPlayer.MediaStatus.InvalidMedia):
            self._apagar_mp3()

    def _apagar_mp3(self) -> None:
        if self._mp3_atual:
            self._player.setSource(QUrl())
            try:
                os.remove(self._mp3_atual)
            except OSError:
                pass
            self._mp3_atual = ""

    def _alternar_mic(self) -> None:
        if self._mic is not None:
            self._parar_mic()
            return
        entrada = QMediaDevices.defaultAudioInput()
        if entrada.isNull():
            self.btn_mic.setChecked(False)
            self._rodape("Nenhum microfone encontrado. Conecte um e tente de novo.", erro=True)
            return
        fmt = QAudioFormat()
        fmt.setSampleRate(16000)
        fmt.setChannelCount(1)
        fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        if not entrada.isFormatSupported(fmt):
            fmt = entrada.preferredFormat()
        if fmt.sampleFormat() != QAudioFormat.SampleFormat.Int16:
            self.btn_mic.setChecked(False)
            self._rodape("O microfone usa um formato de áudio que o Jarvis ainda não lê.", erro=True)
            return
        self._player.stop()
        self._mic_fmt = fmt
        self._mic_buf = QBuffer(self)
        self._mic_buf.open(QIODevice.OpenModeFlag.WriteOnly)
        self._mic = QAudioSource(entrada, fmt, self)
        self._mic.start(self._mic_buf)
        self.btn_mic.setText("⏹ Enviar")
        self._rodape("Ouvindo… fale e clique em Enviar.")

    def _parar_mic(self) -> None:
        mic, buf = self._mic, self._mic_buf
        self._mic = self._mic_buf = None
        mic.stop()
        dados = bytes(buf.data())
        buf.close()
        self.btn_mic.setChecked(False)
        self.btn_mic.setText("🎤")
        if len(dados) < 8000:  # menos de ~0,25 s: clique sem fala
            self._rodape("Não ouvi nada. Clique no microfone e fale.", erro=True)
            return
        f = self._mic_fmt
        bio = io.BytesIO()
        with wave.open(bio, "wb") as w:
            w.setnchannels(f.channelCount())
            w.setsampwidth(2)
            w.setframerate(f.sampleRate())
            w.writeframes(dados)
        self._rodape("Transcrevendo…")
        self.btn_mic.setEnabled(False)
        self._transcricao = TranscreveWorker(self.llm, bio.getvalue(), self)
        self._transcricao.pronto.connect(self._transcreveu)
        self._transcricao.start()

    def _transcreveu(self, texto: str) -> None:
        self.btn_mic.setEnabled(True)
        if not texto:
            self._rodape("Não consegui entender o áudio. Tente de novo ou digite.", erro=True)
            return
        self.enviar(texto)

    def aguardar_fim(self, ms: int = 2000) -> None:
        """Chamado no fechamento da janela: espera a chamada em andamento terminar."""
        for t in (self._fala, self._transcricao, self._modelos):
            if t is not None and t.isRunning():
                t.wait(ms)
        if self._mic is not None:
            self._mic.stop()
        self._apagar_mp3()
        w = self._worker
        if w is not None and w.isRunning() and not w.wait(ms):
            w.terminate()
            w.wait(500)
