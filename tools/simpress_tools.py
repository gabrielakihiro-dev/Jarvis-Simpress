"""Ferramentas do Simpress para o Jarvis.

Define o catálogo de ferramentas (formato OpenAI / OpenRouter), o despachante
que as executa e o texto dos cartões de confirmação. Ferramentas que alteram
dados só rodam depois que o usuário confirma no cartão.

O Jarvis nunca se conecta ao Chrome de automação (porta 9333): tudo passa pela
API do servidor Simpress.
"""

from typing import Any, Callable, Dict, List, Optional

from simpress_client import DECISOES_VALIDAS, ROTINAS_VALIDAS, SimpressClient


def _tool(nome: str, descricao: str, propriedades: Optional[Dict[str, Any]] = None, obrigatorios: Optional[List[str]] = None) -> Dict[str, Any]:
    parametros: Dict[str, Any] = {"type": "object", "properties": propriedades or {}}
    if obrigatorios:
        parametros["required"] = obrigatorios
    return {"type": "function", "function": {"name": nome, "description": descricao, "parameters": parametros}}


_SERIAL = {"type": "string", "description": "Número de série da máquina (ex.: 'BRJ149SCJG', 'CMVXKV7YCM')."}

# Ferramentas que alteram dados: o Jarvis para e pede confirmação ao usuário.
MUTADORAS = frozenset({
    "executar_automacao_chrome",
    "cancelar_automacao_chrome",
    "atualizar_apelido",
    "atualizar_usuario",
    "decidir_pendencia_usuario",
})

TOOLS_SCHEMA: List[Dict[str, Any]] = [
    # Consultas
    _tool(
        "consultar_equipamento",
        "Detalhes de um equipamento pelo número de série (modelo, tipo, cidade, usuário). Trata MacBooks que venham sem a letra 'S'.",
        {"serial": _SERIAL}, ["serial"],
    ),
    _tool(
        "pesquisar_catalogo",
        "Pesquisa equipamentos por texto, cidade, categoria ou status de usuário logado.",
        {
            "termo": {"type": "string", "description": "Modelo ou parte da série (ex.: 'ProBook', 'Dell')."},
            "cidade": {"type": "string", "description": "Cidade (ex.: 'Curitiba', 'Maringá')."},
            "categoria": {"type": "string", "description": "Categoria (ex.: 'notebook', 'macbook', 'desktop')."},
            "usuario": {"type": "string", "enum": ["sem", "com"], "description": "'sem' = sem usuário logado; 'com' = com usuário."},
        },
    ),
    _tool("obter_totais_inventario", "Totais oficiais da base Simpress: máquinas, unidades e alterações pendentes de exportação."),
    _tool("listar_chamados_abertos", "Chamados técnicos e ordens de serviço (OS) em andamento, conferidos ou com divergência."),
    _tool("consultar_status_automacao", "Informa se há rotina de automação do Chrome em execução, qual e o progresso."),
    _tool("consultar_ultima_comparacao", "Data e resumo do último cruzamento de planilhas (divergências, ausentes no Endpoint ou na Simpress)."),
    _tool("obter_painel", "Painel geral do Simpress (visão resumida de inventário, chamados e pendências)."),
    _tool("obter_prontidao", "Disponibilidade dos arquivos e recursos do Simpress (o que está pronto para uso)."),
    _tool("listar_pendencias_operacionais", "Pendências operacionais da última atualização de inventário."),
    _tool(
        "linha_do_tempo_chamados",
        "Linha do tempo dos chamados e OS de um equipamento.",
        {"serial": _SERIAL}, ["serial"],
    ),
    _tool(
        "obter_relatorio_mensal",
        "Dados do relatório mensal de um mês.",
        {"mes": {"type": "string", "description": "Mês no formato AAAA-MM (ex.: '2026-10')."}}, ["mes"],
    ),
    _tool("listar_historico_automacao", "Histórico das últimas rotinas de automação executadas."),
    _tool("resumo_sebrae", "Resumo da sincronização de chamados Sebrae."),
    _tool(
        "consultar_historico_comparacao",
        "Detalhes de uma atualização do Histórico de Planilhas pelo identificador.",
        {"evento_id": {"type": "string", "description": "Identificador do evento do histórico."}}, ["evento_id"],
    ),
    _tool("listar_unidades", "Unidades cadastradas no Simpress."),
    _tool("listar_transferencias", "Histórico de transferências de equipamentos."),
    _tool("listar_pendencias_usuarios", "Pendências de usuários logados aguardando decisão (permitir, recusar, remover ou manter)."),
    # Ações que alteram dados (exigem confirmação do usuário)
    _tool(
        "executar_automacao_chrome",
        "Executa uma rotina de automação pelo servidor Simpress. 'login' abre as abas para autenticação manual; 'inventarios' atualiza inventários (UX + Endpoint); 'os' exporta chamados e OS; 'ambas' roda OS e Inventários; 'usuarios' verifica usuários logados; 'sebrae' sincroniza chamados Sebrae. O usuário confirma antes de rodar.",
        {"rotina": {"type": "string", "enum": list(ROTINAS_VALIDAS), "description": "Rotina a executar."}}, ["rotina"],
    ),
    _tool("cancelar_automacao_chrome", "Interrompe com segurança a rotina de automação em andamento. O usuário confirma antes."),
    _tool(
        "atualizar_apelido",
        "Altera o apelido de um equipamento. O usuário confirma antes.",
        {"serial": _SERIAL, "apelido": {"type": "string", "description": "Novo apelido (até 160 caracteres)."}},
        ["serial", "apelido"],
    ),
    _tool(
        "atualizar_usuario",
        "Altera o usuário manual de um equipamento. O usuário confirma antes.",
        {"serial": _SERIAL, "usuario": {"type": "string", "description": "Nome do usuário."}},
        ["serial", "usuario"],
    ),
    _tool(
        "decidir_pendencia_usuario",
        "Registra a decisão sobre uma pendência de usuário. O usuário confirma antes.",
        {
            "pendencia_id": {"type": "string", "description": "Identificador da pendência (de listar_pendencias_usuarios)."},
            "decisao": {"type": "string", "enum": list(DECISOES_VALIDAS), "description": "Decisão a registrar."},
        },
        ["pendencia_id", "decisao"],
    ),
]

