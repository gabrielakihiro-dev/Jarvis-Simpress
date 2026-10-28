"""Senhas no Gerenciador de Credenciais do Windows (via keyring).

A senha nunca e logada nem incluida em excecoes.
"""
from typing import Any, Dict, Optional

import keyring
from keyring.errors import PasswordDeleteError

CREDENCIAIS: Dict[str, Dict[str, Any]] = {
    "microsoft-simpress": {
        "rotulo": "Microsoft Simpress (Dashboard)",
        "usuario": "gansouza@simpress.com.br",
        "hosts": ("login.microsoftonline.com",),
    },
}


def servico(cred_id: str) -> str:
    CREDENCIAIS[cred_id]  # KeyError se desconhecido
    return f"Jarvis/{cred_id}"


def salvar_senha(cred_id: str, senha: str) -> None:
    if not senha:
        raise ValueError("senha vazia")
    keyring.set_password(servico(cred_id), CREDENCIAIS[cred_id]["usuario"], senha)


def senha(cred_id: str) -> Optional[str]:
    return keyring.get_password(servico(cred_id), CREDENCIAIS[cred_id]["usuario"])


def tem_senha(cred_id: str) -> bool:
    return bool(senha(cred_id))


def apagar_senha(cred_id: str) -> None:
    try:
        keyring.delete_password(servico(cred_id), CREDENCIAIS[cred_id]["usuario"])
    except PasswordDeleteError:
        pass
