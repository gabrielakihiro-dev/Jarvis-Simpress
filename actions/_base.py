"""Auxiliar das ferramentas: monta o dicionário TOOL no formato esperado por actions/__init__.py."""

from typing import Any, Callable, Dict, List, Optional

SERIAL = {"type": "string", "description": "Número de série da máquina (ex.: 'BRJ149SCJG', 'CMVXKV7YCM')."}


def tool(
    nome: str,
    descricao: str,
    executar: Callable[[Any, Dict[str, Any]], Dict[str, Any]],
    propriedades: Optional[Dict[str, Any]] = None,
    obrigatorios: Optional[List[str]] = None,
    altera_dados: bool = False,
    descrever: Optional[Callable[[Dict[str, Any]], str]] = None,
) -> Dict[str, Any]:
    """`executar(client, args)` roda a ferramenta; `descrever(args)` monta o texto do cartão de confirmação."""
    parametros: Dict[str, Any] = {"type": "object", "properties": propriedades or {}}
    if obrigatorios:
        parametros["required"] = obrigatorios
    item: Dict[str, Any] = {
        "schema": {"type": "function", "function": {"name": nome, "description": descricao, "parameters": parametros}},
        "executar": executar,
        "altera_dados": altera_dados,
    }
    if descrever:
        item["descrever"] = descrever
    return item
