import json
from datetime import datetime

import pytest

import importacao
from tools.simpress_tools import MUTADORAS, descrever_acao


@pytest.fixture
def raiz(tmp_path):
    entrada = importacao.pasta_entrada(tmp_path)
    for p in ("modelo_lote/endpoint", "modelo_lote/simpress", "pendentes", "processadas", "falhas"):
        (entrada / p).mkdir(parents=True)
    (entrada / "modelo_lote/endpoint/.gitkeep").write_text("")
    for nome in ("end.xlsx", "simp.xlsx"):
        (tmp_path / nome).write_bytes(b"PK")
    return tmp_path


def test_cria_lote_com_um_xlsx_por_papel(raiz):
    nome = importacao.criar_lote(raiz / "end.xlsx", raiz / "simp.xlsx", raiz, datetime(2026, 10, 27, 9, 5, 1))
    lote = importacao.pasta_entrada(raiz) / "pendentes" / nome
    assert nome == "jarvis_20261027_090501"
    assert (lote / "endpoint" / "end.xlsx").is_file() and (lote / "simpress" / "simp.xlsx").is_file()
    assert not list(importacao.pasta_entrada(raiz).glob(".montando_*"))


def test_nao_sobrescreve_lote_existente(raiz):
    agora = datetime(2026, 10, 27, 9, 5, 1)
    importacao.criar_lote(raiz / "end.xlsx", raiz / "simp.xlsx", raiz, agora)
    with pytest.raises(FileExistsError):
        importacao.criar_lote(raiz / "end.xlsx", raiz / "simp.xlsx", raiz, agora)


def test_recusa_arquivo_que_nao_e_xlsx(raiz):
    (raiz / "a.csv").write_text("x")
    with pytest.raises(ValueError):
        importacao.criar_lote(raiz / "a.csv", raiz / "simp.xlsx", raiz)


def test_resultado_le_recibo_inclusive_com_sufixo(raiz):
    entrada = importacao.pasta_entrada(raiz)
    assert importacao.resultado_lote("jarvis_1", raiz) is None
    (entrada / "falhas" / "jarvis_1--ab12").mkdir()
    (entrada / "falhas" / "jarvis_1--ab12" / "_resultado.json").write_text(json.dumps({"status": "falha", "detalhe": "x"}))
    (entrada / "processadas" / "jarvis_10").mkdir()  # outro lote com prefixo parecido
    assert importacao.resultado_lote("jarvis_1", raiz)["status"] == "falha"


def test_cartao_de_unidade_lista_todos_os_campos():
    assert "salvar_unidade" in MUTADORAS
    txt = descrever_acao("salvar_unidade", {"id": 3, "cidade": "Londrina", "endereco": "Rua A", "cep": "86000-000", "cnpj": "9"})
    assert txt == "Editar a unidade #3: cidade Londrina, endereço Rua A, UF PR, CEP 86000-000, CNPJ 9."
    assert descrever_acao("salvar_unidade", {"cidade": "X", "endereco": "Y", "cnpj": "1"}).startswith("Criar nova unidade")
