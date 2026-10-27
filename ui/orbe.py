"""Orbe do Jarvis: anéis desenhados com QPainter que mostram o estado. Clicar nele chama o Jarvis."""

import math

from PyQt6.QtCore import QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QWidget

from ui import theme

ROTULOS = {"ocioso": "Clique para falar", "pensando": "Pensando…",
           "falando": "Falando…", "ouvindo": "Ouvindo…"}


class Orbe(QWidget):
    clicado = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.estado = "ocioso"
        self._fase = 0.0
        self._diametro = 120
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._timer = QTimer(self)
        self._timer.setInterval(33)  # ~30 fps
        self._timer.timeout.connect(self._passo)
        self.definir("ocioso")
        self.compacto(False)

    def compacto(self, sim: bool) -> None:
        self._diametro = 64 if sim else 120
        self.setFixedHeight(self._diametro + 30)
        self.update()

    def escuta(self, ligada: bool) -> None:
        ROTULOS["ocioso"] = "Em espera: bata duas palmas ou diga “Jarvis”" if ligada else "Clique para falar"
        self.definir(self.estado)

    def definir(self, estado: str) -> None:
        self.estado = estado
        self.setAccessibleName(f"Orbe do Jarvis: {ROTULOS[estado]}. Enter ou Espaço para falar.")
        if theme.movimento_reduzido():
            self._timer.stop()
        elif not self._timer.isActive():
            self._timer.start()
        self.update()

    def _passo(self) -> None:
        self._fase = (self._fase + 0.033) % 1000
        self.update()

    def mousePressEvent(self, ev) -> None:
        if ev.button() == Qt.MouseButton.LeftButton:
            self.clicado.emit()

    def keyPressEvent(self, ev) -> None:
        if ev.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicado.emit()
        else:
            super().keyPressEvent(ev)

    def paintEvent(self, _ev) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        d, f = self._diametro, self._fase
        cx, cy = self.width() / 2, d / 2 + 4
        estatico = theme.movimento_reduzido()
        cor = QColor(theme.ERROR if self.estado == "ouvindo" else theme.CYAN)
        if self.estado == "pensando":
            escala = 1.0
        elif self.estado == "falando":
            escala = 1.0 if estatico else 0.92 + 0.08 * abs(math.sin(f * 9))
        else:
            escala = 1.0 if estatico else 0.96 + 0.04 * math.sin(f * 2)
        for i, (fr, larg, alfa) in enumerate(((0.5, 3, 255), (0.38, 2, 170), (0.26, 2, 110))):
            r = d * fr * escala
            c = QColor(cor if i == 0 or self.estado != "ouvindo" else QColor(theme.CYAN))
            c.setAlpha(alfa)
            p.setPen(QPen(c, larg))
            caixa = QRectF(cx - r + 2, cy - r, 2 * r - 4, 2 * r - 4)
            if self.estado == "pensando" and not estatico:
                inicio = int(((f * (120 + 60 * i)) % 360) * 16) * (1 if i % 2 == 0 else -1)
                p.drawArc(caixa, inicio, 250 * 16)
            else:
                p.drawEllipse(caixa)
        miolo = QColor(cor)
        miolo.setAlpha(60)
        p.setBrush(miolo)
        p.setPen(Qt.PenStyle.NoPen)
        r = d * 0.14 * escala
        p.drawEllipse(QRectF(cx - r, cy - r - 2, 2 * r, 2 * r))
        p.setPen(QColor(theme.TEXT_SECONDARY))
        p.drawText(QRectF(0, d + 8, self.width(), 20), Qt.AlignmentFlag.AlignCenter, ROTULOS[self.estado])
        if self.hasFocus():
            p.setPen(QPen(QColor(theme.CYAN), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(QRectF(1, 1, self.width() - 2, self.height() - 2), 6, 6)
        p.end()
