"""Rotinas de automação do Chrome (alteram dados: o usuário confirma antes)."""

from actions._base import tool
from simpress_client import ROTINAS_VALIDAS

TOOLS = [
    tool(
        "executar_automacao_chrome",
        "Executa uma rotina de automação pelo servidor Simpress. 'login' abre as abas para autenticação manual; 'inventarios' atualiza inventários (UX + Endpoint); 'os' exporta chamados e OS; 'ambas' roda OS e Inventários; 'usuarios' verifica usuários logados; 'sebrae' sincroniza chamados Sebrae. O usuário confirma antes de rodar.",
        lambda c, a: c.executar_automacao(str(a.get("rotina", ""))),
        {"rotina": {"type": "string", "enum": list(ROTINAS_VALIDAS), "description": "Rotina a executar."}}, ["rotina"],
        altera_dados=True,
        descrever=lambda a: f"Executar a rotina '{a.get('rotina', '')}' de automação no Chrome.",
    ),
    tool(
        "cancelar_automacao_chrome",
        "Interrompe com segurança a rotina de automação em andamento. O usuário confirma antes.",
        lambda c, a: c.cancelar_automacao(),
        altera_dados=True,
        descrever=lambda a: "Cancelar a rotina de automação em andamento.",
    ),
]
