"""E-mails e link pessoal vêm do .env (variáveis JARVIS_*), com falha clara quando faltam."""
import sys
from pathlib import Path

import keyring
import pytest
from keyring.backend import KeyringBackend

import credenciais
from actions.pc import abrir_alvos
from login_receitas import rodar_receita
from sites import resolver_site, variavel_faltando

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import verify  # noqa: E402


class _Mem(KeyringBackend):
    priority = 1

    def __init__(self):
        self.d = {}

    def get_password(self, s, u):
        return self.d.get((s, u))

    def set_password(self, s, u, p):
        self.d[(s, u)] = p

    def delete_password(self, s, u):
        self.d.pop((s, u), None)


class PaginaMuda:
    def __init__(self):
        self.acoes = []

    def __getattr__(self, nome):
        def f(*a, **k):
            self.acoes.append(nome)
            return False
        return f


def test_conta_vem_do_ambiente(monkeypatch):
    monkeypatch.setenv("JARVIS_CONTA_MICROSOFT", "  fulano@example.com ")
    assert credenciais.usuario("microsoft-simpress") == "fulano@example.com"


def test_conta_faltando_da_erro_claro_e_nao_grava_senha(monkeypatch):
    monkeypatch.delenv("JARVIS_CONTA_MICROSOFT")
    with pytest.raises(credenciais.ContaNaoConfigurada, match="JARVIS_CONTA_MICROSOFT"):
        credenciais.usuario("microsoft-simpress")
    assert credenciais.usuario("microsoft-simpress", obrigatorio=False) == ""
    anterior = keyring.get_keyring()
    keyring.set_keyring(_Mem())
    try:
        with pytest.raises(credenciais.ContaNaoConfigurada):
            credenciais.salvar_senha("microsoft-simpress", "x")
    finally:
        keyring.set_keyring(anterior)


@pytest.mark.parametrize("site,variavel", [("dashboard", "JARVIS_URL_DASHBOARD"), ("softexpert", "JARVIS_CONTA_SOFTEXPERT")])
def test_receita_sem_variavel_falha_antes_de_mexer_na_pagina(monkeypatch, site, variavel):
    monkeypatch.delenv(variavel)
    p = PaginaMuda()
    r = rodar_receita(site, p, obter_senha=lambda c: "x")
    assert r["login"] == "falhou" and variavel in r["motivo"] and ".env" in r["motivo"]
    assert p.acoes == []


def test_receita_usa_a_conta_do_ambiente(monkeypatch):
    monkeypatch.setenv("JARVIS_CONTA_SOFTEXPERT", "soft@example.com")
    clicados, vistos = [], []

    hosts = ["outro.com", "outro.com", "sebraepr.softexpert.app"]

    class P(PaginaMuda):
        def host(self):
            return hosts.pop(0) if len(hosts) > 1 else hosts[0]

        def clicar_texto(self, t):
            clicados.append(t)
            return True

        def ir(self, url):
            vistos.append(url)

        def tem_texto(self, t):
            return False

    assert rodar_receita("softexpert", P(), dormir=lambda s: None)["login"] == "ok"
    assert vistos and clicados == ["SSO", "soft@example.com"]


def test_dashboard_sem_url_nao_abre_e_avisa(monkeypatch):
    monkeypatch.delenv("JARVIS_URL_DASHBOARD")
    assert resolver_site("dashboard") is None and variavel_faltando("o Dashboard") == "JARVIS_URL_DASHBOARD"
    abertos = []
    r = abrir_alvos(["dashboard"], lambda urls: abertos.extend(urls), abrir_programa=lambda p: None, pastas=[])
    assert abertos == [] and "JARVIS_URL_DASHBOARD" in r["resultados"][0]["erro"]


def test_dashboard_com_url_abre(monkeypatch):
    monkeypatch.setenv("JARVIS_URL_DASHBOARD", "https://exemplo.sharepoint.com/d")
    assert resolver_site("dashboard") == "https://exemplo.sharepoint.com/d" and variavel_faltando("dashboard") is None
    assert variavel_faltando("youtube") is None


def test_varredura_de_email_aceita_ficticio_e_recusa_real():
    def pessoal(linha):
        return any(not verify.DOMINIOS_FICTICIOS.search(m.group(1)) for m in verify.EMAIL.finditer(linha))

    assert not pessoal("a@example.com, b@sub.example.org, c@empresa.com, d@x.com, nada aqui")
    arroba = "@"  # montado aqui para a própria varredura não achar e-mail no teste
    assert pessoal("fulano" + arroba + "firma.com.br") and pessoal("x" + arroba + "exemplo.com.br") and pessoal("y" + arroba + "notexample.com")
