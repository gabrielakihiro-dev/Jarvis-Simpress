"""Palavra de ativação "Hey Jarvis" (openwakeword), offline, fora da thread da tela.

O microfone entrega blocos de 800 amostras (50 ms); o modelo quer quadros de 1280 (80 ms), 16 kHz mono Int16.
A parte pura (re-buffer, limiar, repouso) não depende de Qt nem do modelo e é testada com um modelo falso.
O modelo é baixado por um passo explícito (ver README); este módulo nunca instala nem baixa nada.
"""

import os
import queue
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

QUADRO = 1280                 # amostras por quadro do modelo (80 ms a 16 kHz)
QUADRO_BYTES = QUADRO * 2
QUADRO_MS = 80
MODELO = "hey_jarvis"
LIMIAR_PADRAO = 0.4           # padrão do openwakeword é 0.5; menor = mais sensível (e mais falso alarme)
REPOUSO_MS = 2000             # depois de disparar, não dispara de novo (a mesma fala ainda ecoa no modelo)


def limiar_do_ambiente() -> float:
    try:
        return float(os.environ.get("JARVIS_WAKE_LIMIAR") or LIMIAR_PADRAO)
    except ValueError:
        return LIMIAR_PADRAO


# --- lógica pura (testada sem microfone e sem modelo) -----------------------

class DetectorChamada:
    """Re-bufferiza blocos de qualquer tamanho em quadros de 1280 amostras e aplica limiar e repouso.

    `modelo.predict(quadro: bytes) -> float` dá a pontuação (0..1) da palavra; `modelo.reset()` limpa o estado.
    """

    def __init__(self, modelo, limiar: Optional[float] = None, repouso_ms: int = REPOUSO_MS):
        self.modelo = modelo
        self.limiar = limiar_do_ambiente() if limiar is None else limiar
        self.repouso_ms = repouso_ms
        self._resto = b""
        self._repouso = 0     # quadros ainda ignorados depois de um disparo

    def limpar(self) -> None:
        self._resto = b""
        self._repouso = 0
        self.modelo.reset()

    def alimentar(self, bloco: bytes) -> bool:
        """True quando algum quadro deste bloco passa o limiar (no máximo um disparo por repouso)."""
        dados = self._resto + bloco
        disparou = False
        while len(dados) >= QUADRO_BYTES:
            quadro, dados = dados[:QUADRO_BYTES], dados[QUADRO_BYTES:]
            if self._repouso:
                self._repouso -= 1
                continue
            if self.modelo.predict(quadro) >= self.limiar:
                disparou = True
                self._repouso = max(1, self.repouso_ms // QUADRO_MS)
                self.modelo.reset()  # a pontuação alta continuaria nos quadros seguintes
        self._resto = dados
        return disparou


class ModeloOpenWakeWord:
    """Adaptador: bytes Int16 -> pontuação máxima do openwakeword. Falha (ImportError/FileNotFoundError...) ao criar."""

    def __init__(self, nome: str = MODELO):
        import numpy as np
        from openwakeword.model import Model
        self._np = np
        self._modelo = Model(wakeword_models=[nome], inference_framework="onnx")

    def predict(self, quadro: bytes) -> float:
        saida = self._modelo.predict(self._np.frombuffer(quadro, dtype=self._np.int16))
        return max(saida.values(), default=0.0)

    def reset(self) -> None:
        self._modelo.reset()


# --- Qt --------------------------------------------------------------------

class PalavraChaveWorker(QThread):
    """Escuta "Hey Jarvis" numa thread própria: `ouviu` quando passa o limiar, `falhou` se não der para carregar."""

    ouviu = pyqtSignal()
    falhou = pyqtSignal(str)

    def __init__(self, parent=None, criar_modelo=ModeloOpenWakeWord):
        super().__init__(parent)
        self._fila: queue.Queue = queue.Queue(maxsize=100)
        self._zerar = False
        self._criar_modelo = criar_modelo

    def alimentar(self, bloco: bytes) -> None:
        try:
            self._fila.put_nowait(bloco)
        except queue.Full:
            pass

    def zerar(self) -> None:
        self._zerar = True

    def _esvaziar(self) -> None:
        try:
            while True:
                self._fila.get_nowait()
        except queue.Empty:
            pass

    def run(self) -> None:
        try:
            detector = DetectorChamada(self._criar_modelo())
        except Exception as e:  # sem openwakeword, sem onnxruntime ou sem o modelo baixado
            self.falhou.emit(f"Hey Jarvis indisponível ({e})")
            return
        while not self.isInterruptionRequested():
            try:
                bloco = self._fila.get(timeout=0.2)
            except queue.Empty:
                continue
            if self._zerar:
                self._zerar = False
                detector.limpar()
                continue
            if detector.alimentar(bloco):
                self._esvaziar()
                self.ouviu.emit()
