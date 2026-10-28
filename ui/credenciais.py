"""Janela local para guardar/apagar senhas de sites. A senha só é digitada aqui, nunca no chat."""

import credenciais
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout

from ui import theme
from ui.widgets import botao


class JanelaCredenciais(QDialog):
    def __init__(self, parent=None, salvar=credenciais.salvar_senha, tem=credenciais.tem_senha,
                 apagar=credenciais.apagar_senha):
        super().__init__(parent)
        self.setWindowTitle("Credenciais")
        self.setStyleSheet(theme.qss())
        self._salvar, self._tem, self._apagar = salvar, tem, apagar
        self._estados: dict = {}
        self._campos: dict = {}
        lay = QVBoxLayout(self)
        aviso = QLabel("As senhas ficam no Gerenciador de Credenciais do Windows e nunca passam pelo chat.")
        aviso.setWordWrap(True)
        lay.addWidget(aviso)
        for cid, c in credenciais.CREDENCIAIS.items():
            lay.addWidget(QLabel(f"<b>{c['rotulo']}</b> — {c['usuario']}"))
            linha = QHBoxLayout()
            estado = QLabel()
            campo = QLineEdit()
            campo.setEchoMode(QLineEdit.EchoMode.Password)
            campo.setPlaceholderText("Nova senha")
            campo.setAccessibleName(f"Senha de {c['rotulo']}")
            b_salvar = botao("Salvar", "primario", nome=f"Salvar senha de {c['rotulo']}")
            b_apagar = botao("Apagar", "", nome=f"Apagar senha de {c['rotulo']}")
            b_salvar.clicked.connect(lambda _=False, i=cid: self._clicar_salvar(i))
            b_apagar.clicked.connect(lambda _=False, i=cid: self._clicar_apagar(i))
            for w in (estado, campo, b_salvar, b_apagar):
                linha.addWidget(w)
            lay.addLayout(linha)
            self._estados[cid], self._campos[cid] = estado, campo
            self._atualizar(cid)

    def estado_texto(self, cid: str) -> str:
        return self._estados[cid].text()

    def _atualizar(self, cid: str, msg: str = "") -> None:
        self._estados[cid].setText(msg or ("salva" if self._tem(cid) else "não salva"))

    def _clicar_salvar(self, cid: str) -> None:
        senha = self._campos[cid].text()
        if not senha:
            self._atualizar(cid, "Digite a senha antes de salvar")
            return
        self._salvar(cid, senha)
        self._campos[cid].clear()
        self._atualizar(cid)

    def _clicar_apagar(self, cid: str) -> None:
        self._apagar(cid)
        self._atualizar(cid)
