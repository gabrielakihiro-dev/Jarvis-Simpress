import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# QApplication única da suíte (é também uma QCoreApplication: test_escuta a reaproveita).
# Sem isto, o QCoreApplication de test_escuta faria os widgets de outros testes falharem.
import os  # noqa: E402

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication  # noqa: E402

APP = QApplication.instance() or QApplication([])
