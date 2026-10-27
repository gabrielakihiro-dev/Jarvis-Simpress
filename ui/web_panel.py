"""Painel central: as telas reais do Simpress embutidas (QWebEngine) ou o aviso de servidor offline."""

import json

from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QStackedLayout, QVBoxLayout, QWidget

from ui import theme
from ui.widgets import botao


class WebPanel(QWidget):
    tentar_de_novo = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._base = ""
        self._pendente = None  # id do elemento a clicar quando a página terminar de carregar
        self._carregada = False

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        barra = QFrame()
        barra.setObjectName("rodape")
        bl = QHBoxLayout(barra)
        bl.setContentsMargins(theme.SP["sm"], theme.SP["xs"], theme.SP["sm"], theme.SP["xs"])
        self.btn_voltar = botao("◀", "fantasma", "Voltar", "Voltar")
        self.btn_recarregar = botao("⟳", "fantasma", "Recarregar a tela", "Recarregar a tela")
        self.btn_externo = botao("Abrir no navegador", "fantasma", "Abrir esta tela no navegador padrão")
        self.rotulo = QLabel("")
        self.rotulo.setObjectName("secundario")
        for w in (self.btn_voltar, self.btn_recarregar):
            bl.addWidget(w)
        bl.addWidget(self.rotulo, 1)
        bl.addWidget(self.btn_externo)
        raiz.addWidget(barra)

        corpo = QWidget()
        self._pilha = QStackedLayout(corpo)
        self.view = QWebEngineView()
        self.view.setAccessibleName("Tela do Simpress")
        self._pilha.addWidget(self.view)
        self._pilha.addWidget(self._criar_offline())
        raiz.addWidget(corpo, 1)

        self.view.loadFinished.connect(self._ao_carregar)
        self.btn_voltar.clicked.connect(self.view.back)
        self.btn_recarregar.clicked.connect(self.view.reload)
        self.btn_externo.clicked.connect(lambda: self._base and QDesktopServices.openUrl(QUrl(self._base)))
        self._pilha.setCurrentIndex(1)

    def _criar_offline(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        titulo = QLabel("✕ O Simpress está desligado")
        titulo.setObjectName("titulo")
        titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ajuda = QLabel(
            "Para usar as telas, ligue o servidor: abra a pasta do Simpress e execute "
            "<b>iniciar_servidor.bat</b>. O Jarvis encontra a porta sozinho."
        )
        ajuda.setObjectName("secundario")
        ajuda.setWordWrap(True)
        ajuda.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ajuda.setMaximumWidth(480)
        self.btn_retry = botao("Procurar de novo", "primario")
        self.btn_retry.clicked.connect(self.tentar_de_novo)
        for x in (titulo, ajuda):
            lay.addWidget(x, 0, Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.btn_retry, 0, Qt.AlignmentFlag.AlignCenter)
        return w

    # --- estado -----------------------------------------------------------

    def encerrar(self) -> None:
        """Libera a página antes do QApplication acabar; evita travamento do WebEngine ao sair."""
        page = self.view.page()
        self.view.setHtml("")
        page.deleteLater()
        self.view.deleteLater()

    def definir_servidor(self, base_url: str, online: bool) -> None:
        """Mostra a tela web quando online; senão, o aviso. Só recarrega se a URL mudou."""
        if not online:
            self._pilha.setCurrentIndex(1)
            return
        self._pilha.setCurrentIndex(0)
        if base_url != self._base:
            self._base = base_url
            self._carregada = False
            self.view.load(QUrl(base_url + "/"))
        self.rotulo.setText(base_url)

    def abrir(self, id_elemento: str) -> None:
        """Navega no Cockpit clicando no botão de aba/ferramenta que já existe na página."""
        self._pendente = id_elemento
        if self._carregada:
            self._clicar()

    def _ao_carregar(self, ok: bool) -> None:
        self._carregada = ok
        if ok and self._pendente:
            self._clicar()

    def _clicar(self) -> None:
        js = f"(function(i){{var e=document.getElementById(i);if(e){{e.click();return true}}return false}})({json.dumps(self._pendente)})"
        self.view.page().runJavaScript(js)
        self._pendente = None
