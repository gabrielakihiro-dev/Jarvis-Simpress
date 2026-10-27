"""Componentes pequenos do HUD: indicador de status, chip e cartão de confirmação."""

import html
import re

from PyQt5.QtCore import QPropertyAnimation, Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QShortcut,
    QVBoxLayout,
)
from PyQt5.QtGui import QKeySequence

from ui import theme

_COR_NIVEL = {"ok": theme.SUCCESS, "aviso": theme.WARNING, "erro": theme.ERROR, "neutro": theme.TEXT_SECONDARY}
_ICONE_NIVEL = {"ok": "●", "aviso": "▲", "erro": "✕", "neutro": "○"}


class IndicadorStatus(QLabel):
    """Ícone + rótulo + valor: o nível nunca é passado só pela cor."""

    def __init__(self, rotulo: str, parent=None):
        super().__init__(parent)
        self._rotulo = rotulo
        self.definir("neutro", "—")
        self.setTextFormat(Qt.RichText)

    def definir(self, nivel: str, valor: str) -> None:
        cor = _COR_NIVEL[nivel]
        texto = f"<span style='color:{cor}'>{_ICONE_NIVEL[nivel]}</span> " \
                f"<span style='color:{theme.TEXT_SECONDARY}'>{html.escape(self._rotulo)}</span> " \
                f"<b>{html.escape(valor)}</b>"
        self.setText(texto)
        self.setAccessibleName(f"{self._rotulo}: {valor}")


def botao(texto: str, papel: str = "", dica: str = "", nome: str = "") -> QPushButton:
    b = QPushButton(texto)
    if papel:
        b.setProperty("papel", papel)
    if dica:
        b.setToolTip(dica)
    b.setAccessibleName(nome or dica or texto)
    b.setCursor(Qt.PointingHandCursor)
    return b


def renderizar(texto: str) -> str:
    """Markdown mínimo → HTML que o QTextBrowser entende. O texto é escapado antes."""
    linhas, aberta, saida = html.escape(texto).split("\n"), False, []
    for linha in linhas:
        item = re.match(r"^\s*(?:[-*•]|\d+[.)])\s+(.*)$", linha)
        if item and not aberta:
            saida.append("<ul>")
            aberta = True
        if not item and aberta:
            saida.append("</ul>")
            aberta = False
        conteudo = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", item.group(1) if item else linha)
        conteudo = re.sub(r"`([^`]+)`", rf"<code style='color:{theme.CYAN}'>\1</code>", conteudo)
        saida.append(f"<li>{conteudo}</li>" if item else (conteudo + "<br>" if conteudo else "<br>"))
    if aberta:
        saida.append("</ul>")
    return "".join(saida)


class CartaoConfirmacao(QFrame):
    """Pergunta antes de qualquer alteração. O texto vem do código, nunca da IA."""

    decidido = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("cartao_confirmacao")
        self.setAccessibleName("Confirmação de alteração")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(theme.SP["md"], theme.SP["md"], theme.SP["md"], theme.SP["md"])
        lay.setSpacing(theme.SP["sm"])
        aviso = QLabel("▲ Confirmar alteração")
        aviso.setObjectName("aviso")
        self._texto = QLabel()
        self._texto.setWordWrap(True)
        self._texto.setTextInteractionFlags(Qt.NoTextInteraction)
        linha = QHBoxLayout()
        self.btn_ok = botao("Confirmar e executar", "primario")
        self.btn_cancelar = botao("Cancelar")
        linha.addWidget(self.btn_ok)
        linha.addWidget(self.btn_cancelar)
        linha.addStretch(1)
        lay.addWidget(aviso)
        lay.addWidget(self._texto)
        lay.addLayout(linha)
        self.btn_ok.clicked.connect(lambda: self._decidir(True))
        self.btn_cancelar.clicked.connect(lambda: self._decidir(False))
        esc = QShortcut(QKeySequence(Qt.Key_Escape), self)
        esc.setContext(Qt.WidgetWithChildrenShortcut)
        esc.activated.connect(lambda: self._decidir(False))
        self._efeito = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._efeito)
        self._anim = QPropertyAnimation(self._efeito, b"opacity", self)
        self.hide()

    def mostrar(self, descricao: str) -> None:
        self._texto.setText(descricao)
        self.show()
        ms = theme.duracao(200)
        if ms:
            self._anim.stop()
            self._anim.setDuration(ms)
            self._anim.setStartValue(0.0)
            self._anim.setEndValue(1.0)
            self._anim.start()
        else:
            self._efeito.setOpacity(1.0)
        self.btn_cancelar.setFocus()  # o padrão seguro é não alterar

    def _decidir(self, confirmado: bool) -> None:
        if self.isVisible():
            self.hide()
            self.decidido.emit(confirmado)
