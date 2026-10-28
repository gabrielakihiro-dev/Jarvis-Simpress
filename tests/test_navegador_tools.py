from contextlib import contextmanager

import pytest

import navegador_jarvis as nj
from llm_client import SYSTEM_PROMPT
from tools.simpress_tools import SimpressToolbox, descrever_acao

box = SimpressToolbox(client=object())


class Elemento:
    def __init__(self, pagina, textos, senha=False):
        self.pagina, self.textos, self.senha = pagina, textos, senha

    def click(self, **kw):
        self.pagina.cliques.append(self.textos)

    def fill(self, texto, **kw):
        self.pagina.digitados.append(texto)

    def press(self, tecla, **kw):
        self.pagina.teclas.append(tecla)


class PaginaFalsa:
    def __init__(self):
        self.url, self.titulo, self.senha = "https://a.com/", "A", False
        self.cliques, self.digitados, self.teclas, self.gotos = [], [], [], []
        self._textos = ["Ver"]

    def elemento(self, textos):
        self._textos = textos

    def title(self):
        return self.titulo

    def goto(self, url, **kw):
        self.gotos.append((url, kw))
        self.url = url


@pytest.fixture
def pagina_falsa(monkeypatch):
    p = PaginaFalsa()

    @contextmanager
    def conectar():
        yield object()

    monkeypatch.setattr(nj, "conectar", conectar)
    monkeypatch.setattr(nj, "pagina_ativa", lambda b: p)
    monkeypatch.setattr(nj, "achar_elemento", lambda page, alvo: Elemento(p, p._textos, p.senha))
    monkeypatch.setattr(nj, "textos_do_elemento", lambda loc: loc.textos)
    monkeypatch.setattr(nj, "e_senha", lambda loc: loc.senha)
    return p


def test_clicar_arriscado_nao_clica(pagina_falsa):
    pagina_falsa.elemento(textos=["Excluir"])
    assert box.execute("clicar", {"alvo": "Excluir"})["erro"].startswith("Ação que altera dados")
    assert pagina_falsa.cliques == []


def test_clicar_livre_clica(pagina_falsa):
    assert box.execute("clicar", {"alvo": "Ver"}) == {"clicou": "Ver", "url": "https://a.com/"}
    assert pagina_falsa.cliques == [["Ver"]]


def test_confirmado_recusa_host_diferente(pagina_falsa):
    pagina_falsa.url = "https://outro.com/x"
    r = box.execute("clicar_confirmado", {"alvo": "Salvar", "host": "sebraepr.softexpert.app"})
    assert "mudou" in r["erro"] and pagina_falsa.cliques == []


def test_confirmado_mesmo_host_clica(pagina_falsa):
    pagina_falsa.elemento(textos=["Salvar"])
    r = box.execute("clicar_confirmado", {"alvo": "Salvar", "host": "A.com"})
    assert r["clicou"] == "Salvar" and pagina_falsa.cliques == [["Salvar"]]


def test_digitar_no_sharepoint_pede_confirmacao_e_senha_nunca(pagina_falsa):
    pagina_falsa.url = "https://simpress-my.sharepoint.com/:x:/r/a"
    assert "digitar_confirmado" in box.execute("digitar", {"campo": "A1", "texto": "x"})["erro"]
    pagina_falsa.url, pagina_falsa.senha = "https://a.com", True
    assert "logar_site" in box.execute("digitar_confirmado", {"campo": "Senha", "texto": "x", "host": "a.com"})["erro"]
    assert "logar_site" in box.execute("digitar", {"campo": "Senha", "texto": "x"})["erro"]
    assert pagina_falsa.digitados == []


def test_digitar_com_enter(pagina_falsa):
    r = box.execute("digitar", {"campo": "Buscar", "texto": "lo-fi", "enter": True})
    assert "erro" not in r and pagina_falsa.digitados == ["lo-fi"] and pagina_falsa.teclas == ["Enter"]


def test_navegar_valida_alvo_e_usa_goto(pagina_falsa):
    assert "erro" in box.execute("navegar", {"alvo": "file:///c:/x"})
    assert pagina_falsa.gotos == []
    r = box.execute("navegar", {"alvo": "https://b.com/"})
    assert r == {"url": "https://b.com/", "titulo": "A"}
    assert pagina_falsa.gotos == [("https://b.com/", {"wait_until": "domcontentloaded", "timeout": 15000})]


def test_excecao_do_playwright_vira_mensagem_fixa(pagina_falsa, monkeypatch):
    def explode(page, alvo):
        raise RuntimeError("segredo digitado")

    monkeypatch.setattr(nj, "achar_elemento", explode)
    assert box.execute("digitar", {"campo": "x", "texto": "segredo"}) == {"erro": "Erro no navegador."}


def test_navegador_erro_passa_a_mensagem(pagina_falsa, monkeypatch):
    def nao_acha(page, alvo):
        raise nj.NavegadorErro("Não achei 'x' na página.")

    monkeypatch.setattr(nj, "achar_elemento", nao_acha)
    assert box.execute("clicar", {"alvo": "x"}) == {"erro": "Não achei 'x' na página."}


def test_abas_listar_trocar_e_indice_invalido(pagina_falsa):
    class Aba:
        def __init__(self, url):
            self.url, self.frente = url, False

        def title(self):
            return "T"

        def bring_to_front(self):
            self.frente = True

    abas = [Aba("https://a.com/"), Aba("https://b.com/")]
    pagina_falsa.context = type("Ctx", (), {"pages": abas})()
    assert box.execute("abas", {"acao": "listar"})["abas"][1] == {"indice": 1, "titulo": "T", "url": "https://b.com/"}
    box.execute("abas", {"acao": "trocar", "indice": 1})
    assert abas[1].frente
    assert "erro" in box.execute("abas", {"acao": "fechar", "indice": 5})


def test_cartao_do_dashboard_avisa_da_rotina():
    t = descrever_acao("clicar_confirmado", {"alvo": "Salvar", "host": "simpress-my.sharepoint.com"})
    assert t.startswith("Clicar em 'Salvar' em simpress-my.sharepoint.com.") and "30 min" in t
    assert descrever_acao("digitar_confirmado", {"campo": "A1", "texto": "5", "host": "a.com"}) == \
        "Digitar '5' em 'A1' em a.com."
    assert descrever_acao("digitar_confirmado", {"campo": "A1", "texto": "5", "host": "a.com", "enter": True}) ==         "Digitar '5' em 'A1' e apertar Enter em a.com."


def test_prompt_trata_pagina_como_dado():
    assert "conteudo_pagina" in SYSTEM_PROMPT
