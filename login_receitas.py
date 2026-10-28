"""Receitas de login dos sites do catálogo.

A senha sai do Gerenciador de Credenciais direto para o campo, só se o host da aba estiver na lista da
credencial. Nunca entra no resultado nem em mensagem de erro. MFA, código e PIN são sempre do usuário:
a receita só espera o site final aparecer.
"""

import time
from typing import Dict, List, Protocol, Tuple

import credenciais
from sites import CATALOGO

Passo = Tuple[str, ...]  # ("esperar", host, texto_ausente) aceita o 3º elemento opcional

RECEITAS: Dict[str, List[Passo]] = {
    "dashboard": [
        ("ir", CATALOGO["dashboard"]["url"]),
        ("escolher_conta", "gansouza@simpress.com.br"),
        ("usuario", "microsoft-simpress"),
        ("senha", "microsoft-simpress"),
        ("clicar", "Sim"),  # tela "Continuar conectado?"
        ("esperar", "simpress-my.sharepoint.com"),
    ],
    "softexpert": [
        ("ir", CATALOGO["softexpert"]["url"]),
        ("clicar", "SSO"),
        ("escolher_conta", "gakihiro@pr.sebrae.com.br"),
        ("esperar", "sebraepr.softexpert.app", "SSO"),  # a tela de login já está no host final
    ],
}

SEM_SENHA = "Senha não cadastrada. Use ⚙ › Credenciais…"
FORA_DO_HOST = "Página fora dos endereços permitidos para esta senha."
ERRO_NAVEGADOR = "Erro no navegador durante o login."


class PaginaLogin(Protocol):
    def host(self) -> str: ...
    def ir(self, url: str) -> None: ...
    def clicar_texto(self, texto: str) -> bool: ...
    def tem_campo(self, tipo: str) -> bool: ...
    def tem_texto(self, texto: str) -> bool: ...
    def preencher(self, tipo: str, valor: str, hosts=None) -> None: ...


def rodar_receita(
    site: str,
    pagina: PaginaLogin,
    obter_senha=credenciais.senha,
    agora=time.monotonic,
    dormir=time.sleep,
    espera_mfa_s: float = 120,
    intervalo_s: float = 2,
) -> Dict:
    def falhou(motivo):
        return {"login": "falhou", "site": site, "motivo": motivo}

    passos = RECEITAS[site]
    _, host_final, *resto = passos[-1]
    texto_ausente = resto[0] if resto else None

    def chegou():
        return pagina.host() == host_final and not (texto_ausente and pagina.tem_texto(texto_ausente))

    try:
        for tipo, valor, *_ in passos:
            if tipo == "ir":
                pagina.ir(valor)
                if chegou():
                    return {"login": "ok", "site": site}
            elif tipo in ("clicar", "escolher_conta"):
                pagina.clicar_texto(valor)  # opcional: a tela pode não aparecer
            elif tipo == "usuario":
                if pagina.tem_campo("usuario"):
                    pagina.preencher("usuario", credenciais.CREDENCIAIS[valor]["usuario"])
            elif tipo == "senha":
                if not pagina.tem_campo("senha"):  # espera o campo; sem ele o passo "esperar" decide
                    continue
                senha = obter_senha(valor)
                if not senha:
                    return falhou(SEM_SENHA)
                # Host conferido logo antes de digitar: a aba pode ter mudado durante a espera.
                hosts = credenciais.CREDENCIAIS[valor]["hosts"]
                if pagina.host() not in hosts:
                    return falhou(FORA_DO_HOST)
                pagina.preencher("senha", senha, hosts=hosts)  # o adaptador confere o host de novo
            elif tipo == "esperar":
                inicio = agora()
                while not chegou():
                    if agora() - inicio >= espera_mfa_s:
                        return {"login": "aguardando_mfa", "site": site}
                    dormir(intervalo_s)
                return {"login": "ok", "site": site}
    except Exception:  # o texto da exceção pode conter a senha
        return falhou(ERRO_NAVEGADOR)
    return falhou(ERRO_NAVEGADOR)  # receita sem passo "esperar"
