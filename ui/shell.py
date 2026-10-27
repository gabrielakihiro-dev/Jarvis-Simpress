"""Janela principal do Jarvis: HUD de status, menu das telas do Simpress, web e chat."""

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)

import voice
from llm_client import LLMClient
from simpress_client import SimpressClient
from ui import theme
from ui.chat_panel import ChatPanel
from ui.web_panel import WebPanel
from ui.widgets import IndicadorStatus, botao

LARGURA_COMPACTA = 1100
INTERVALO_STATUS_S = 10

# (ícone, rótulo, id do elemento no Cockpit). F1–F8 seguem os atalhos do próprio Cockpit.
TELAS = [
    ("⌂", "Início", "tab-home"),
    ("⇄", "Transporte", "tab-retirada-entrega"),
    ("▤", "Resumo", "tab-resumo"),
    ("⚙", "Automação", "tab-automacao"),
    ("☎", "Chamados", "btn-acompanhamento-chamados"),
    ("≈", "Comparação", "btn-cockpit-comparacao"),
    ("✎", "Histórico de apelidos", "btn-historico-apelidos"),
    ("▦", "Relatório mensal", "btn-relatorio-mensal"),
    ("⟳", "Atualizar planilhas", "btn-atualizar-planilhas"),
    ("☰", "Histórico de planilhas", "btn-historico-comparacoes"),
    ("⌖", "Unidades", "btn-catalogo-unidades"),
]


class StatusWorker(QThread):
    """Consulta o Simpress de tempos em tempos, fora da thread da tela."""

    atualizado = pyqtSignal(dict)

    def __init__(self, simpress: SimpressClient, parent=None):
        super().__init__(parent)
        self.simpress = simpress

    def run(self) -> None:
        while not self.isInterruptionRequested():
            self.atualizado.emit(self.coletar())
            for _ in range(INTERVALO_STATUS_S * 4):
                if self.isInterruptionRequested():
                    return
                self.msleep(250)

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
        except Exception:
            estado["online"] = False
        return estado


