"""Catálogo de sites que o Jarvis sabe abrir pelo nome."""

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
        "url": "https://simpress-my.sharepoint.com/:x:/r/personal/jufsouza_simpress_com_br/_layouts/15/doc2.aspx?sourcedoc=%7Bbe6cb02e-6528-45f0-a4ca-224923818e90%7D&action=edit",
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


def resolver_site(alvo: str) -> Optional[str]:
    """Apelido do catálogo -> URL; http(s) com host -> o próprio alvo; o resto -> None."""
    bruto = alvo.strip()
    if bruto.lower().startswith(("http://", "https://")):
        return bruto if urlparse(bruto).hostname else None
    chave = normalizar(bruto)
    for item in CATALOGO.values():
        if chave in item["apelidos"]:
            return item["url"]
    return None
