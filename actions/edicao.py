"""Edições no cadastro (alteram dados: o usuário confirma antes). O texto do cartão vem só dos argumentos."""

from actions._base import SERIAL, tool
from simpress_client import DECISOES_VALIDAS


def _serial(a):
    return str(a.get("serial", "")).strip().upper()


def _descrever_unidade(a):
    campos = (
        f"cidade {a.get('cidade', '')}, endereço {a.get('endereco', '')}, "
        f"UF {a.get('uf') or 'PR'}, CEP {a.get('cep', '')}, CNPJ {a.get('cnpj', '')}"
    )
    if a.get("id") not in (None, ""):
        return f"Editar a unidade #{a.get('id')}: {campos}."
    return f"Criar nova unidade: {campos}."


TOOLS = [
    tool(
        "atualizar_apelido",
        "Altera o apelido de um equipamento. O usuário confirma antes.",
        lambda c, a: c.atualizar_apelido(str(a.get("serial", "")), str(a.get("apelido", ""))),
        {"serial": SERIAL, "apelido": {"type": "string", "description": "Novo apelido (até 160 caracteres)."}},
        ["serial", "apelido"],
        altera_dados=True,
        descrever=lambda a: f"Alterar o apelido do serial {_serial(a)} para '{a.get('apelido', '')}'.",
    ),
    tool(
        "atualizar_usuario",
        "Altera o usuário manual de um equipamento. O usuário confirma antes.",
        lambda c, a: c.atualizar_usuario(str(a.get("serial", "")), str(a.get("usuario", ""))),
        {"serial": SERIAL, "usuario": {"type": "string", "description": "Nome do usuário."}},
        ["serial", "usuario"],
        altera_dados=True,
        descrever=lambda a: f"Alterar o usuário do serial {_serial(a)} para '{a.get('usuario', '')}'.",
    ),
    tool(
        "salvar_unidade",
        "Edita uma unidade existente (informe o id de listar_unidades) ou cria uma nova (sem id). Envie todos os campos, repetindo os que não mudam. O usuário confirma antes.",
        lambda c, a: c.salvar_unidade(
            cidade=str(a.get("cidade", "")), endereco=str(a.get("endereco", "")), cnpj=str(a.get("cnpj", "")),
            uf=str(a.get("uf", "") or "PR"), cep=str(a.get("cep", "") or ""), id=a.get("id"),
        ),
        {
            "id": {"type": "integer", "description": "Id da unidade a editar (de listar_unidades). Omita só para criar."},
            "cidade": {"type": "string"},
            "endereco": {"type": "string"},
            "uf": {"type": "string", "description": "Sigla com 2 letras (padrão PR)."},
            "cep": {"type": "string"},
            "cnpj": {"type": "string"},
        },
        ["cidade", "endereco", "cnpj"],
        altera_dados=True,
        descrever=_descrever_unidade,
    ),
    tool(
        "decidir_pendencia_usuario",
        "Registra a decisão sobre uma pendência de usuário. O usuário confirma antes.",
        lambda c, a: c.decidir_pendencia_usuario(str(a.get("pendencia_id", "")), str(a.get("decisao", ""))),
        {
            "pendencia_id": {"type": "string", "description": "Identificador da pendência (de listar_pendencias_usuarios)."},
            "decisao": {"type": "string", "enum": list(DECISOES_VALIDAS), "description": "Decisão a registrar."},
        },
        ["pendencia_id", "decisao"],
        altera_dados=True,
        descrever=lambda a: f"Registrar a decisão '{a.get('decisao', '')}' na pendência {a.get('pendencia_id', '')}.",
    ),
]
