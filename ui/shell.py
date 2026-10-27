"""Janela principal do Jarvis: barra do topo, cartões de status à esquerda e chat com orbe no centro."""

import os
from pathlib import Path

from dotenv import set_key
from PyQt6.QtCore import QThread, QUrl, pyqtSignal
from PyQt6.QtGui import QAction, QDesktopServices
from PyQt6.QtWidgets import (
    QBoxLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

import voice
from llm_client import LLMClient
from simpress_client import SimpressClient
from ui import theme
from ui.chat_panel import ChatPanel
from ui.widgets import IndicadorStatus, botao

LARGURA_COMPACTA = 1100
INTERVALO_STATUS_S = 10
ARQUIVO_ENV = Path(__file__).resolve().parent.parent / ".env"

# (chave do status, rótulo, pergunta enviada ao clicar)
CARTOES = [
    ("equipamentos", "Equipamentos", "Quais são os totais do inventário?"),
    ("chamados", "Chamados abertos", "Quais chamados estão abertos?"),
    ("automacao", "Automação", "Qual é o status da automação?"),
    ("pendencias", "Pendências", "Quais são as pendências operacionais?"),
]


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
        self._compacto = None
        self._ultimo: dict = {}
        self._cartoes = {}

        raiz = QWidget()
        raiz.setObjectName("raiz")
        self.setCentralWidget(raiz)
        col = QVBoxLayout(raiz)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)

        self.chat = ChatPanel(self.llm)
        self.chat.setMaximumWidth(880)
        col.addWidget(self._criar_topo())

        corpo = QWidget()
        # esquerda→direita no desktop; abaixo de 1100 px os cartões viram faixa no topo
        self._lay_corpo = QBoxLayout(QBoxLayout.Direction.LeftToRight, corpo)
        self._lay_corpo.setContentsMargins(0, 0, 0, 0)
        self._lay_corpo.setSpacing(0)
        self._lay_corpo.addWidget(self._criar_status())
        centro = QHBoxLayout()
        centro.addStretch(1)
        centro.addWidget(self.chat, 100)
        centro.addStretch(1)
        self._lay_corpo.addLayout(centro, 1)
        col.addWidget(corpo, 1)

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
        lay.addStretch(1)
        self.lbl_escuta = QLabel("💤 em espera")
        self.lbl_escuta.setObjectName("escutando")
        self.lbl_escuta.setToolTip("Em espera: o microfone só procura duas palmas ou “Jarvis”, neste computador. "
                                    "Nada é gravado nem enviado até você chamar.")
        self.lbl_escuta.setAccessibleName("Em espera por palmas ou pela palavra Jarvis")
        self.lbl_escuta.hide()
        lay.addWidget(self.lbl_escuta)
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
        self.acao_escuta = QAction("Escuta ativa (palmas e “Jarvis”)", menu)
        self.acao_escuta.setCheckable(True)
        self.acao_escuta.toggled.connect(self._escuta)
        menu.addAction(self.acao_escuta)
        btn_menu = botao("⚙", "fantasma", "Modelo, navegador, importação, nova conversa e escuta ativa", "Configurações")
        btn_menu.setMenu(menu)
        lay.addWidget(btn_menu)
        return topo

    def _criar_status(self) -> QFrame:
        self.painel_status = QFrame()
        self.painel_status.setObjectName("status")
        self._lay_status = QBoxLayout(QBoxLayout.Direction.TopToBottom, self.painel_status)
        self._lay_status.setContentsMargins(*(theme.SP["md"],) * 4)
        self._lay_status.setSpacing(theme.SP["sm"])
        for chave, rotulo, pergunta in CARTOES:
            b = botao("", "status", f"{rotulo}: clique para perguntar ao Jarvis", rotulo)
            b.clicked.connect(lambda _=False, p=pergunta: self.chat.enviar(p))
            self._cartoes[chave] = (b, rotulo)
            self._definir_cartao(chave, "neutro", "—")
            self._lay_status.addWidget(b)
        self._lay_status.addStretch(1)
        return self.painel_status

    def _definir_cartao(self, chave: str, nivel: str, valor: str) -> None:
        b, rotulo = self._cartoes[chave]
        b.setText(f"{rotulo}  {valor}" if self._compacto else f"{rotulo}\n{valor}")
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

    def _aplicar_status(self, e: dict) -> None:
        for texto in avisos(self._ultimo, e):
            self.chat.avisar(texto)
        self._ultimo = e
        if not e.get("online"):
            self.ind_servidor.definir("erro", "offline")
            for chave in self._cartoes:
                self._definir_cartao(chave, "neutro", "—")
            return
        porta = e["url"].rsplit(":", 1)[-1]
        self.ind_servidor.definir("ok", f"online :{porta}")
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
        self.ind_ia.definir(nivel, self.llm.modelo_principal.split("/")[-1] if self.llm.client else "sem chave")
        self.lbl_escuta.setVisible(self.chat.escuta.ligada)

    # --- layout responsivo --------------------------------------------------

    def _ajustar_layout(self) -> None:
        compacto = self.width() < LARGURA_COMPACTA
        if compacto == self._compacto:
            return
        self._compacto = compacto
        d = QBoxLayout.Direction
        self._lay_corpo.setDirection(d.TopToBottom if compacto else d.LeftToRight)
        self._lay_status.setDirection(d.LeftToRight if compacto else d.TopToBottom)
        if compacto:
            self.painel_status.setMinimumWidth(0)
            self.painel_status.setMaximumWidth(16777215)
        else:
            self.painel_status.setFixedWidth(200)
        self.ind_ia.setVisible(not compacto)
        self.chat.orbe.compacto(compacto)
        if self._ultimo:  # redesenha os cartões no novo formato; sem "antes", não repete aviso
            anterior, self._ultimo = self._ultimo, {}
            self._aplicar_status(anterior)

    def resizeEvent(self, ev) -> None:
        super().resizeEvent(ev)
        self._ajustar_layout()

    def closeEvent(self, ev) -> None:
        self._status.requestInterruption()
        self._status.wait(3000)
        self.chat.aguardar_fim()
        super().closeEvent(ev)
