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