NOMES_FERRAMENTAS = frozenset(t["function"]["name"] for t in TOOLS_SCHEMA)


def requer_confirmacao(nome: str) -> bool:
    return nome in MUTADORAS


def descrever_acao(nome: str, args: Dict[str, Any]) -> str:
    """Texto do cartão de confirmação, montado só a partir dos argumentos (nunca escrito pela IA)."""
    serial = str(args.get("serial", "")).strip().upper()
    if nome == "executar_automacao_chrome":
        return f"Executar a rotina '{args.get('rotina', '')}' de automação no Chrome."
    if nome == "cancelar_automacao_chrome":
        return "Cancelar a rotina de automação em andamento."
    if nome == "atualizar_apelido":
        return f"Alterar o apelido do serial {serial} para '{args.get('apelido', '')}'."
    if nome == "atualizar_usuario":
        return f"Alterar o usuário do serial {serial} para '{args.get('usuario', '')}'."
    if nome == "decidir_pendencia_usuario":
        return f"Registrar a decisão '{args.get('decisao', '')}' na pendência {args.get('pendencia_id', '')}."
    return f"Executar {nome}."


class SimpressToolbox:
    """Executa as chamadas de ferramenta pedidas pelo agente."""

    def __init__(self, client: Optional[SimpressClient] = None):
        self.client = client or SimpressClient()
        c = self.client
        self._despacho: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
            "consultar_equipamento": lambda a: c.consultar_equipamento(str(a.get("serial", ""))),
            "pesquisar_catalogo": lambda a: c.pesquisar_catalogo(
                termo=str(a.get("termo", "")), cidade=a.get("cidade"),
                categoria=a.get("categoria"), usuario=a.get("usuario"),
            ),
            "obter_totais_inventario": lambda a: c.obter_totais_inventario(),
            "listar_chamados_abertos": lambda a: c.listar_chamados_abertos(),
            "consultar_status_automacao": lambda a: c.consultar_status_automacao(),
            "consultar_ultima_comparacao": lambda a: c.consultar_ultima_comparacao(),
            "obter_painel": lambda a: c.obter_painel(),
            "obter_prontidao": lambda a: c.obter_prontidao(),
            "listar_pendencias_operacionais": lambda a: c.listar_pendencias_operacionais(),
            "linha_do_tempo_chamados": lambda a: c.linha_do_tempo_chamados(str(a.get("serial", ""))),
            "obter_relatorio_mensal": lambda a: c.obter_relatorio_mensal(str(a.get("mes", ""))),
            "listar_historico_automacao": lambda a: c.listar_historico_automacao(),
            "resumo_sebrae": lambda a: c.resumo_sebrae(),
            "consultar_historico_comparacao": lambda a: c.consultar_historico_comparacao(str(a.get("evento_id", ""))),
            "listar_unidades": lambda a: c.listar_unidades(),
            "listar_transferencias": lambda a: c.listar_transferencias(),
            "listar_pendencias_usuarios": lambda a: c.listar_pendencias_usuarios(),
            "executar_automacao_chrome": lambda a: c.executar_automacao(str(a.get("rotina", ""))),
            "cancelar_automacao_chrome": lambda a: c.cancelar_automacao(),
            "atualizar_apelido": lambda a: c.atualizar_apelido(str(a.get("serial", "")), str(a.get("apelido", ""))),
            "atualizar_usuario": lambda a: c.atualizar_usuario(str(a.get("serial", "")), str(a.get("usuario", ""))),
            "decidir_pendencia_usuario": lambda a: c.decidir_pendencia_usuario(
                str(a.get("pendencia_id", "")), str(a.get("decisao", ""))
            ),
        }

    def execute(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Despacha a ferramenta pelo nome. Quem chama garante a confirmação das mutadoras."""
        funcao = self._despacho.get(tool_name)
        if funcao is None:
            return {"erro": f"Ferramenta desconhecida: {tool_name}"}
        return funcao(args if isinstance(args, dict) else {})
