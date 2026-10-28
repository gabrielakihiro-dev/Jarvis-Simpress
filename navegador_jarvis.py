"""Chrome próprio do Jarvis (visível, perfil dedicado, CDP local) e escolha da aba ativa."""

import os
import subprocess
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import List

PORTA = int(os.environ.get("JARVIS_CHROME_PORTA", "9334"))
PERFIL = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "JarvisChrome"
_ABAS_VAZIAS = ("about:blank", "chrome://newtab/", "chrome://new-tab-page/")


class NavegadorErro(Exception):
    """Mensagem já pronta para a IA."""


def localizar_chrome() -> Path:
    candidatos = [
        Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
    ]
    for caminho in candidatos:
        if caminho.is_file():
            return caminho
    raise NavegadorErro("Google Chrome não encontrado neste computador.")


def comando_chrome(chrome: Path) -> List[str]:
    return [
        str(chrome),
        f"--remote-debugging-port={PORTA}",
        "--remote-debugging-address=127.0.0.1",
        f"--user-data-dir={PERFIL}",
        "--no-first-run",
        "--no-default-browser-check",
    ]


def cdp_ativo() -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORTA}/json/version", timeout=2):
            return True
    except Exception:
        return False


def garantir_chrome(espera_s: float = 10, popen=subprocess.Popen, ativo=cdp_ativo, dormir=time.sleep) -> None:
    if ativo():
        return
    popen(comando_chrome(localizar_chrome()))
    for _ in range(int(espera_s / 0.5)):
        dormir(0.5)
        if ativo():
            return
    raise NavegadorErro("O Chrome do Jarvis não respondeu.")


@contextmanager
def conectar():
    """Entrega o Browser do Chrome do Jarvis; ao sair só encerra o Playwright (o Chrome fica aberto)."""
    from playwright.sync_api import sync_playwright  # import tardio: o módulo carrega sem playwright

    garantir_chrome()
    with sync_playwright() as p:
        yield p.chromium.connect_over_cdp(f"http://127.0.0.1:{PORTA}")


def pagina_ativa(browser):
    contexto = browser.contexts[0]
    paginas = contexto.pages
    for pagina in paginas:
        if pagina.evaluate("document.visibilityState") == "visible":
            return pagina
    return paginas[-1] if paginas else contexto.new_page()


def abrir_abas(urls: List[str]) -> None:
    with conectar() as browser:
        for i, url in enumerate(urls):
            pagina = pagina_ativa(browser) if i == 0 else None
            if pagina is None or pagina.url not in _ABAS_VAZIAS:
                pagina = browser.contexts[0].new_page()
            pagina.goto(url, wait_until="commit")
