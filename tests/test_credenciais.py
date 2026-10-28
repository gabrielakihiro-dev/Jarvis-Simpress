import logging

import keyring
import pytest
from keyring.backend import KeyringBackend
from keyring.errors import PasswordDeleteError

import credenciais


class _Memoria(KeyringBackend):
    priority = 1

    def __init__(self):
        self.d = {}

    def get_password(self, servico, usuario):
        return self.d.get((servico, usuario))

    def set_password(self, servico, usuario, senha):
        self.d[(servico, usuario)] = senha

    def delete_password(self, servico, usuario):
        if (servico, usuario) not in self.d:
            raise PasswordDeleteError("nao existe")
        del self.d[(servico, usuario)]


@pytest.fixture(autouse=True)
def backend():
    anterior = keyring.get_keyring()
    keyring.set_keyring(_Memoria())
    yield
    keyring.set_keyring(anterior)


CID = "microsoft-simpress"


def test_servico():
    assert credenciais.servico(CID) == "Jarvis/microsoft-simpress"


def test_salvar_ler_apagar():
    assert not credenciais.tem_senha(CID)
    assert credenciais.senha(CID) is None
    credenciais.salvar_senha(CID, "s3gredo")
    assert credenciais.tem_senha(CID)
    assert credenciais.senha(CID) == "s3gredo"
    credenciais.apagar_senha(CID)
    assert not credenciais.tem_senha(CID)


def test_apagar_sem_senha_nao_levanta():
    credenciais.apagar_senha(CID)


def test_senha_vazia():
    with pytest.raises(ValueError):
        credenciais.salvar_senha(CID, "")


def test_id_desconhecido():
    for f in (credenciais.tem_senha, credenciais.apagar_senha, credenciais.senha, credenciais.servico):
        with pytest.raises(KeyError):
            f("nao-existe")
    with pytest.raises(KeyError):
        credenciais.salvar_senha("nao-existe", "x")


def test_senha_fora_do_log(caplog):
    with caplog.at_level(logging.DEBUG):
        credenciais.salvar_senha(CID, "s3gredo")
        credenciais.senha(CID)
        credenciais.apagar_senha(CID)
    assert "s3gredo" not in caplog.text
