import pytest

import navegador_jarvis as nj

HTML = """<label for=u>Usuário</label><input id=u value="joao.silva">
<input type=password aria-label=Senha value="segredo123">
<button aria-label="Excluir"><svg></svg></button><input type=submit value="Buscar">
<p>Olá mundo</p>"""


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
