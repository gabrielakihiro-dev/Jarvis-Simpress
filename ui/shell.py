"""Janela principal do Jarvis (Modelo 1b, tela dividida): topo, trilho com orbe e cartões à esquerda, chat à direita."""

import os
from pathlib import Path

from dotenv import set_key
from PyQt6.QtCore import QThread, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QAction, QDesktopServices, QFontMetrics, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

import voice
from llm_client import LLMClient
from simpress_client import SimpressClient
from ui import theme
from ui.chat_panel import ChatPanel
from ui.widgets import MEDIDOR_DISPONIVEL, IndicadorStatus, MedidorSistema, botao

LARGURA_COMPACTA = 1100
LARGURA_LISTA = 760
CHAT_MAX = 880
# medidas de cada faixa de largura (jarvis-1b.css): trilho, colunas e largura dos cartões, espaço entre eles,
# espaço acima dos cartões, fonte do rótulo do orbe, padding do chat (topo, lados, base) e largura do nome do modelo
FAIXAS = {
    "larga": dict(trilho=600, colunas=4, cartao=132, gap=8, margem=24, fonte=16, chat=(16, 24, 12), modelo=260),
    "media": dict(trilho=304, colunas=2, cartao=137, gap=6, margem=16, fonte=15, chat=(12, 12, 8), modelo=260),
    "lista": dict(trilho=224, colunas=1, cartao=200, gap=4, margem=12, fonte=14, chat=(12, 12, 8), modelo=150),
}
INTERVALO_STATUS_S = 10
ARQUIVO_ENV = Path(__file__).resolve().parent.parent / ".env"

# (chave do status, rótulo, pergunta enviada ao clicar)
CARTOES = [
    ("equipamentos", "Equipamentos", "Quais são os totais do inventário?"),
    ("chamados", "Chamados abertos", "Quais chamados estão abertos?"),
    ("automacao", "Automação", "Qual é o status da automação?"),
    ("pendencias", "Pendências", "Quais são as pendências operacionais?"),
]


def faixa(largura: int, altura: int) -> tuple:
    """(nome da faixa, diâmetro do orbe). Janela larga e baixa encolhe o orbe para caber rótulo e cartões."""
    if largura <= LARGURA_LISTA:
        return "lista", 192
    if largura < LARGURA_COMPACTA:
        return "media", 268
    return "larga", 300 if altura <= 640 else 400 if altura <= 760 else 500


class StatusWorker(QThread):
    """Consulta o Simpress de tempos em tempos, fora da thread da tela."""

    atualizado = pyqtSignal(dict)

    def __init__(self, simpress: SimpressClient, parent=None):
        super().__init__(parent)
        self.simpress = simpress
        self._acordar = False

    def run(self) -> None:
        while not self.isInterruptionRequested():
            self.atualizado.emit(self.coletar())
            for _ in range(INTERVALO_STATUS_S * 4):
                if self.isInterruptionRequested():
                    return
                if self._acordar:  # "Procurar de novo": consulta já, sem esperar o intervalo
                    self._acordar = False
                    break
                self.msleep(250)

    def acordar(self) -> None:
        self._acordar = True

    def coletar(self) -> dict:
        estado = {"online": False, "url": self.simpress.base_url}
        try:
            totais = self.simpress.obter_totais_inventario()
            if "erro" in totais:
                if not self.simpress.descobrir():
                    return estado
                totais = self.simpress.obter_totais_inventario()
                if "erro" in totais:
                    return estado
            estado.update(online=True, url=self.simpress.base_url, equipamentos=totais.get("total_equipamentos_oficial", 0))
            chamados = self.simpress.listar_chamados_abertos()
            estado["chamados"] = chamados.get("total_chamados") if "erro" not in chamados else None
            auto = self.simpress.consultar_status_automacao()
            estado["automacao"] = auto if "erro" not in auto else None
            pend = self.simpress.listar_pendencias_operacionais()
            estado["pendencias"] = pend.get("total") if "erro" not in pend else None
        except Exception:
            estado["online"] = False
        return estado


