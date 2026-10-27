"""Consultas ao Simpress (somente leitura)."""

from actions._base import SERIAL, tool

TOOLS = [
    tool(
        "consultar_equipamento",
        "Detalhes de um equipamento pelo número de série (modelo, tipo, cidade, usuário). Trata MacBooks que venham sem a letra 'S'.",
        lambda c, a: c.consultar_equipamento(str(a.get("serial", ""))),
        {"serial": SERIAL}, ["serial"],
    ),
    tool(
        "pesquisar_catalogo",
        "Pesquisa equipamentos por texto, cidade, categoria ou status de usuário logado.",
        lambda c, a: c.pesquisar_catalogo(
            termo=str(a.get("termo", "")), cidade=a.get("cidade"),
            categoria=a.get("categoria"), usuario=a.get("usuario"),
        ),
        {
            "termo": {"type": "string", "description": "Modelo ou parte da série (ex.: 'ProBook', 'Dell')."},
            "cidade": {"type": "string", "description": "Cidade (ex.: 'Curitiba', 'Maringá')."},
            "categoria": {"type": "string", "description": "Categoria (ex.: 'notebook', 'macbook', 'desktop')."},
            "usuario": {"type": "string", "enum": ["sem", "com"], "description": "'sem' = sem usuário logado; 'com' = com usuário."},
        },
    ),
    tool(
        "obter_totais_inventario",
        "Totais oficiais da base Simpress: máquinas, unidades e alterações pendentes de exportação.",
        lambda c, a: c.obter_totais_inventario(),
    ),
    tool(
        "listar_chamados_abertos",
        "Chamados técnicos e ordens de serviço (OS) em andamento, conferidos ou com divergência.",
        lambda c, a: c.listar_chamados_abertos(),
    ),
    tool(
        "consultar_status_automacao",
        "Informa se há rotina de automação do Chrome em execução, qual e o progresso.",
        lambda c, a: c.consultar_status_automacao(),
    ),
    tool(
        "consultar_ultima_comparacao",
        "Data e resumo do último cruzamento de planilhas (divergências, ausentes no Endpoint ou na Simpress).",
        lambda c, a: c.consultar_ultima_comparacao(),
    ),
    tool(
        "obter_painel",
        "Painel geral do Simpress (visão resumida de inventário, chamados e pendências).",
        lambda c, a: c.obter_painel(),
    ),
    tool(
        "obter_prontidao",
        "Disponibilidade dos arquivos e recursos do Simpress (o que está pronto para uso).",
        lambda c, a: c.obter_prontidao(),
    ),
    tool(
        "listar_pendencias_operacionais",
        "Pendências operacionais da última atualização de inventário.",
        lambda c, a: c.listar_pendencias_operacionais(),
    ),
    tool(
        "linha_do_tempo_chamados",
        "Linha do tempo dos chamados e OS de um equipamento.",
        lambda c, a: c.linha_do_tempo_chamados(str(a.get("serial", ""))),
        {"serial": SERIAL}, ["serial"],
    ),
    tool(
        "obter_relatorio_mensal",
        "Dados do relatório mensal de um mês.",
        lambda c, a: c.obter_relatorio_mensal(str(a.get("mes", ""))),
        {"mes": {"type": "string", "description": "Mês no formato AAAA-MM (ex.: '2026-10')."}}, ["mes"],
    ),
    tool(
        "listar_historico_automacao",
        "Histórico das últimas rotinas de automação executadas.",
        lambda c, a: c.listar_historico_automacao(),
    ),
    tool("resumo_sebrae", "Resumo da sincronização de chamados Sebrae.", lambda c, a: c.resumo_sebrae()),
    tool(
        "consultar_historico_comparacao",
        "Detalhes de uma atualização do Histórico de Planilhas pelo identificador.",
        lambda c, a: c.consultar_historico_comparacao(str(a.get("evento_id", ""))),
        {"evento_id": {"type": "string", "description": "Identificador do evento do histórico."}}, ["evento_id"],
    ),
    tool(
        "listar_unidades",
        "Unidades cadastradas no Simpress, com id, cidade, endereço, UF, CEP e CNPJ.",
        lambda c, a: c.listar_unidades(),
    ),
    tool("listar_transferencias", "Histórico de transferências de equipamentos.", lambda c, a: c.listar_transferencias()),
    tool(
        "listar_pendencias_usuarios",
        "Pendências de usuários logados aguardando decisão (permitir, recusar, remover ou manter).",
        lambda c, a: c.listar_pendencias_usuarios(),
    ),
]
