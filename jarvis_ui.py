"""Ponto de entrada do Jarvis com interface HUD (PyQt5). A janela fica em ui/shell.py."""

import os
import sys

# Precisa vir antes de criar o QApplication quando o WebEngine é usado.
from PyQt5.QtCore import Qt, QCoreApplication

QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)

from dotenv import load_dotenv

load_dotenv()

from PyQt5.QtWidgets import QApplication  # noqa: E402

from ui import theme  # noqa: E402
from ui.shell import JarvisShell  # noqa: E402


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyleSheet(theme.qss())
    janela = JarvisShell()
    janela.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
