"""Usuário logado de várias séries de uma vez (somente leitura; nomes e logins passam pela máscara LGPD)."""

from actions._base import tool

TOOL = tool(
    "usuarios_logados",
    "Consulta o usuário logado e o nome da pessoa de até 20 séries de uma vez (sem alterar nada). "
    "Para uma série só, consultar_equipamento já traz. Nomes e logins chegam como marcadores [PESSOA_n]: use-os como vieram.",
    lambda c, a: c.usuarios_logados(a.get("series")),
    {"series": {"type": "array", "items": {"type": "string"}, "description": "Séries a consultar (até 20)."}},
    ["series"],
    altera_dados=False,
)
