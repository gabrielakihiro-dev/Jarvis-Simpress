"""Lote de importação de inventários pela pasta oficial do Simpress.

Segue o README de `data/state/entrada_automatica`: copia `modelo_lote` com um
.xlsx em `endpoint/` e outro em `simpress/`. O lote é montado numa pasta
temporária ao lado de `pendentes/` e entra lá de uma vez (renomeação), para o
importador nunca ver um lote copiado pela metade.
"""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

SIMPRESS_DIR = Path(os.environ.get("SIMPRESS_DIR") or Path(__file__).resolve().parent.parent / "Simpress")


def pasta_entrada(raiz: Optional[Path] = None) -> Path:
    return Path(raiz or SIMPRESS_DIR) / "data" / "state" / "entrada_automatica"


def criar_lote(endpoint: str, simpress: str, raiz: Optional[Path] = None, agora: Optional[datetime] = None) -> str:
    """Publica o par de planilhas em `pendentes/jarvis_<data>_<hora>`. Devolve o nome do lote."""
    arquivos = {"endpoint": Path(endpoint), "simpress": Path(simpress)}
    for papel, arq in arquivos.items():
        if not arq.is_file() or arq.suffix.lower() != ".xlsx":
            raise ValueError(f"A planilha de {papel} precisa ser um arquivo .xlsx existente.")
    entrada = pasta_entrada(raiz)
    modelo, pendentes = entrada / "modelo_lote", entrada / "pendentes"
    if not modelo.is_dir() or not pendentes.is_dir():
        raise FileNotFoundError(f"Pasta de entrada do Simpress não encontrada em {entrada}.")
    nome = f"jarvis_{(agora or datetime.now()):%Y%m%d_%H%M%S}"
    destino, temporaria = pendentes / nome, entrada / f".montando_{nome}"
    if destino.exists() or temporaria.exists() or resultado_lote(nome, raiz) is not None:
        raise FileExistsError(f"Já existe um lote chamado {nome}. Tente de novo em 1 segundo.")
    shutil.copytree(modelo, temporaria)
    try:
        for papel, arq in arquivos.items():
            shutil.copy2(arq, temporaria / papel / arq.name)
        os.rename(temporaria, destino)  # no Windows falha se o destino já existir
    except Exception:
        shutil.rmtree(temporaria, ignore_errors=True)  # só a pasta temporária que este código criou
        raise
    return nome


def resultado_lote(nome: str, raiz: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Recibo `_resultado.json` do lote em `processadas/` ou `falhas/`; None enquanto não terminou."""
    entrada = pasta_entrada(raiz)
    for pasta in ("processadas", "falhas"):
        # o importador acrescenta `--<sufixo>` ao nome se ele já existir no destino
        for d in sorted((entrada / pasta).glob(f"{nome}*")):
            if d.name != nome and not d.name.startswith(f"{nome}--"):
                continue
            recibo = d / "_resultado.json"
            if recibo.is_file():
                try:
                    return json.loads(recibo.read_text(encoding="utf-8"))
                except ValueError:
                    return {"status": "falha", "detalhe": "Recibo ilegível."}
    return None
