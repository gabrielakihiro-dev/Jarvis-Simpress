import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QLineEdit, QPushButton

from ui.credenciais import JanelaCredenciais

app = QApplication.instance() or QApplication([])


def janela(tem_inicial=False):
    estado = {"salva": tem_inicial}
    chamadas = []

    def salvar(i, s):
        chamadas.append(("salvar", i, s))
        estado["salva"] = True

    def apagar(i):
        chamadas.append(("apagar", i))
        estado["salva"] = False

    j = JanelaCredenciais(salvar=salvar, tem=lambda i: estado["salva"], apagar=apagar)
    return j, chamadas


def botao(j, texto):
    return next(b for b in j.findChildren(QPushButton) if b.text() == texto)


def test_campo_e_senha_e_salvar_limpa_e_marca_salva():
    j, chamadas = janela()
    campo = j.findChild(QLineEdit)
    assert campo.echoMode() == QLineEdit.EchoMode.Password
    assert "não salva" in j.estado_texto("microsoft-simpress")
    campo.setText("x")
    botao(j, "Salvar").click()
    assert chamadas == [("salvar", "microsoft-simpress", "x")]
    assert campo.text() == ""
    assert j.estado_texto("microsoft-simpress") == "salva"


def test_senha_vazia_nao_chama_salvar():
    j, chamadas = janela()
    botao(j, "Salvar").click()
    assert chamadas == []
    assert "Digite" in j.estado_texto("microsoft-simpress")


def test_apagar():
    j, chamadas = janela(tem_inicial=True)
    assert j.estado_texto("microsoft-simpress") == "salva"
    botao(j, "Apagar").click()
    assert chamadas == [("apagar", "microsoft-simpress")]
    assert "não salva" in j.estado_texto("microsoft-simpress")
