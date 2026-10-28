import pytest

import navegador_jarvis as nj
from actions import navegador as nav
from login_receitas import RECEITAS, rodar_receita


class PaginaFalsa:
    def __init__(self, hosts, campos, explode_em=None, texto_erro="", textos=(set(),)):
        self.hosts, self.campos, self.preenchidos = list(hosts), set(campos), []
        self.textos, self.clicados = list(textos), []  # textos: visíveis a cada tem_texto; repete o último
        self.explode_em, self.texto_erro = explode_em, texto_erro

    def _talvez_explodir(self, metodo):
        if self.explode_em == metodo:
            raise Exception(self.texto_erro)

    def host(self):
        self._talvez_explodir("host")
        return self.hosts.pop(0) if len(self.hosts) > 1 else self.hosts[0]

    def ir(self, url):
        self._talvez_explodir("ir")

    def clicar_texto(self, texto):
        self._talvez_explodir("clicar_texto")
        self.clicados.append(texto)
        return False

    def tem_campo(self, tipo):
        self._talvez_explodir("tem_campo")
        return tipo in self.campos

    def tem_texto(self, texto):
        return texto in (self.textos.pop(0) if len(self.textos) > 1 else self.textos[0])

    def preencher(self, tipo, valor, hosts=None):
        self._talvez_explodir("preencher")
        self.preenchidos.append((tipo, valor))


def test_senha_so_no_host_permitido():
    p = PaginaFalsa(hosts=["phish.com"], campos={"senha"})
    r = rodar_receita("dashboard", p, obter_senha=lambda c: "S3nh@")
    assert r == {"login": "falhou", "site": "dashboard", "motivo": "Página fora dos endereços permitidos para esta senha."}
    assert p.preenchidos == []


def test_login_ok_e_resultado_sem_senha():
    p = PaginaFalsa(hosts=["login.microsoftonline.com"] * 4 + ["simpress-my.sharepoint.com"], campos={"usuario", "senha"})
    r = rodar_receita("dashboard", p, obter_senha=lambda c: "S3nh@", dormir=lambda s: None)
    assert r == {"login": "ok", "site": "dashboard"} and "S3nh@" not in str(r)
    assert ("senha", "S3nh@") in p.preenchidos


def test_mfa_nao_aprovado_em_2_min():
    relogio = iter(range(0, 1000, 2))
    p = PaginaFalsa(hosts=["login.microsoftonline.com"] * 999, campos={"senha"})
    r = rodar_receita("dashboard", p, obter_senha=lambda c: "x", agora=lambda: next(relogio), dormir=lambda s: None)
    assert r["login"] == "aguardando_mfa"


def test_sem_senha_cadastrada():
    p = PaginaFalsa(hosts=["login.microsoftonline.com"] * 9, campos={"senha"})
    assert rodar_receita("dashboard", p, obter_senha=lambda c: None)["motivo"].startswith("Senha não cadastrada")


def test_excecao_vira_mensagem_fixa():
    p = PaginaFalsa(hosts=["login.microsoftonline.com"] * 9, campos={"senha"}, explode_em="preencher", texto_erro="S3nh@")
    r = rodar_receita("dashboard", p, obter_senha=lambda c: "S3nh@")
    assert r["motivo"] == "Erro no navegador durante o login." and "S3nh@" not in str(r)


def test_ja_logado_nao_digita():
    p = PaginaFalsa(hosts=["simpress-my.sharepoint.com"], campos=set())
    assert rodar_receita("dashboard", p, obter_senha=lambda c: 1 / 0)["login"] == "ok"


def test_erro_do_cofre_vira_mensagem_fixa():
    def cofre(c):
        raise RuntimeError("keyring S3nh@")

    p = PaginaFalsa(hosts=["login.microsoftonline.com"] * 9, campos={"senha"})
    r = rodar_receita("dashboard", p, obter_senha=cofre)
    assert r == {"login": "falhou", "site": "dashboard", "motivo": "Erro no navegador durante o login."}


