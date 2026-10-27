"""Componentes pequenos do HUD: indicador de status, chip, medidores e cartão de confirmação."""

import html
import re

from PyQt6.QtCore import QPoint, QPropertyAnimation, QRect, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLayout,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtGui import QKeySequence, QShortcut

from ui import theme

try:
    import psutil
except ImportError:  # sem psutil o medidor só não aparece
    psutil = None

MEDIDOR_DISPONIVEL = psutil is not None

_COR_NIVEL = {"ok": theme.SUCCESS, "aviso": theme.WARNING, "erro": theme.ERROR, "neutro": theme.TEXT_SECONDARY}
_ICONE_NIVEL = {"ok": "●", "aviso": "▲", "erro": "✕", "neutro": "○"}


class IndicadorStatus(QLabel):
    """Ícone + rótulo + valor: o nível nunca é passado só pela cor."""

    def __init__(self, rotulo: str, parent=None):
        super().__init__(parent)
        self._rotulo = rotulo
        self.definir("neutro", "—")
        self.setTextFormat(Qt.TextFormat.RichText)

    def definir(self, nivel: str, valor: str) -> None:
        cor = _COR_NIVEL[nivel]
        texto = f"<span style='color:{cor}'>{_ICONE_NIVEL[nivel]}</span> " \
                f"<span style='color:{theme.TEXT_SECONDARY}'>{html.escape(self._rotulo)}</span> " \
                f"<b>{html.escape(valor)}</b>"
        self.setText(texto)
        self.setAccessibleName(f"{self._rotulo}: {valor}")


class FluxoLayout(QLayout):
    """Itens lado a lado que descem para a linha de baixo quando não cabem (como flex-wrap)."""

    def __init__(self, parent=None, espaco: int = 4):
        super().__init__(parent)
        self._itens: list = []
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(espaco)

    def addItem(self, item) -> None:
        self._itens.append(item)

    def count(self) -> int:
        return len(self._itens)

    def itemAt(self, i: int):
        return self._itens[i] if 0 <= i < len(self._itens) else None

    def takeAt(self, i: int):
        return self._itens.pop(i) if 0 <= i < len(self._itens) else None

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, largura: int) -> int:
        return self._dispor(QRect(0, 0, largura, 0), aplicar=False)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._dispor(rect, aplicar=True)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        tam = QSize()
        for item in self._itens:
            tam = tam.expandedTo(item.minimumSize())
        return tam

    def _dispor(self, rect: QRect, aplicar: bool) -> int:
        x, y, alto_linha = rect.x(), rect.y(), 0
        for item in self._itens:
            if item.widget() and item.widget().isHidden():
                continue
            dica = item.sizeHint()
            if x > rect.x() and x + dica.width() > rect.right() + 1:
                x, y, alto_linha = rect.x(), y + alto_linha + self.spacing(), 0
            if aplicar:
                item.setGeometry(QRect(QPoint(x, y), dica))
            x += dica.width() + self.spacing()
            alto_linha = max(alto_linha, dica.height())
        return y + alto_linha - rect.y()


def texto_medidor(nome: str, pct: float) -> str:
    return f"{nome} {round(max(0.0, min(100.0, pct)))}%"


class MedidorSistema(QWidget):
    """CPU e RAM discretos no topo, a cada 2 s; pausa com a janela oculta ou minimizada."""

    NOMES = {"CPU": "processador", "RAM": "memória"}

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(theme.SP["md"])
        self._itens = {}
        for nome in self.NOMES:
            col = QVBoxLayout()
            col.setSpacing(2)
            rotulo = QLabel(texto_medidor(nome, 0))
            rotulo.setObjectName("medidor")
            barra = QProgressBar()
            barra.setObjectName("medidor")
            barra.setTextVisible(False)
            barra.setFixedWidth(56)
            col.addWidget(rotulo)
            col.addWidget(barra)
            lay.addLayout(col)
            self._itens[nome] = (rotulo, barra)
        self._timer = QTimer(self)
        self._timer.setInterval(2000)
        self._timer.timeout.connect(self._atualizar)
        psutil.cpu_percent(None)  # a 1ª leitura sempre volta 0: serve só de marco

    def _atualizar(self) -> None:
        if not self.isVisible() or self.window().isMinimized():
            return
        valores = {"CPU": psutil.cpu_percent(None), "RAM": psutil.virtual_memory().percent}
        for nome, (rotulo, barra) in self._itens.items():
            texto = texto_medidor(nome, valores[nome])
            rotulo.setText(texto)
            barra.setValue(round(valores[nome]))
            acessivel = f"Uso de {self.NOMES[nome]}: {texto.split()[-1]}"
            rotulo.setAccessibleName(acessivel)
            barra.setAccessibleName(acessivel)

    def showEvent(self, ev) -> None:
        super().showEvent(ev)
        self._timer.start()
        self._atualizar()

    def hideEvent(self, ev) -> None:
        super().hideEvent(ev)
        self._timer.stop()


def botao(texto: str, papel: str = "", dica: str = "", nome: str = "") -> QPushButton:
    b = QPushButton(texto)
    if papel:
        b.setProperty("papel", papel)
    if dica:
        b.setToolTip(dica)
    b.setAccessibleName(nome or dica or texto)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
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
        self._texto.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
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
        esc = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        esc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
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
