"""Ferramentas do Jarvis, uma por item de `TOOL`/`TOOLS` em cada módulo deste pacote.

Para criar uma ferramenta, adicione um módulo aqui (sem `_` no início) com `TOOL = tool(...)`
ou `TOOLS = [tool(...), ...]` (veja `_base.py`). A descoberta olha só este pacote: nenhum
código de fora dele é carregado.
"""

import importlib
import os
import pkgutil
from typing import Any, Dict


def carregar() -> Dict[str, Dict[str, Any]]:
    achadas: Dict[str, Dict[str, Any]] = {}
    # Modo leve (servidor_leve.py): sem Chrome nem keyring, então sem as ferramentas de navegador e PC.
    pular = {"navegador", "pc"} if os.environ.get("JARVIS_MODO_LEVE") == "1" else set()
    for modulo in sorted(m.name for m in pkgutil.iter_modules(__path__) if not m.name.startswith("_") and m.name not in pular):
        mod = importlib.import_module(f"{__name__}.{modulo}")
        itens = ([mod.TOOL] if hasattr(mod, "TOOL") else []) + list(getattr(mod, "TOOLS", []))
        for item in itens:
            nome = item["schema"]["function"]["name"]
            if nome in achadas:
                raise ValueError(f"Ferramenta duplicada: {nome}")
            achadas[nome] = item
    return achadas