class JarvisShell(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("J.A.R.V.I.S. — Simpress")
        self.resize(1400, 860)
        self.setMinimumSize(720, 520)

        self.simpress = SimpressClient()
        self.llm = LLMClient(self.simpress)
        self._compacto = None
        self._ativo = None
        self._botoes = {}

        raiz = QWidget()
        raiz.setObjectName("raiz")
        self.setCentralWidget(raiz)
        col = QVBoxLayout(raiz)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        col.addWidget(self._criar_hud())

        self._corpo = QWidget()
        self._lay_corpo = QHBoxLayout(self._corpo)
        self._lay_corpo.setContentsMargins(0, 0, 0, 0)
        self._lay_corpo.setSpacing(0)
        self.menu = self._criar_menu()
        self.web = WebPanel()
        self.chat = ChatPanel(self.llm)
        self.chat.setMinimumWidth(340)
        self.chat.setMaximumWidth(440)
        self._lay_corpo.addWidget(self.menu)
        self._lay_corpo.addWidget(self.web, 1)
        self._lay_corpo.addWidget(self.chat)
        col.addWidget(self._corpo, 1)

        self.web.tentar_de_novo.connect(self._reprocurar)
        self.chat.mudou_estado.connect(self._atualizar_ia)
        self._atalhos()
        self._atualizar_ia()

        self._status = StatusWorker(self.simpress, self)
        self._status.atualizado.connect(self._aplicar_status)
        self._status.start()

        self.setTabOrder(self.menu, self.web)
        self._ajustar_layout()
        self._selecionar(0)

    # --- construção -------------------------------------------------------

    def _criar_hud(self) -> QFrame:
        hud = QFrame()
        hud.setObjectName("hud")
        lay = QHBoxLayout(hud)
        lay.setContentsMargins(theme.SP["lg"], theme.SP["sm"], theme.SP["lg"], theme.SP["sm"])
        lay.setSpacing(theme.SP["lg"])
        self.logo = QLabel("J.A.R.V.I.S.")
        self.logo.setObjectName("logo")
        lay.addWidget(self.logo)
        self.ind_servidor = IndicadorStatus("Simpress")
        self.ind_equip = IndicadorStatus("Equipamentos")
        self.ind_chamados = IndicadorStatus("Chamados")
        self.ind_auto = IndicadorStatus("Automação")
        self.ind_ia = IndicadorStatus("IA")
        for w in (self.ind_servidor, self.ind_equip, self.ind_chamados, self.ind_auto):
            lay.addWidget(w)
        lay.addStretch(1)
        lay.addWidget(self.ind_ia)
        self.btn_chat = botao("Assistente (Ctrl+J)", "fantasma", "Mostrar ou esconder o assistente (Ctrl+J)", "Mostrar ou esconder o assistente")
        self.btn_chat.clicked.connect(self._alternar_chat)
        lay.addWidget(self.btn_chat)
        return hud

    def _criar_menu(self) -> QFrame:
        menu = QFrame()
        menu.setObjectName("menu")
        lay = QVBoxLayout(menu)
        lay.setContentsMargins(theme.SP["sm"], theme.SP["sm"], theme.SP["sm"], theme.SP["sm"])
        lay.setSpacing(theme.SP["xs"])
        for i, (icone, rotulo, _) in enumerate(TELAS):
            atalho = f" (F{i + 1})" if i < 8 else ""
            b = botao(f"{icone}  {rotulo}", "menu", f"{rotulo}{atalho}", rotulo)
            b.clicked.connect(lambda _=False, n=i: self._selecionar(n))
            lay.addWidget(b)
            self._botoes[i] = b
        lay.addStretch(1)
        menu.setFixedWidth(230)
        return menu

    def _atalhos(self) -> None:
        for i in range(8):
            QShortcut(QKeySequence(f"F{i + 1}"), self, activated=lambda n=i: self._selecionar(n)).setContext(Qt.ShortcutContext.ApplicationShortcut)
        QShortcut(QKeySequence("Ctrl+J"), self, activated=self._alternar_chat).setContext(Qt.ShortcutContext.ApplicationShortcut)

    # --- comportamento ----------------------------------------------------

    def _selecionar(self, n: int) -> None:
        self._ativo = n
        for i, b in self._botoes.items():
            b.setProperty("ativo", "true" if i == n else "false")
            b.style().unpolish(b)
            b.style().polish(b)
        self.web.abrir(TELAS[n][2])

    def _alternar_chat(self) -> None:
        self.chat.setVisible(not self.chat.isVisible())
        if self.chat.isVisible():
            self.chat.focar_entrada()
            self._posicionar_chat()

    def _reprocurar(self) -> None:
        self.ind_servidor.definir("neutro", "procurando…")
        if self.simpress.descobrir():
            self._aplicar_status(self._status.coletar())

    def _aplicar_status(self, e: dict) -> None:
        if not e.get("online"):
            self.ind_servidor.definir("erro", "offline")
            self.ind_equip.definir("neutro", "—")
            self.ind_chamados.definir("neutro", "—")
            self.ind_auto.definir("neutro", "—")
            self.web.definir_servidor(e.get("url", ""), False)
            return
        porta = e["url"].rsplit(":", 1)[-1]
        self.ind_servidor.definir("ok", f"online :{porta}")
        self.ind_equip.definir("ok", str(e.get("equipamentos", "—")))
        c = e.get("chamados")
        self.ind_chamados.definir("neutro" if c is None else ("aviso" if c else "ok"), "—" if c is None else str(c))
        a = e.get("automacao")
        if a is None:
            self.ind_auto.definir("neutro", "—")
        elif a.get("executando"):
            self.ind_auto.definir("aviso", f"executando {a.get('rotina', '')}".strip())
        else:
            self.ind_auto.definir("ok", "ociosa")
        self.web.definir_servidor(e["url"], True)

    def _atualizar_ia(self) -> None:
        nivel = "ok" if self.llm.client else "erro"
        voz = "voz ligada" if voice.HABILITAR_VOZ else "voz desligada"
        self.ind_ia.definir(nivel, f"{self.llm.modelo_principal.split('/')[-1]} · {voz}" if self.llm.client else "sem chave")

    # --- layout responsivo --------------------------------------------------

    def _ajustar_layout(self) -> None:
        compacto = self.width() < LARGURA_COMPACTA
        if compacto == self._compacto:
            return
        self._compacto = compacto
        for i, b in self._botoes.items():
            icone, rotulo, _ = TELAS[i]
            b.setText(icone if compacto else f"{icone}  {rotulo}")
        self.menu.setFixedWidth(56 if compacto else 230)
        self.logo.setVisible(not compacto)
        self.ind_ia.setVisible(not compacto)  # sem espaço no HUD estreito; o estado da IA aparece no chat
        self.btn_chat.setText("Chat" if compacto else "Assistente (Ctrl+J)")
        if compacto:
            self._lay_corpo.removeWidget(self.chat)
            self.chat.setParent(self._corpo)
            self.chat.hide()
        else:
            self._lay_corpo.addWidget(self.chat)
            self.chat.show()

    def _posicionar_chat(self) -> None:
        if self._compacto:
            largura = min(420, self._corpo.width() - 56)
            self.chat.setGeometry(self._corpo.width() - largura, 0, largura, self._corpo.height())
            self.chat.raise_()

    def resizeEvent(self, ev) -> None:
        super().resizeEvent(ev)
        self._ajustar_layout()
        if self.chat.isVisible():
            self._posicionar_chat()

    def closeEvent(self, ev) -> None:
        self._status.requestInterruption()
        self._status.wait(3000)
        self.chat.aguardar_fim()
        self.web.encerrar()
        super().closeEvent(ev)
