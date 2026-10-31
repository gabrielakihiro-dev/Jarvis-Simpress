"""Consultas ao Simpress (somente leitura)."""

from actions._base import SERIAL, tool

BULLET = ' Para listas sem tabela própria, use um bullet "•" por campo, todos no mesmo nível, sem deixar campo sem bullet.'

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
        "Data e resumo do último cruzamento de planilhas (divergências, ausentes no Endpoint ou na Simpress). "
        "O total de 'apelidos sem atualização' vem no campo `apelidos_sem_atualizacao` de `resumo_divergencias`: informe só o número "
        "(não existe lista item a item dessa seção).",
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
        "Linha do tempo dos chamados e OS de um equipamento." + BULLET,
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
        "Histórico das últimas rotinas de automação executadas." + BULLET,
        lambda c, a: c.listar_historico_automacao(),
    ),
    tool("resumo_sebrae", "Resumo da sincronização de chamados Sebrae.", lambda c, a: c.resumo_sebrae()),
    tool(
        "consultar_historico_comparacao",
        "Detalhes de uma atualização do Histórico de Planilhas pelo identificador. Divergência de localidade e transferência "
        "são dados diferentes: não liste transferências como se fossem as divergências encontradas.",
        lambda c, a: c.consultar_historico_comparacao(str(a.get("evento_id", ""))),
        {"evento_id": {"type": "string", "description": "Identificador do evento do histórico."}}, ["evento_id"],
    ),
    tool(
        "listar_unidades",
        "Unidades cadastradas no Simpress, com id, cidade, endereço, UF, CEP e CNPJ.",
        lambda c, a: c.listar_unidades(),
    ),
    tool(
        "listar_transferencias",
        "Histórico de transferências de equipamentos. Cada item já traz `hostname`: ao apresentar uma transferência, "
        "inclua o `hostname` em uma linha logo abaixo da Série. Transferência não é divergência de localidade: nunca "
        "liste transferências como se fossem as divergências encontradas, nem presuma que toda série divergente tem "
        "transferência registrada." + BULLET,
        lambda c, a: c.listar_transferencias(),
    ),
    tool(
        "listar_divergencias_localidade",
        "Lista todas as séries da seção 'Localidade divergente' do último cruzamento de planilhas (local cadastrado na Simpress diferente do previsto pela série). "
        "Para listar as séries divergentes, use esta ferramenta (nunca `listar_transferencias`). "
        "Diga o total (ex.: 'Encontrei 6 localidades divergentes.') e liste cada item de `itens` (série, computador, local_previsto, "
        "local_na_simpress), seja a pergunta geral ou específica (ex.: 'qual o local previsto dessa série?'). "
        "Quando vier `transferencias_relacionadas` (lista não vazia), apresente cada transferência em texto logo após a frase do total: "
        "um bullet '•' por campo (Série, De, Para, Contato, Observação), todos no mesmo nível de indentação, com uma linha em branco "
        "entre uma transferência e a próxima. Se vier `aviso_transferencias`, informe esse aviso no texto. "
        "O cruzamento com transferências já vem pronto: não chame `listar_transferencias` à parte para isso.",
        lambda c, a: c.listar_divergencias_localidade(),
    ),
    tool(
        "consultar_divergencia_localidade",
        "Verifica se uma série aparece na seção 'Localidade divergente' do último cruzamento de planilhas (local cadastrado na Simpress diferente do previsto pela série). "
        "Divergência e transferência são dados diferentes: não presuma que uma série divergente tem transferência registrada.",
        lambda c, a: c.consultar_divergencia_localidade(str(a.get("serial", ""))),
        {"serial": SERIAL}, ["serial"],
    ),
    tool(
        "listar_pendencias_usuarios",
        "Pendências de usuários logados aguardando decisão (permitir, recusar, remover ou manter).",
        lambda c, a: c.listar_pendencias_usuarios(),
    ),
    tool(
        "listar_secao_comparacao",
        "Lista os itens de uma seção do último cruzamento de planilhas: correspondências ambíguas "
        "(séries/hostnames duplicados ou conflitantes; cada item tem 'chave' ou, se for duplicidade "
        "de série, 'serie'/'computador'), séries sem mapeamento, apelidos/hostnames atualizados, "
        "divergências de apelidos manuais (apelido digitado manualmente diferente do que está nas "
        "planilhas) ou mudanças de usuário logado. Use para responder 'qual' é a série, apelido ou "
        "usuário por trás de um total mostrado no painel. Responda com os itens de `itens` (o `total` já é o número oficial do painel): "
        "em 'correspondencias_ambiguas' cada item tem `chave` ou, se for duplicidade de série, `serie`/`computador`; "
        "em 'series_sem_mapeamento', 'apelidos_atualizados' e 'divergencias_apelidos_manuais' use `serie`; "
        "em 'mudancas_usuarios' use `usuario_anterior`/`usuario_novo`. Não cobre 'apelidos sem atualização' "
        "(nunca use secao 'apelidos_atualizados' para essa pergunta): para esse total, use consultar_ultima_comparacao "
        "(não há lista item a item dele).",
        lambda c, a: c.listar_secao_comparacao(str(a.get("secao", ""))),
        {
            "secao": {
                "type": "string",
                "enum": [
                    "correspondencias_ambiguas",
                    "series_sem_mapeamento",
                    "apelidos_atualizados",
                    "divergencias_apelidos_manuais",
                    "mudancas_usuarios",
                ],
                "description": "Seção a listar.",
            }
        },
        ["secao"],
    ),
]
