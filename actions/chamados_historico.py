"""Histórico do acompanhamento de chamados (somente leitura): importações, uma importação e a evolução entre duas."""

from actions._base import tool

TOOLS = [
    tool(
        "historico_chamados",
        "Lista as importações do acompanhamento de chamados (mais recentes primeiro): id, data, arquivos de origem e resumo. "
        "Os ids servem a snapshot_chamados e evolucao_chamados.",
        lambda c, a: c.historico_chamados(a.get("limite")),
        {"limite": {"type": "integer", "description": "Quantas importações trazer (1 a 20, padrão 10)."}},
        altera_dados=False,
    ),
    tool(
        "snapshot_chamados",
        "Mostra uma importação do acompanhamento de chamados: resumo, contagem e as primeiras séries com a relação de OS. "
        "O id vem de historico_chamados.",
        lambda c, a: c.snapshot_chamados(a.get("id")),
        {"id": {"type": "string", "description": "Id da importação (de historico_chamados)."}},
        ["id"],
        altera_dados=False,
    ),
    tool(
        "evolucao_chamados",
        "Compara duas importações do acompanhamento de chamados: séries novas, alteradas (com os nomes dos campos) e ausentes "
        "no arquivo mais novo. Para a evolução do inventário use evolucao_atualizacoes.",
        lambda c, a: c.evolucao_chamados(a.get("anterior"), a.get("atual")),
        {
            "anterior": {"type": "string", "description": "Id da importação mais antiga (de historico_chamados)."},
            "atual": {"type": "string", "description": "Id da importação mais nova (de historico_chamados)."},
        },
        ["anterior", "atual"],
        altera_dados=False,
    ),
]
