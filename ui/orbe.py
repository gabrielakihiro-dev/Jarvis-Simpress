"""Orbe do Jarvis: núcleo HUD pseudo-3D (esfera de pontos, anéis e onda) desenhado com QPainter.

Clicar nele chama o Jarvis. A cor e o ritmo mostram o estado; o texto embaixo diz o mesmo em palavras.
"""

import math
import time

from PyQt6.QtCore import QLineF, QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QPainter, QPen, QPolygonF, QRadialGradient
from PyQt6.QtWidgets import QWidget

from ui import theme

ROTULOS = {"ocioso": "Clique para falar", "pensando": "Pensando…",
           "falando": "Falando…", "ouvindo": "Ouvindo…",
           "dormindo": "Dormindo: bata duas palmas ou diga “Jarvis”",
           "mudo": "Microfone mudo (Ctrl+M para ativar)"}

DIST = 3.2           # distância da câmera em raios da esfera: menor = perspectiva mais forte
N_PONTOS = 420
FAIXAS = 5           # pontos agrupados por profundidade: um drawPoints por faixa, do fundo para a frente
N_ANEL = 72
# (raio relativo à esfera, inclinação em X, inclinação em Y, velocidade do giro próprio)
ANEIS = ((1.25, 1.15, 0.25, 1.0), (1.38, 0.35, 1.05, -0.7), (1.15, -0.85, -0.6, 1.4))

# estado visual: (cor, giro em rad/s, intensidade 0..1, onda: None | "mic" | "fala" | "pulso")
VISUAL = {
    "ocioso": (theme.CYAN, 0.35, 0.85, "mic"),
    "ouvindo": (theme.LARANJA, 0.7, 1.0, "mic"),
    "pensando": (theme.CYAN_HOVER, 1.8, 1.0, "pulso"),
    "falando": (theme.CYAN, 0.6, 1.0, "fala"),
    "dormindo": (theme.BORDER_STRONG, 0.08, 0.45, None),
    "mudo": (theme.WARNING, 0.12, 0.4, None),
}


# --- geometria pura (testada sem Qt) ----------------------------------------

def pontos_esfera(n: int) -> list:
    """Espiral de Fibonacci: n pontos quase uniformes na esfera de raio 1."""
    ouro = math.pi * (3 - math.sqrt(5))
    pts = []
    for i in range(n):
        y = 1 - 2 * (i + 0.5) / n
        r = math.sqrt(1 - y * y)
        a = ouro * i
        pts.append((r * math.cos(a), y, r * math.sin(a)))
    return pts


def girar(pontos: list, ax: float, ay: float) -> list:
    """Gira em torno de X (ax) e depois de Y (ay). z positivo aponta para quem olha."""
    cx, sx, cy, sy = math.cos(ax), math.sin(ax), math.cos(ay), math.sin(ay)
    saida = []
    for x, y, z in pontos:
        y, z = y * cx - z * sx, y * sx + z * cx
        x, z = x * cy + z * sy, -x * sy + z * cy
        saida.append((x, y, z))
    return saida


def projetar(x: float, y: float, z: float, raio: float, dist: float = DIST) -> tuple:
    """Perspectiva: devolve (dx, dy, escala) relativos ao centro; o mais perto fica maior."""
    f = dist / (dist - z)
    return x * raio * f, -y * raio * f, f


def envelope_fala(t: float) -> float:
    """Volume simulado da fala (0..1): o Qt não entrega o nível da saída de áudio."""
    return min(1.0, 0.25 + 0.75 * abs(math.sin(t * 7.1) * math.sin(t * 2.3 + 1.0)))


def anel(raio: float, giro: float, ix: float, iy: float, n: int = N_ANEL) -> list:
    base = [(raio * math.cos(giro + 2 * math.pi * k / n), raio * math.sin(giro + 2 * math.pi * k / n), 0.0)
            for k in range(n)]
    return girar(base, ix, iy)


ESFERA = pontos_esfera(N_PONTOS)
# onda: (cos, sin, ângulo) de cada vértice, calculados uma vez
ONDA = [(math.cos(a), math.sin(a), a) for a in (2 * math.pi * k / 96 for k in range(96))]


