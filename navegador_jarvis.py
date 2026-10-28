"""Chrome próprio do Jarvis (visível, perfil dedicado, CDP local) e escolha da aba ativa."""

import json
import os
import re
import subprocess
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Iterable, List
from urllib.parse import urlparse

from sites import normalizar

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


def _ordem_das_abas() -> List[str]:
    """ids das abas (type=page) do Chrome, da mais recentemente ativada para a mais antiga."""
    with urllib.request.urlopen(f"http://127.0.0.1:{PORTA}/json/list", timeout=2) as r:
        return [t["id"] for t in json.load(r) if t.get("type") == "page"]


def _id_da_aba(contexto, pagina) -> str:
    sessao = contexto.new_cdp_session(pagina)
    try:
        return sessao.send("Target.getTargetInfo")["targetInfo"]["targetId"]
    finally:
        sessao.detach()


def pagina_ativa(browser):
    # No Windows várias abas dizem "visible"; o /json/list põe a última ativada primeiro.
    contexto = browser.contexts[0] if browser.contexts else browser.new_context()
    paginas = contexto.pages
    if not paginas:
        return contexto.new_page()
    try:
        primeira = _ordem_das_abas()[0]
        for pagina in paginas:
            try:
                if _id_da_aba(contexto, pagina) == primeira:
                    return pagina
            except Exception:
                continue
    except Exception:
        pass
    for pagina in paginas:
        try:
            if pagina.evaluate("document.visibilityState") == "visible":
                return pagina
        except Exception:
            continue
    return paginas[-1]


def abrir_abas(urls: List[str]) -> None:
    with conectar() as browser:
        for i, url in enumerate(urls):
            pagina = pagina_ativa(browser) if i == 0 else None
            if pagina is None or pagina.url not in _ABAS_VAZIAS:
                pagina = browser.contexts[0].new_page()
            pagina.goto(url, wait_until="commit")


PALAVRAS_RISCO = frozenset(
    "enviar salvar gravar registrar aplicar excluir apagar remover finalizar concluir confirmar "
    "aprovar reprovar encerrar atribuir publicar send save delete submit ok".split()
)


def e_arriscado(textos: Iterable[str]) -> bool:
    """True se algum texto tem uma palavra de risco inteira (sem acento, minúsculo)."""
    return any(p in PALAVRAS_RISCO for t in textos for p in re.findall(r"\w+", normalizar(t or "")))


def host_de(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def salva_sozinho(url: str) -> bool:
    return host_de(url).endswith(".sharepoint.com")


def _primeiro_visivel(loc):
    for item in loc.all():
        if item.is_visible():
            return item
    return None


def achar_elemento(page, alvo: str):
    # Escada de busca adaptada de open-jarvis/openjarvis browser.py (Apache License 2.0).
    tentativas = []
    if alvo[:1] in ("#", ".", "[") or "=" in alvo:
        tentativas.append(lambda: page.locator(alvo))
    tentativas += [
        lambda: page.get_by_text(alvo, exact=True),
        lambda: page.get_by_role("button", name=alvo),
        lambda: page.get_by_role("link", name=alvo),
        lambda: page.get_by_label(alvo),
        lambda: page.get_by_placeholder(alvo),
        lambda: page.get_by_text(alvo),
    ]
    for tentar in tentativas:
        try:
            achado = _primeiro_visivel(tentar())
        except Exception:  # seletor inválido etc.: segue a escada
            continue
        if achado:
            return achado
    raise NavegadorErro(f"Não achei '{alvo}' na página.")


_JS_NOMES = r"""(e) => {
  const attrs = ['aria-label', 'title', 'alt'];
  const t = [e.innerText];
  for (const a of attrs) t.push(e.getAttribute(a));
  if (['submit', 'button', 'reset'].includes((e.getAttribute('type') || '').toLowerCase())) t.push(e.getAttribute('value'));
  for (const id of (e.getAttribute('aria-labelledby') || '').split(/\s+/)) {
    const r = id && document.getElementById(id);
    if (r) t.push(r.innerText || r.getAttribute('aria-label'));
  }
  for (const d of e.querySelectorAll('[alt], [title], [aria-label]')) for (const a of attrs) t.push(d.getAttribute(a));
  return t.filter(x => x && x.trim());
}"""


def textos_do_elemento(loc) -> List[str]:
    """Tudo que dá nome ao elemento (inclusive alt/title de filhos e aria-labelledby); nunca value de campo."""
    return loc.evaluate(_JS_NOMES)


def e_senha(loc) -> bool:
    return (loc.get_attribute("type") or "").lower() == "password"


_JS_ELEMENTOS = r"""(max) => {
  const out = [];
  const nome = (e) => (__NOMES__)(e)[0] || '';
  const rotuloCampo = (e) => {
    const l = e.labels && e.labels[0];
    return (l && l.innerText) || e.getAttribute('aria-label') || e.placeholder || e.name || '';
  };
  for (const e of document.querySelectorAll('button, a[href], input, textarea, select, [role=button]')) {
    if (out.length >= max) break;
    if (!e.getClientRects().length) continue;
    const tipo = (e.type || '').toLowerCase();
    let kind, rotulo;
    if (e.matches('input, textarea, select')) {
      if (tipo === 'hidden') continue;
      if (['submit', 'button', 'reset', 'image'].includes(tipo)) { kind = 'botao'; rotulo = (tipo === 'image' ? '' : e.value) || nome(e); }
      else { kind = 'campo'; rotulo = rotuloCampo(e); }
    } else {
      kind = e.matches('a') ? 'link' : 'botao';
      rotulo = nome(e);
    }
    rotulo = rotulo.replace(/\s+/g, ' ').trim();
    if (rotulo) out.push({tipo: kind, rotulo});
  }
  return out;
}""".replace("__NOMES__", _JS_NOMES)


def extrair_pagina(page, limite: int = 5000, max_elementos: int = 60) -> Dict:
    """Título, url, texto e rótulos dos controles. Nunca lê o valor de campos."""
    texto = page.evaluate("document.body ? document.body.innerText : ''")
    return {
        "titulo": page.title(),
        "url": page.url,
        "texto_pagina": texto[:limite],
        "elementos": page.evaluate(_JS_ELEMENTOS, max_elementos),
    }


class PaginaPlaywright:
    """Adaptador da `login_receitas.PaginaLogin` sobre uma page do Playwright. Espera até 5 s por elemento."""

    CAMPOS = {"usuario": "input[type=email], input[name=loginfmt]", "senha": "input[type=password]"}

    def __init__(self, page):
        self.page = page

    def host(self) -> str:
        return host_de(self.page.url)

    def ir(self, url: str) -> None:
        self.page.goto(url, wait_until="domcontentloaded", timeout=15000)

    def clicar_texto(self, texto: str) -> bool:
        from playwright.sync_api import TimeoutError as Demorou

        p = self.page
        alvo = p.get_by_role("button", name=texto, exact=True).or_(
            p.get_by_role("link", name=texto, exact=True)).or_(p.get_by_text(texto, exact=True))
        try:
            alvo.first.click(timeout=5000)
            return True
        except Demorou:
            return False

    def tem_campo(self, tipo: str) -> bool:
        from playwright.sync_api import TimeoutError as Demorou

        try:
            self.page.locator(self.CAMPOS[tipo]).first.wait_for(state="visible", timeout=5000)
            return True
        except Demorou:
            return False

    def preencher(self, tipo: str, valor: str) -> None:
        campo = self.page.locator(self.CAMPOS[tipo]).first
        campo.fill(valor, timeout=5000)
        campo.press("Enter")
