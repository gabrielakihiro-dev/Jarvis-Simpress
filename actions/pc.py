"""Abrir sites (catálogo ou URL http/https) e programas (atalhos do Menu Iniciar)."""

import os
import webbrowser
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import navegador_jarvis
from actions._base import tool
from sites import CATALOGO, normalizar, resolver_site, variavel_faltando

MAX_ALVOS = 10


def _pastas_menu_iniciar() -> List[Path]:
    bases = (os.environ.get("ProgramData"), os.environ.get("APPDATA"))
    return [Path(b) / "Microsoft" / "Windows" / "Start Menu" / "Programs" for b in bases if b]


def achar_atalhos(nome: str, pastas: Optional[List[Path]] = None) -> List[Path]:
    """`.lnk` do Menu Iniciar cujo nome é igual ao pedido; sem igual, os que o contêm."""
    pedido = normalizar(nome)
    if not pedido:
        return []
    todos: Dict[str, Path] = {}  # mesmo nome em ProgramData e APPDATA conta uma vez (fica o primeiro caminho)
    for pasta in pastas if pastas is not None else _pastas_menu_iniciar():
        for p in pasta.rglob("*.lnk"):
            todos.setdefault(normalizar(p.stem), p)
    if pedido in todos:
        return [todos[pedido]]
    return [p for n, p in todos.items() if pedido in n]


def abrir_alvos(
    alvos: List[str],
    abrir_site: Callable[[List[str]], Optional[str]],
    abrir_programa: Callable[[str], None] = os.startfile,
    pastas: Optional[List[Path]] = None,
) -> Dict[str, Any]:
    """Abre cada alvo; sites do pedido vão juntos numa só chamada de `abrir_site` (pode devolver um aviso)."""
    resultados: List[Dict[str, Any]] = []
    urls: List[str] = []
    for alvo in alvos[:MAX_ALVOS]:
        url = resolver_site(alvo)
        if url:
            urls.append(url)
            resultados.append({"alvo": alvo, "aberto": "site"})
            continue
        faltando = variavel_faltando(alvo)
        if faltando:
            resultados.append({"alvo": alvo, "erro": f"Falta configurar {faltando} no arquivo .env do Jarvis."})
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
    saida: Dict[str, Any] = {"resultados": resultados}
    if urls:
        try:
            aviso = abrir_site(urls)
            if aviso:
                saida["aviso"] = aviso
        except Exception:
            for r in resultados:
                if r.get("aberto") == "site":
                    del r["aberto"]
                    r["erro"] = "Não consegui abrir o site."
    return saida


def _abrir_no_navegador(urls: List[str]) -> Optional[str]:
    """Abre no Chrome do Jarvis; se ele não responder, cai para o navegador padrão e avisa."""
    try:
        navegador_jarvis.abrir_abas(urls)
        return None
    except navegador_jarvis.NavegadorErro:
        for u in urls:
            webbrowser.open(u)
        return "Abri no navegador padrão: o Chrome do Jarvis não respondeu."


def _executar(_cliente: Any, args: Dict[str, Any]) -> Dict[str, Any]:
    alvos = args.get("alvos", [])
    if isinstance(alvos, str):  # o modelo às vezes manda uma string só
        alvos = [alvos]
    return abrir_alvos([str(x) for x in alvos], _abrir_no_navegador)


TOOL = tool(
    "abrir",
    "Abre vários sites e programas de uma vez. Cada alvo é um nome do catálogo (" + ", ".join(s["nome"] for s in CATALOGO.values())
    + "), uma URL http/https ou o nome de um programa instalado. Aceita vários alvos num só pedido (máx. 10).",
    _executar,
    {"alvos": {"type": "array", "items": {"type": "string"}, "description": "Sites, URLs ou programas a abrir."}},
    ["alvos"],
    altera_dados=False,
)