class Orbe(QWidget):
    clicado = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.estado = "ocioso"
        self._mudo = False
        self._diametro = 140
        self._t = 0.0
        self._giro = 0.6
        self._vel = VISUAL["ocioso"][1]
        self._nivel_alvo = self._nivel = 0.0
        self._antes = time.monotonic()
        self._brilho: dict = {}
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)  # o padrão do Windows não segura 16 ms
        self._timer.setInterval(16)  # ~60 fps
        self._timer.timeout.connect(self._passo)
        self.definir("ocioso")
        self.compacto(False)

    @property
    def visual(self) -> str:
        """Estado desenhado: o mudo vale enquanto o Jarvis não está pensando nem falando."""
        return "mudo" if self._mudo and self.estado in ("ocioso", "dormindo", "ouvindo") else self.estado

    def compacto(self, sim: bool) -> None:
        self._diametro = 72 if sim else 140
        self.setFixedHeight(self._diametro + 30)
        self.update()

    def escuta(self, ligada: bool) -> None:
        ROTULOS["ocioso"] = "Em espera: bata duas palmas ou diga “Jarvis”" if ligada else "Clique para falar"
        self.definir(self.estado)

    def definir_mudo(self, mudo: bool) -> None:
        self._mudo = mudo
        self.definir(self.estado)

    def definir_nivel(self, nivel: float) -> None:
        """Nível 0..1 do microfone (Escuta.nivel); a onda só reage a ele em espera ou ouvindo."""
        self._nivel_alvo = max(0.0, min(1.0, nivel))

    def definir(self, estado: str) -> None:
        self.estado = estado
        rotulo = ROTULOS[self.visual]
        acao = "" if self.visual == "mudo" else " Enter ou Espaço para falar."
        self.setAccessibleName(f"Orbe do Jarvis: {rotulo}.{acao}")
        self.setAccessibleDescription(f"Núcleo animado do Jarvis. Estado: {rotulo}")
        self._sincronizar()
        self.update()

    def _sincronizar(self) -> None:
        if self.isVisible() and not theme.movimento_reduzido():
            if not self._timer.isActive():
                self._antes = time.monotonic()
                self._timer.start()
        else:
            self._timer.stop()

    def showEvent(self, ev) -> None:
        super().showEvent(ev)
        self._sincronizar()

    def hideEvent(self, ev) -> None:
        super().hideEvent(ev)
        self._timer.stop()

    def _passo(self) -> None:
        agora = time.monotonic()
        dt, self._antes = min(agora - self._antes, 0.1), agora
        if self.window().isMinimized():
            return
        self._t += dt
        self._vel += (VISUAL[self.visual][1] - self._vel) * min(1.0, dt * 3)  # troca de ritmo suave
        self._giro += self._vel * dt
        self._nivel += (self._nivel_alvo - self._nivel) * 0.25
        self._nivel_alvo *= 0.96  # sem novos blocos (microfone fechado), a onda volta ao repouso
        self.update()

    def mousePressEvent(self, ev) -> None:
        if ev.button() == Qt.MouseButton.LeftButton:
            self.clicado.emit()

    def keyPressEvent(self, ev) -> None:
        if ev.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicado.emit()
        else:
            super().keyPressEvent(ev)

    # --- desenho ---------------------------------------------------------------

    def _gradiente(self, raio: float, cor: str) -> QBrush:
        chave = (round(raio), cor)
        if chave not in self._brilho:
            g = QRadialGradient(QPointF(0, 0), raio)
            for pos, alfa in ((0.0, 150), (0.35, 60), (1.0, 0)):
                c = QColor(cor)
                c.setAlpha(alfa)
                g.setColorAt(pos, c)
            self._brilho = {chave: QBrush(g)}  # só o tamanho atual: troca ao entrar/sair do modo compacto
        return self._brilho[chave]

    def _amplitude(self, onda) -> float:
        if onda == "mic":
            return 0.08 + 0.92 * self._nivel
        if onda == "fala":
            return envelope_fala(self._t)
        if onda == "pulso":
            return 0.3 + 0.2 * math.sin(self._t * 6)
        return 0.0

    def _desenhar_anel(self, p: QPainter, pts: list, cor: QColor, frente: bool, inten: float) -> None:
        """pts: (x, y, z) já projetados na tela, com o z original para separar frente e fundo."""
        linhas = []
        for i, (x, y, z) in enumerate(pts):
            x2, y2, z2 = pts[i - 1]
            if (z + z2 > 0) == frente:
                linhas.append(QLineF(x2, y2, x, y))
        c = QColor(cor)
        c.setAlpha(int((200 if frente else 60) * inten))
        p.setPen(QPen(c, 1.6 if frente else 1.0))
        p.drawLines(linhas)

    def paintEvent(self, _ev) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        d = self._diametro
        visual = self.visual
        cor_hex, _vel, inten, onda = VISUAL[visual]
        cor = QColor(cor_hex)
        estatico = theme.movimento_reduzido()
        t = 0.0 if estatico else self._t
        giro = 0.6 if estatico else self._giro
        r = d * 0.27
        p.translate(self.width() / 2, d / 2 + 4)

        amp = 0.0 if estatico and onda != "mic" else self._amplitude(onda)
        p.setPen(Qt.PenStyle.NoPen)
        p.setOpacity(0.55 + 0.45 * min(1.0, amp) if onda else 0.35)
        p.setBrush(self._gradiente(d * 0.5, cor_hex))
        p.drawEllipse(QPointF(0, 0), d * 0.5, d * 0.5)
        p.setOpacity(1.0)

        aneis = []
        for i, (raio, ix, iy, v) in enumerate(ANEIS):
            pts = anel(raio, giro * v, ix + 0.15 * math.sin(t * 0.3 + i), iy + giro * 0.25)
            aneis.append([(*projetar(x, y, z, r)[:2], z) for x, y, z in pts])
        for pts in aneis:
            self._desenhar_anel(p, pts, cor, False, inten)

        faixas = [[] for _ in range(FAIXAS)]
        for x, y, z in girar(ESFERA, 0.35 + 0.2 * math.sin(t * 0.4), giro):
            f = r * DIST / (DIST - z)  # projetar() em linha: roda 420 vezes por quadro
            faixas[min(FAIXAS - 1, int((z + 1) / 2 * FAIXAS))].append(QPointF(x * f, -y * f))
        escala = d / 140
        for i, pts in enumerate(faixas):
            prof = (i + 0.5) / FAIXAS
            c = QColor(cor)
            c.setAlpha(int((35 + 200 * prof) * inten))
            caneta = QPen(c, (1.0 + 2.2 * prof) * escala)
            caneta.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(caneta)
            p.drawPoints(QPolygonF(pts))

        for pts in aneis:
            self._desenhar_anel(p, pts, cor, True, inten)

        nucleo = QColor(theme.TEXT if visual not in ("dormindo", "mudo") else cor_hex)
        nucleo.setAlpha(int(220 * inten))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(nucleo)
        p.drawEllipse(QPointF(0, 0), r * 0.12, r * 0.12)

        if onda:
            base, extra = d * 0.445, d * 0.045 * amp
            sin = math.sin
            contorno = QPolygonF([QPointF(c * rr, s * rr) for c, s, rr in (
                (c, s, base + extra * (0.6 * sin(6 * a + t * 3) + 0.4 * sin(11 * a - t * 5))) for c, s, a in ONDA)])
            c = QColor(cor)
            c.setAlpha(int(90 + 140 * min(1.0, amp)))
            p.setPen(QPen(c, 1.4))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPolygon(contorno)

        p.resetTransform()
        p.setPen(QColor(theme.TEXT_SECONDARY))
        p.drawText(QRectF(0, d + 8, self.width(), 20), Qt.AlignmentFlag.AlignCenter, ROTULOS[visual])
        if self.hasFocus():
            p.setPen(QPen(QColor(theme.CYAN), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(QRectF(1, 1, self.width() - 2, self.height() - 2), 6, 6)
        p.end()
