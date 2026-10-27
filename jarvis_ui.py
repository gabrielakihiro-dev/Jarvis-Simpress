"""Ponto de entrada do Jarvis com interface HUD (PyQt6). A janela fica em ui/shell.py."""

import os
import sys

# Precisa vir antes de criar o QApplication quando o WebEngine é usado.
from PyQt6.QtCore import Qt, QCoreApplication

QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)

from dotenv import load_dotenv

load_dotenv()

from PyQt6.QtWidgets import QApplication  # noqa: E402

from ui import theme  # noqa: E402
from ui.shell import JarvisShell  # noqa: E402


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyleSheet(theme.qss())
    janela = JarvisShell()
    janela.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
