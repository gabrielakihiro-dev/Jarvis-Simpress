"""Senhas no Gerenciador de Credenciais do Windows (via keyring).

A senha nunca e logada nem incluida em excecoes.
"""
import os
from typing import Any, Dict, Optional

import keyring
from keyring.errors import PasswordDeleteError

CREDENCIAIS: Dict[str, Dict[str, Any]] = {
    "microsoft-simpress": {
        "rotulo": "Microsoft Simpress (Dashboard)",
        "usuario_env": "JARVIS_CONTA_MICROSOFT",  # e-mail da conta: fica no .env, não no código
        "hosts": ("login.microsoftonline.com",),
    },
}


class ContaNaoConfigurada(ValueError):
    """A variável do .env com o e-mail da conta não foi preenchida."""

    def __init__(self, variavel: str):
        self.variavel = variavel
        super().__init__(f"Falta configurar {variavel} (e-mail da conta) no arquivo .env do Jarvis.")


def usuario(cred_id: str, obrigatorio: bool = True) -> str:
    """E-mail da conta, lido do .env na hora do uso. Sem ele: ContaNaoConfigurada (ou "" se não for obrigatório)."""
    variavel = CREDENCIAIS[cred_id]["usuario_env"]
    valor = os.environ.get(variavel, "").strip()
    if not valor and obrigatorio:
        raise ContaNaoConfigurada(variavel)
    return valor


def servico(cred_id: str) -> str:
    CREDENCIAIS[cred_id]  # KeyError se desconhecido
    return f"Jarvis/{cred_id}"


def salvar_senha(cred_id: str, senha: str) -> None:
    if not senha:
        raise ValueError("senha vazia")
    keyring.set_password(servico(cred_id), usuario(cred_id), senha)


def senha(cred_id: str) -> Optional[str]:
    return keyring.get_password(servico(cred_id), usuario(cred_id))


def tem_senha(cred_id: str) -> bool:
    return bool(senha(cred_id))


def apagar_senha(cred_id: str) -> None:
    try:
        keyring.delete_password(servico(cred_id), usuario(cred_id))
    except PasswordDeleteError:
        pass
