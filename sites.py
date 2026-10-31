"""Catálogo de sites que o Jarvis sabe abrir pelo nome."""

import os
import re
import unicodedata
from typing import Any, Dict, Optional
from urllib.parse import urlparse

CATALOGO: Dict[str, Dict[str, Any]] = {
    "youtube": {"nome": "YouTube", "url": "https://www.youtube.com", "apelidos": ["youtube"]},
    "endpoint": {
        "nome": "Endpoint Central",
        "url": "https://centralendpoint.pr.sebrae.com.br/webclient#/uems/inventory/computers",
        "apelidos": ["endpoint", "endpoint central", "central endpoint"],
    },
    "ux": {"nome": "UX Simpress", "url": "https://ux.simpress.com.br/MeusEquipamentos/Index", "apelidos": ["ux", "ux simpress"]},
    "dashboard": {
        "nome": "Dashboard (Operacional_SEBRAE)",
        "url_env": "JARVIS_URL_DASHBOARD",  # link pessoal do SharePoint: fica no .env, não no código
        "apelidos": ["dashboard", "operacional sebrae"],
    },
    "softexpert": {
        "nome": "SoftExpert",
        "url": "https://sebraepr.softexpert.app/softexpert/workspace?page=taskCenter",
        "apelidos": ["softexpert", "soft expert"],
    },
}


def normalizar(texto: str) -> str:
    """Sem acento, minúsculo, espaços colapsados e sem artigo (o/a/os/as) no início."""
    sem_acento = "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))
    limpo = re.sub(r"\s+", " ", sem_acento.lower()).strip()
    return re.sub(r"^(os|as|o|a) ", "", limpo)


def url_do_site(item: Dict[str, Any]) -> str:
    """URL do item do catálogo; vazia se vem de uma variável de ambiente que não foi preenchida."""
    return item.get("url") or os.environ.get(item.get("url_env", ""), "").strip()


def variavel_faltando(alvo: str) -> Optional[str]:
    """Nome da variável do .env que falta para abrir este site do catálogo (None se não falta nada)."""
    chave = normalizar(alvo.strip())
    for item in CATALOGO.values():
        if chave in item["apelidos"] and not url_do_site(item):
            return item["url_env"]
    return None


def resolver_site(alvo: str) -> Optional[str]:
    """Apelido do catálogo -> URL; http(s) com host -> o próprio alvo; o resto -> None."""
    bruto = alvo.strip()
    if bruto.lower().startswith(("http://", "https://")):
        return bruto if urlparse(bruto).hostname else None
    chave = normalizar(bruto)
    for item in CATALOGO.values():
        if chave in item["apelidos"]:
            return url_do_site(item) or None
    return None
