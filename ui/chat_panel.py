"""Painel de chat com a IA: mensagens, ações rápidas e cartão de confirmação."""

import html
import os
from typing import Callable, Optional

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
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
from llm_client import MODELOS_CATALOGO, LLMClient, Resposta
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


class ChatPanel(QFrame):
    ir_para = pyqtSignal(str)       # pedido de abrir uma tela
    mudou_estado = pyqtSignal()     # modelo ou voz mudaram

    def __init__(self, llm: LLMClient, parent=None):
        super().__init__(parent)
        self.setObjectName("chat")
        self.llm = llm
        self._worker: Optional[AgentWorker] = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(*(theme.SP["md"],) * 4)
        lay.setSpacing(theme.SP["sm"])

        topo = QHBoxLayout()
        titulo = QLabel("Assistente")
        titulo.setObjectName("titulo")
        self.combo = QComboBox()
        self.combo.setAccessibleName("Modelo de IA")
        self.combo.setEditable(False)
        slugs = [s for s, _ in MODELOS_CATALOGO.values()]
        if llm.modelo_principal not in slugs:
            slugs.insert(0, llm.modelo_principal)
        self.combo.addItems(slugs)
        self.combo.setCurrentIndex(slugs.index(llm.modelo_principal))
        self.combo.currentTextChanged.connect(self._trocar_modelo)
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
        self.btn_enviar = botao("Enviar", "primario")
        self.btn_enviar.clicked.connect(self._enviar_campo)
        entrada.addWidget(self.campo, 1)
        entrada.addWidget(self.btn_enviar)
        lay.addLayout(entrada)

        self.rodape = QLabel("")
        self.rodape.setObjectName("secundario")
        self.rodape.setWordWrap(True)
        self.rodape.setAccessibleName("Estado do assistente")
        lay.addWidget(self.rodape)
        lay.addWidget(self.btn_limpar, 0, Qt.AlignLeft)

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
        for w in (self.campo, self.btn_enviar, self.combo, self.btn_limpar, *self._chips):
            w.setEnabled(not ocupado)
        self.btn_enviar.setText("Pensando…" if ocupado else "Enviar")

    def focar_entrada(self) -> None:
        self.campo.setFocus()

    # --- ações ------------------------------------------------------------

    def _trocar_modelo(self, slug: str) -> None:
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
            voice.falar(r.texto_voz)
        self.campo.setFocus()

    def aguardar_fim(self, ms: int = 2000) -> None:
        """Chamado no fechamento da janela: espera a chamada em andamento terminar."""
        w = self._worker
        if w is not None and w.isRunning() and not w.wait(ms):
            w.terminate()
            w.wait(500)
