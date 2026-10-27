"""Ferramentas do Simpress para o Jarvis.

O catálogo vem do pacote `actions/` (uma ferramenta por item `TOOL`/`TOOLS`). Este módulo
monta o formato OpenAI / OpenRouter, o despachante e o texto dos cartões de confirmação.
Ferramentas que alteram dados só rodam depois que o usuário confirma no cartão.

O Jarvis nunca se conecta ao Chrome de automação (porta 9333): tudo passa pela
API do servidor Simpress.
"""

from typing import Any, Dict, List, Optional

from actions import carregar
from simpress_client import SimpressClient

_FERRAMENTAS = carregar()

TOOLS_SCHEMA: List[Dict[str, Any]] = [t["schema"] for t in _FERRAMENTAS.values()]
NOMES_FERRAMENTAS = frozenset(_FERRAMENTAS)

# Ferramentas que alteram dados: o Jarvis para e pede confirmação ao usuário.
# Sem "altera_dados" explícito, a ferramenta conta como mutadora.
MUTADORAS = frozenset(nome for nome, t in _FERRAMENTAS.items() if t.get("altera_dados", True))


def requer_confirmacao(nome: str) -> bool:
    return nome in MUTADORAS


def descrever_acao(nome: str, args: Dict[str, Any]) -> str:
    """Texto do cartão de confirmação, montado só a partir dos argumentos (nunca escrito pela IA)."""
    descrever = _FERRAMENTAS.get(nome, {}).get("descrever")
    return descrever(args) if descrever else f"Executar {nome}."


class SimpressToolbox:
    """Executa as chamadas de ferramenta pedidas pelo agente."""

    def __init__(self, client: Optional[SimpressClient] = None):
        self.client = client or SimpressClient()

    def execute(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Despacha a ferramenta pelo nome. Quem chama garante a confirmação das mutadoras."""
        ferramenta = _FERRAMENTAS.get(tool_name)
        if ferramenta is None:
            return {"erro": f"Ferramenta desconhecida: {tool_name}"}
        return ferramenta["executar"](self.client, args if isinstance(args, dict) else {})