def test_host_conferido_logo_antes_de_digitar():
    # O campo apareceu, mas a aba já foi para outro host: não digita.
    p = PaginaFalsa(hosts=["login.microsoftonline.com", "phish.com"], campos={"senha"})
    r = rodar_receita("dashboard", p, obter_senha=lambda c: "S3nh@")
    assert r["motivo"] == "Página fora dos endereços permitidos para esta senha." and p.preenchidos == []


def test_softexpert_ok_so_quando_o_sso_some():
    # A tela de login do SoftExpert já está no host final: o botão SSO visível ainda não é login.
    p = PaginaFalsa(hosts=["sebraepr.softexpert.app"], campos=set(), textos=[{"SSO"}] * 3 + [set()])
    r = rodar_receita("softexpert", p, obter_senha=lambda c: 1 / 0, dormir=lambda s: None)
    assert r == {"login": "ok", "site": "softexpert"} and p.preenchidos == []
    assert "SSO" in p.clicados and p.textos == [set()]


def test_softexpert_sso_visivel_por_2_min_aguarda():
    relogio = iter(range(0, 1000, 2))
    p = PaginaFalsa(hosts=["sebraepr.softexpert.app"], campos=set(), textos=[{"SSO"}])
    r = rodar_receita("softexpert", p, agora=lambda: next(relogio), dormir=lambda s: None)
    assert r == {"login": "aguardando_mfa", "site": "softexpert"}


def test_softexpert_ja_logado_nao_clica():
    p = PaginaFalsa(hosts=["sebraepr.softexpert.app"], campos=set())
    assert rodar_receita("softexpert", p, obter_senha=lambda c: 1 / 0) == {"login": "ok", "site": "softexpert"}
    assert p.clicados == []


def test_logar_site_devolve_resultado_da_receita(monkeypatch):
    from contextlib import contextmanager

    @contextmanager
    def conectar():
        yield object()

    monkeypatch.setattr(nj, "conectar", conectar)
    monkeypatch.setattr(nj, "pagina_ativa", lambda b: "page")
    monkeypatch.setattr(nj, "PaginaPlaywright", lambda page: ("adaptada", page))
    monkeypatch.setattr(nav, "rodar_receita", lambda site, pagina: {"login": "ok", "site": site, "p": pagina})
    item = next(t for t in nav.TOOLS if t["schema"]["function"]["name"] == "logar_site")
    assert item["executar"](None, {"site": "dashboard"}) == {"login": "ok", "site": "dashboard", "p": ("adaptada", "page")}
    assert item["schema"]["function"]["parameters"]["properties"]["site"]["enum"] == list(RECEITAS)
    assert item["executar"](None, {"site": "google"}) == {"erro": "Não tenho receita de login para esse site."}


def test_adaptador_devolve_false_no_timeout():
    pw = pytest.importorskip("playwright.sync_api")

    class Loc:
        first = property(lambda self: self)

        def wait_for(self, **kw):
            raise pw.TimeoutError("demorou")

        def click(self, **kw):
            raise pw.TimeoutError("demorou")

        def or_(self, outro):
            return self

    class Page:
        url = "https://Login.MicrosoftOnline.com/x"
        locator = get_by_text = get_by_role = lambda self, *a, **kw: Loc()

    p = nj.PaginaPlaywright(Page())
    assert p.host() == "login.microsoftonline.com"
    assert p.tem_campo("senha") is False and p.clicar_texto("Sim") is False and p.tem_texto("SSO") is False


def test_adaptador_confere_host_colado_no_fill():
    class Campo:
        preenchido = None
        first = property(lambda self: self)

        def fill(self, valor, **kw):
            self.preenchido = valor

        def press(self, tecla, **kw):
            pass

    class Page:
        url = "https://phish.com/login"
        campo = Campo()
        locator = lambda self, sel: self.campo

    page = Page()
    p = nj.PaginaPlaywright(page)
    with pytest.raises(nj.NavegadorErro):
        p.preencher("senha", "S3nh@", hosts=("login.microsoftonline.com",))
    assert page.campo.preenchido is None
    page.url = "https://login.microsoftonline.com/x"
    p.preencher("senha", "S3nh@", hosts=("login.microsoftonline.com",))
    assert page.campo.preenchido == "S3nh@"
