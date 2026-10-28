import pytest

import navegador_jarvis as nj

HTML = """<label for=u>Usuário</label><input id=u value="joao.silva">
<input type=password aria-label=Senha value="segredo123">
<button aria-label="Excluir"><svg></svg></button><input type=submit value="Buscar">
<button><img alt="Excluir"></button><button><span title="Apagar"></span></button>
<span id=rot>Remover</span><button aria-labelledby=rot></button>
<input type=image alt="Enviar"><p>Olá mundo</p>"""


@pytest.fixture
def pagina():
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="chrome", headless=True)
        except Exception as e:
            pytest.skip(f"Chrome indisponível: {e}")
        try:
            yield browser.new_page()
        finally:
            browser.close()


def test_ler_pagina_nao_devolve_valor_de_campo(pagina):
    pagina.set_content(HTML)
    dados = nj.extrair_pagina(pagina)
    bruto = str(dados)
    assert "joao.silva" not in bruto and "segredo123" not in bruto
    assert "Olá mundo" in dados["texto_pagina"]
    assert {"tipo": "campo", "rotulo": "Usuário"} in dados["elementos"]


def test_botao_so_icone_e_arriscado(pagina):
    pagina.set_content(HTML)
    assert nj.e_arriscado(nj.textos_do_elemento(nj.achar_elemento(pagina, "Excluir")))
    assert not nj.e_arriscado(nj.textos_do_elemento(nj.achar_elemento(pagina, "Buscar")))
    assert nj.e_senha(nj.achar_elemento(pagina, "Senha"))


def test_nome_vindo_de_filho_ou_labelledby_e_arriscado(pagina):
    pagina.set_content(HTML)
    for alvo in ("Apagar", "Remover", "Enviar"):
        assert nj.e_arriscado(nj.textos_do_elemento(nj.achar_elemento(pagina, alvo))), alvo
    pagina.set_content('<button><img alt="Excluir"></button>')
    assert nj.e_arriscado(nj.textos_do_elemento(nj.achar_elemento(pagina, "Excluir")))
    assert {"tipo": "botao", "rotulo": "Excluir"} in nj.extrair_pagina(pagina)["elementos"]


def test_filho_de_botao_ou_link_reporta_nome_do_pai(pagina):
    pagina.set_content('<button id="b1"><span>Salvar</span> <span>alterações</span></button>')
    assert nj.e_arriscado(nj.textos_do_elemento(nj.achar_elemento(pagina, "alterações")))
    pagina.set_content('<a href="#"><span>Excluir</span><em>item</em></a>')
    assert nj.e_arriscado(nj.textos_do_elemento(nj.achar_elemento(pagina, "item")))
