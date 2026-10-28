"""Abrir sites (catálogo ou URL http/https) e programas (atalhos do Menu Iniciar)."""

import os
import webbrowser
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from actions._base import tool
from sites import CATALOGO, normalizar, resolver_site

MAX_ALVOS = 10


def _pastas_menu_iniciar() -> List[Path]:
    bases = (os.environ.get("ProgramData"), os.environ.get("APPDATA"))
    return [Path(b) / "Microsoft" / "Windows" / "Start Menu" / "Programs" for b in bases if b]


def achar_atalhos(nome: str, pastas: Optional[List[Path]] = None) -> List[Path]:
    """`.lnk` do Menu Iniciar cujo nome é igual ao pedido; sem igual, os que o contêm."""
    pedido = normalizar(nome)
    if not pedido:
        return []
    todos = [p for pasta in (pastas if pastas is not None else _pastas_menu_iniciar()) for p in pasta.rglob("*.lnk")]
    iguais = [p for p in todos if normalizar(p.stem) == pedido]
    return iguais or [p for p in todos if pedido in normalizar(p.stem)]


def abrir_alvos(
    alvos: List[str],
    abrir_site: Callable[[List[str]], None],
    abrir_programa: Callable[[str], None] = os.startfile,
    pastas: Optional[List[Path]] = None,
) -> Dict[str, Any]:
    """Abre cada alvo; sites do pedido vão juntos numa só chamada de `abrir_site`."""
    resultados: List[Dict[str, Any]] = []
    urls: List[str] = []
    for alvo in alvos[:MAX_ALVOS]:
        url = resolver_site(alvo)
        if url:
            urls.append(url)
            resultados.append({"alvo": alvo, "aberto": "site"})
            continue
        if ":" in alvo and "/" in alvo:  # esquema não permitido (file:, ftp:...) não vira busca de atalho
            resultados.append({"alvo": alvo, "erro": "Só abro sites http/https, nomes do catálogo ou programas do Menu Iniciar."})
            continue
        atalhos = achar_atalhos(alvo, pastas)
        if len(atalhos) == 1:
            try:
                abrir_programa(str(atalhos[0]))
                resultados.append({"alvo": alvo, "aberto": "programa"})
            except OSError as e:
                resultados.append({"alvo": alvo, "erro": f"Não consegui abrir: {e}"})
        elif atalhos:
            resultados.append({"alvo": alvo, "opcoes": sorted(p.stem for p in atalhos)})
        else:
            resultados.append({"alvo": alvo, "erro": "Não achei site no catálogo nem programa com esse nome."})
    if urls:
        abrir_site(urls)
    return {"resultados": resultados}


def _abrir_no_navegador(urls: List[str]) -> None:
    # shortcut: navegador padrão do Windows; a Fase 2 troca pelo Chrome do Jarvis.
    for u in urls:
        webbrowser.open(u)


TOOL = tool(
    "abrir",
    "Abre vários sites e programas de uma vez. Cada alvo é um nome do catálogo (" + ", ".join(s["nome"] for s in CATALOGO.values())
    + "), uma URL http/https ou o nome de um programa instalado. Aceita vários alvos num só pedido (máx. 10).",
    lambda c, a: abrir_alvos([str(x) for x in a.get("alvos", [])], _abrir_no_navegador),
    {"alvos": {"type": "array", "items": {"type": "string"}, "description": "Sites, URLs ou programas a abrir."}},
    ["alvos"],
    altera_dados=False,
)
