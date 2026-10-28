from actions.pc import abrir_alvos, achar_atalhos
from sites import CATALOGO, normalizar, resolver_site


def test_apelidos_soltos_resolvem():
    assert resolver_site("Endpoint") == CATALOGO["endpoint"]["url"]
    assert resolver_site("o Soft Expert") == CATALOGO["softexpert"]["url"]
    assert resolver_site("UX") == CATALOGO["ux"]["url"]
    assert resolver_site("https://www.google.com") == "https://www.google.com"


def test_esquemas_perigosos_recusados():
    for alvo in ("file:///C:/Windows", "javascript:alert(1)", "http://", "ftp://x"):
        assert resolver_site(alvo) is None


def test_normalizar():
    assert normalizar("  Área   de TRABALHO ") == "area de trabalho"


def _menu(tmp_path, *nomes):
    for n in nomes:
        (tmp_path / f"{n}.lnk").write_text("x")
    return [tmp_path]


def test_atalho_por_nome_sem_acento_e_ambiguo(tmp_path):
    pastas = _menu(tmp_path, "Bloco de Notas", "Excel", "Excel Viewer")
    assert [p.stem for p in achar_atalhos("bloco de notas", pastas)] == ["Bloco de Notas"]
    assert [p.stem for p in achar_atalhos("excel", pastas)] == ["Excel"]  # igual vence "contém"
    assert sorted(p.stem for p in achar_atalhos("exc", pastas)) == ["Excel", "Excel Viewer"]


def test_abrir_varios_de_uma_vez(tmp_path):
    sites, progs = [], []
    r = abrir_alvos(["youtube", "endpoint", "bloco de notas", "nada disso", "file:///c:/x"],
                    abrir_site=sites.extend, abrir_programa=progs.append, pastas=_menu(tmp_path, "Bloco de Notas"))
    assert sites == [CATALOGO["youtube"]["url"], CATALOGO["endpoint"]["url"]]
    assert progs == [str(tmp_path / "Bloco de Notas.lnk")]
    erros = [x["alvo"] for x in r["resultados"] if "erro" in x]
    assert erros == ["nada disso", "file:///c:/x"]


def test_atalho_ambiguo_devolve_opcoes(tmp_path):
    r = abrir_alvos(["exc"], abrir_site=list, abrir_programa=lambda p: 1 / 0,
                    pastas=_menu(tmp_path, "Excel", "Excel Viewer"))
    assert sorted(r["resultados"][0]["opcoes"]) == ["Excel", "Excel Viewer"]


def test_atalho_duplicado_em_duas_pastas_nao_e_ambiguo(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(), b.mkdir()
    pastas = _menu(a, "Excel") + _menu(b, "Excel")
    assert [p.stem for p in achar_atalhos("excel", pastas)] == ["Excel"]
    progs = []
    r = abrir_alvos(["excel"], abrir_site=list, abrir_programa=progs.append, pastas=pastas)
    assert r["resultados"] == [{"alvo": "excel", "aberto": "programa"}]
    assert progs == [str(a / "Excel.lnk")]


def test_alvos_string_vira_lista(monkeypatch):
    import navegador_jarvis
    from actions.pc import TOOL
    chamadas = []
    monkeypatch.setattr(navegador_jarvis, "abrir_abas", chamadas.append)
    r = TOOL["executar"](None, {"alvos": "youtube"})
    assert chamadas == [[CATALOGO["youtube"]["url"]]]
    assert r["resultados"] == [{"alvo": "youtube", "aberto": "site"}]


def test_abrir_site_com_excecao_qualquer_vira_erro_so_nos_sites(tmp_path):
    def quebra(urls):
        raise RuntimeError("boom")
    progs = []
    r = abrir_alvos(["youtube", "bloco de notas"], abrir_site=quebra, abrir_programa=progs.append,
                    pastas=_menu(tmp_path, "Bloco de Notas"))
    assert r["resultados"] == [{"alvo": "youtube", "erro": "Não consegui abrir o site."},
                               {"alvo": "bloco de notas", "aberto": "programa"}]


def test_tool_abre_no_chrome_do_jarvis(monkeypatch):
    import navegador_jarvis
    from actions.pc import TOOL
    chamadas = []
    monkeypatch.setattr(navegador_jarvis, "abrir_abas", chamadas.append)
    r = TOOL["executar"](None, {"alvos": ["youtube", "endpoint"]})
    assert chamadas == [[CATALOGO["youtube"]["url"], CATALOGO["endpoint"]["url"]]]
    assert "aviso" not in r


def test_tool_cai_para_navegador_padrao(monkeypatch):
    import webbrowser
    import navegador_jarvis
    from actions.pc import TOOL

    def falha(urls):
        raise navegador_jarvis.NavegadorErro("sem chrome")
    abertas = []
    monkeypatch.setattr(navegador_jarvis, "abrir_abas", falha)
    monkeypatch.setattr(webbrowser, "open", abertas.append)
    r = TOOL["executar"](None, {"alvos": ["youtube", "endpoint"]})
    assert abertas == [CATALOGO["youtube"]["url"], CATALOGO["endpoint"]["url"]]
    assert r["aviso"] == "Abri no navegador padrão: o Chrome do Jarvis não respondeu."
    assert all(x["aberto"] == "site" for x in r["resultados"])
