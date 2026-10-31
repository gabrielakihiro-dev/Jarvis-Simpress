"""Escritas do assistente do site (alteram dados: o usuário confirma antes). O texto do cartão vem só dos argumentos."""

from actions._base import SERIAL, tool
from lgpd import limpar_texto_sensivel
from simpress_client import ACOES_APELIDO_MANUAL


def _serial(a):
    return str(a.get("serial", "")).strip().upper()


def _txt(a, campo):
    return limpar_texto_sensivel(str(a.get(campo, "")).strip())


def _descrever_transferencia(a):
    extras = "".join(
        f"; {rotulo} {_txt(a, campo)}"
        for campo, rotulo in (("entrega_cidade", "cidade"), ("descricao_equipamento", "equipamento"), ("entrega_obs", "obs."))
        if _txt(a, campo)
    )
    return (
        f"Registrar no histórico de transferências a série {_serial(a)}: entrega para {_txt(a, 'entrega_contato')}, "
        f"{_txt(a, 'entrega_endereco')}, CNPJ {_txt(a, 'entrega_cnpj')}{extras}. "
        "Só registra a linha no histórico; não gera a planilha de transferência (isso é feito na tela de Transferência)."
    )


def _descrever_apelido_manual(a):
    acao, serial, evento = str(a.get("acao", "")).strip().lower(), _serial(a), str(a.get("evento_id", "")).strip()
    if acao == "manter":
        return f"Manter o apelido manual da série {serial} e marcar a divergência do evento {evento} como resolvida."
    return (
        f"Excluir o apelido manual da série {serial}: o apelido volta a seguir as planilhas de origem, a base é recarregada "
        f"e a divergência do evento {evento} fica resolvida. O sistema recusa se o apelido manual mudou desde a comparação."
    )


def _descrever_nome_pessoa(a):
    nome = _txt(a, "nome")
    if not nome:
        return f"Remover o nome manual da pessoa do login atual da série {_serial(a)}; o nome volta ao que vier do Entra, se houver."
    return f"Salvar o nome '{nome}' para o login atual da série {_serial(a)} (vale para esse login, não só para este equipamento)."


TOOLS = [
    tool(
        "registrar_transferencia",
        "Registra uma linha no histórico de transferências (só o registro; NÃO gera a planilha de transferência). "
        "E-mail e celular não passam por aqui: para eles, oriente a usar a tela de Transferência. O usuário confirma antes.",
        lambda c, a: c.registrar_transferencia(a),
        {
            "serial": SERIAL,
            "entrega_cnpj": {"type": "string", "description": "CNPJ da entrega (14 dígitos)."},
            "entrega_endereco": {"type": "string", "description": "Endereço da entrega."},
            "entrega_contato": {"type": "string", "description": "Nome do contato da entrega."},
            "entrega_cidade": {"type": "string", "description": "Cidade (opcional)."},
            "descricao_equipamento": {"type": "string", "description": "Descrição do equipamento (opcional)."},
            "entrega_obs": {"type": "string", "description": "Observação (opcional)."},
        },
        ["serial", "entrega_cnpj", "entrega_endereco", "entrega_contato"],
        altera_dados=True,
        descrever=_descrever_transferencia,
    ),
    tool(
        "resolver_apelido_manual",
        "Resolve uma divergência de apelido manual de um evento do Histórico de Planilhas: 'manter' o apelido manual ou "
        "'excluir' (o apelido volta a seguir as planilhas). Só divergência pendente. O usuário confirma antes.",
        lambda c, a: c.resolver_apelido_manual(a.get("evento_id", ""), a.get("serial", ""), a.get("acao", "")),
        {
            "evento_id": {"type": "string", "description": "Id do evento (de consultar_historico_comparacao)."},
            "serial": SERIAL,
            "acao": {"type": "string", "enum": list(ACOES_APELIDO_MANUAL), "description": "manter ou excluir o apelido manual."},
        },
        ["evento_id", "serial", "acao"],
        altera_dados=True,
        descrever=_descrever_apelido_manual,
    ),
    tool(
        "salvar_nome_pessoa",
        "Grava o nome da pessoa que usa o login atual de um equipamento; nome vazio remove o nome manual. "
        "O login é obtido pelo sistema. O usuário confirma antes.",
        lambda c, a: c.salvar_nome_pessoa(a.get("serial", ""), a.get("nome", "")),
        {"serial": SERIAL, "nome": {"type": "string", "description": "Nome da pessoa, nas palavras do usuário (vazio remove)."}},
        ["serial", "nome"],
        altera_dados=True,
        descrever=_descrever_nome_pessoa,
    ),
    tool(
        "excluir_chamados_antigos",
        "Apaga as importações antigas do acompanhamento de chamados e mantém só a mais recente. Não dá para desfazer. "
        "O usuário confirma antes.",
        lambda c, a: c.excluir_chamados_antigos(),
        altera_dados=True,
        descrever=lambda a: (
            "Excluir as importações antigas do acompanhamento de chamados: só a mais recente fica. "
            "A linha do tempo e a evolução entre importações perdem esse histórico. Não dá para desfazer."
        ),
    ),
    tool(
        "recarregar_base",
        "Recarrega a base a partir da planilha válida mais recente da pasta de entrada (substitui os dados em memória). "
        "O usuário confirma antes.",
        lambda c, a: c.recarregar_base(),
        altera_dados=True,
        descrever=lambda a: (
            "Recarregar a base: a planilha válida mais recente da pasta de entrada substitui os dados em memória do sistema. "
            "As planilhas em si não são alteradas."
        ),
    ),
]