def avisos(antes: dict, agora: dict) -> list:
    """Mudanças que merecem aviso no chat. O primeiro estado (antes vazio) não avisa."""
    if not antes:
        return []
    if antes.get("online") and not agora.get("online"):
        return ["Perdi a conexão com o Simpress."]
    if not antes.get("online") and agora.get("online"):
        return ["Simpress de volta."]
    saida = []
    c0, c1 = antes.get("chamados"), agora.get("chamados")
    if isinstance(c0, int) and isinstance(c1, int) and c1 > c0:
        saida.append(f"Chegaram {c1 - c0} chamados novos (total {c1}).")
    a0, a1 = antes.get("automacao") or {}, agora.get("automacao") or {}
    if a0.get("executando") and a1 and not a1.get("executando"):
        saida.append(f"A rotina {a0.get('rotina', '')} terminou. Pergunte o status da automação para ver o resultado.")
    return saida


class JarvisShell(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("J.A.R.V.I.S. — Simpress")
        self.resize(1400, 860)
        self.setMinimumSize(720, 520)

        self.simpress = SimpressClient()
        self.llm = LLMClient(self.simpress)
        self._faixa = ""
        self._diametro = 0
        self._ultimo: dict = {}
        self._cartoes = {}

        raiz = QWidget()
        raiz.setObjectName("raiz")
        self.setCentralWidget(raiz)
        col = QVBoxLayout(raiz)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)

        self.chat = ChatPanel(self.llm)
        col.addWidget(self._criar_topo())

        corpo = QHBoxLayout()
        corpo.setContentsMargins(0, 0, 0, 0)
        corpo.setSpacing(0)
        corpo.addWidget(self._criar_trilho())
        corpo.addWidget(self.chat, 1)
        corpo.addStretch(0)  # como .chat > *: até 880 px, alinhado à esquerda; a sobra fica à direita
        col.addLayout(corpo, 1)
        col.addWidget(self._criar_barra_inferior())
        self.setTabOrder(self.chat.orbe, self.chat.texto)

        self.chat.mudou_estado.connect(self._atualizar_ia)
        self._atualizar_ia()

        self._status = StatusWorker(self.simpress, self)
        self._status.atualizado.connect(self._aplicar_status)
        self._status.start()

        self._ajustar_layout()
        if os.getenv("JARVIS_ESCUTA") == "1":
            self._escuta(True)
        self.chat.focar_entrada()

    # --- construção -------------------------------------------------------

    def _criar_topo(self) -> QFrame:
        topo = QFrame()
        topo.setObjectName("hud")
        lay = QHBoxLayout(topo)
        lay.setContentsMargins(theme.SP["lg"], theme.SP["sm"], theme.SP["lg"], theme.SP["sm"])
        lay.setSpacing(theme.SP["lg"])
        logo = QLabel("J.A.R.V.I.S.")
        logo.setObjectName("logo")
        lay.addWidget(logo)
        self.ind_servidor = IndicadorStatus("Simpress")
        lay.addWidget(self.ind_servidor)
        self.medidor = MedidorSistema() if MEDIDOR_DISPONIVEL else None
        if self.medidor:
            lay.addWidget(self.medidor)
        lay.addStretch(1)
        self.lbl_escuta = QLabel("💤 em espera")
        self.lbl_escuta.setObjectName("escutando")
        self.lbl_escuta.setToolTip("Em espera: o microfone só procura “Hey Jarvis”, neste computador. "
                                    "Nada é gravado nem enviado até você chamar.")
        self.lbl_escuta.setAccessibleName("Em espera pela palavra Hey Jarvis")
        self.lbl_escuta.hide()
        lay.addWidget(self.lbl_escuta)
        self.btn_mudo = botao("", "fantasma")
        self.btn_mudo.setObjectName("mudo")
        self.btn_mudo.setCheckable(True)
        self.btn_mudo.toggled.connect(self.chat.escuta.definir_mudo)
        self.chat.escuta.mudou_mudo.connect(self._mostrar_mudo)
        self._mostrar_mudo(False)
        QShortcut(QKeySequence("Ctrl+M"), self, activated=self.btn_mudo.toggle)
        lay.addWidget(self.btn_mudo)
        self.ind_ia = IndicadorStatus("IA")
        lay.addWidget(self.ind_ia)
        lay.addWidget(self.chat.btn_voz)

        menu = QMenu(self)
        modelo = QWidgetAction(menu)
        modelo.setDefaultWidget(self.chat.combo)
        menu.addAction(modelo)
        menu.addSeparator()
        menu.addAction("Abrir Simpress no navegador", lambda: QDesktopServices.openUrl(QUrl(self.simpress.base_url)))
        menu.addAction("Importar planilhas…", self.chat.importar)
        menu.addAction("Nova conversa", self.chat.limpar)
        menu.addSeparator()
        self.acao_escuta = QAction("Escuta ativa (“Hey Jarvis”)", menu)
        self.acao_escuta.setCheckable(True)
        self.acao_escuta.toggled.connect(self._escuta)
        menu.addAction(self.acao_escuta)
        btn_menu = botao("⚙ ▼", "fantasma", "Modelo, navegador, importação, nova conversa e escuta ativa", "Configurações")
        btn_menu.setObjectName("menu")  # a seta é o ▼ do texto, como no 1b; o QSS esconde a seta do Qt
        btn_menu.setMenu(menu)
        lay.addWidget(btn_menu)
        return topo

    def _criar_trilho(self) -> QFrame:
        """Trilho da esquerda: orbe grande e, embaixo, os cartões de status."""
        self.trilho = QFrame()
        self.trilho.setObjectName("trilho")
        lay = QVBoxLayout(self.trilho)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addStretch(1)
        lay.addWidget(self.chat.orbe, 0, Qt.AlignmentFlag.AlignHCenter)
        self.painel_status = QWidget()
        self._grade = QGridLayout(self.painel_status)
        lay.addWidget(self.painel_status, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addStretch(1)
        for chave, rotulo, pergunta in CARTOES:
            b = botao("", "status", f"{rotulo}: clique para perguntar ao Jarvis", rotulo)
            b.clicked.connect(lambda _=False, p=pergunta: self.chat.enviar(p))
            self._cartoes[chave] = (b, rotulo)
            self._definir_cartao(chave, "neutro", "—")
        return self.trilho

    def _criar_barra_inferior(self) -> QFrame:
        """Abaixo de 1100 px, o estado do chat, o Simpress e CPU/RAM descem para esta barra."""
        self.barra = QFrame()
        self.barra.setObjectName("barra_inferior")
        self.barra.setFixedHeight(28)
        lay = QHBoxLayout(self.barra)
        lay.setContentsMargins(theme.SP["md"], 0, theme.SP["md"], 0)
        lay.setSpacing(theme.SP["lg"])
        self.lbl_estado = QLabel(self.chat.rodape.text())  # o aviso inicial chega antes desta ligação
        self.lbl_estado.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse)
        self.lbl_estado.setObjectName("estado")
        self.lbl_estado.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.lbl_estado.setAccessibleName("Estado do assistente")
        self.lbl_estado.linkActivated.connect(lambda _: self.chat.escuta.definir_mudo(False))  # aviso de mudo
        self.chat.mudou_rodape.connect(self.lbl_estado.setText)
        lay.addWidget(self.lbl_estado, 1)
        self.ind_servidor_barra = IndicadorStatus("Simpress")
        lay.addWidget(self.ind_servidor_barra)
        if MEDIDOR_DISPONIVEL:
            lay.addWidget(MedidorSistema())
        return self.barra

    def _definir_cartao(self, chave: str, nivel: str, valor: str) -> None:
        b, rotulo = self._cartoes[chave]
        b.setText(f"{rotulo}  {valor}" if self._faixa == "lista" else f"{rotulo}\n{valor}")
        b.setAccessibleName(f"{rotulo}: {valor}. Clique para perguntar.")
        b.setProperty("nivel", nivel)
        b.style().unpolish(b)
        b.style().polish(b)

    # --- comportamento ----------------------------------------------------

    def _escuta(self, ligar: bool) -> None:
        ok = self.chat.ligar_escuta(ligar)
        self.acao_escuta.blockSignals(True)
        self.acao_escuta.setChecked(ok)
        self.acao_escuta.blockSignals(False)
        self.lbl_escuta.setVisible(ok)
        try:
            set_key(str(ARQUIVO_ENV), "JARVIS_ESCUTA", "1" if ok else "0")
        except OSError:
            pass  # sem .env gravável: só não lembra na próxima abertura

    def _mostrar_mudo(self, mudo: bool) -> None:
        self.btn_mudo.blockSignals(True)
        self.btn_mudo.setChecked(mudo)
        self.btn_mudo.blockSignals(False)
        self.btn_mudo.setText("🔇 Microfone mudo" if mudo else "🎙 Microfone ligado")
        self.btn_mudo.setAccessibleName(f"{'Microfone mudo' if mudo else 'Microfone ligado'}. Ctrl+M para alternar.")
        self.btn_mudo.setToolTip("Microfone mudo: o Jarvis não ouve nome nem fala. Clique ou Ctrl+M para ativar."
                                 if mudo else "Clique ou Ctrl+M para mutar o microfone.")

    def _aplicar_status(self, e: dict) -> None:
        for texto in avisos(self._ultimo, e):
            self.chat.avisar(texto)
        self._ultimo = e
        if not e.get("online"):
            for ind in (self.ind_servidor, self.ind_servidor_barra):
                ind.definir("erro", "offline")
            for chave in self._cartoes:
                self._definir_cartao(chave, "neutro", "—")
            return
        porta = e["url"].rsplit(":", 1)[-1]
        for ind in (self.ind_servidor, self.ind_servidor_barra):
            ind.definir("ok", f"online :{porta}")
        self._definir_cartao("equipamentos", "ok", str(e.get("equipamentos", "—")))
        for chave in ("chamados", "pendencias"):
            n = e.get(chave)
            self._definir_cartao(chave, "neutro" if n is None else ("aviso" if n else "ok"), "—" if n is None else str(n))
        a = e.get("automacao")
        if a is None:
            self._definir_cartao("automacao", "neutro", "—")
        elif a.get("executando"):
            self._definir_cartao("automacao", "aviso", f"executando {a.get('rotina', '')}".strip())
        else:
            self._definir_cartao("automacao", "ok", "ociosa")

    def _atualizar_ia(self) -> None:
        nivel = "ok" if self.llm.client else "erro"
        nome = self.llm.modelo_principal.split("/")[-1] if self.llm.client else "sem chave"
        limite = FAIXAS.get(self._faixa, FAIXAS["larga"])["modelo"]
        self.ind_ia.definir(nivel, QFontMetrics(self.ind_ia.font()).elidedText(nome, Qt.TextElideMode.ElideRight, limite))
        self.ind_ia.setToolTip(self.llm.modelo_principal)
        self.lbl_escuta.setVisible(self.chat.escuta.ligada)

    # --- layout responsivo --------------------------------------------------

    def _ajustar_layout(self) -> None:
        nome, diametro = faixa(self.width(), self.height())
        if (nome, diametro) == (self._faixa, self._diametro):
            return
        mudou_faixa, self._faixa, self._diametro = nome != self._faixa, nome, diametro
        f = FAIXAS[nome]
        # faixa do rótulo na largura do trilho só nas faixas estreitas (“Microfone mudo (Ctrl+M…)” não cabe em 196 px)
        self.chat.orbe.definir_diametro(diametro, f["fonte"], 0 if nome == "larga" else f["trilho"] - 2 * theme.SP["md"])
        if not mudou_faixa:
            return
        larga = nome == "larga"
        self.trilho.setFixedWidth(f["trilho"])
        self.ind_servidor.setVisible(larga)
        if self.medidor:
            self.medidor.setVisible(larga)
        self.barra.setVisible(not larga)
        self.chat.rodape.setVisible(larga)  # a linha de estado vai para a barra inferior
        topo, lado, base = f["chat"]
        self.chat.layout().setContentsMargins(lado, topo, lado, base)
        self.chat.setMaximumWidth(CHAT_MAX + 2 * lado)
        self._grade.setContentsMargins(0, f["margem"], 0, 0)
        self._grade.setSpacing(f["gap"])
        for i, (b, _rotulo) in enumerate(self._cartoes.values()):
            self._grade.removeWidget(b)
            self._grade.addWidget(b, i // f["colunas"], i % f["colunas"])
            b.setFixedWidth(f["cartao"])
            b.setProperty("lista", nome == "lista")  # linha única de 32 px
        self._atualizar_ia()
        if self._ultimo:  # redesenha os cartões no novo formato; sem "antes", não repete aviso
            anterior, self._ultimo = self._ultimo, {}
            self._aplicar_status(anterior)
        else:
            for chave in self._cartoes:
                self._definir_cartao(chave, "neutro", "—")

    def resizeEvent(self, ev) -> None:
        super().resizeEvent(ev)
        self._ajustar_layout()

    def closeEvent(self, ev) -> None:
        self._status.requestInterruption()
        self._status.wait(3000)
        self.chat.aguardar_fim()
        super().closeEvent(ev)
