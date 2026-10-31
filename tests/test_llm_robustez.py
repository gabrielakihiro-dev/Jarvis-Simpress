"""Memória limitada, erros amigáveis, retry e contrato do prompt do LLMClient (sem chamadas reais)."""
import json
import logging
from types import SimpleNamespace as NS

import httpx
import pytest
from openai import APIConnectionError, APITimeoutError, AuthenticationError, RateLimitError

import llm_client
from llm_client import SYSTEM_PROMPT, LLMClient
from tools.simpress_tools import TOOLS_SCHEMA

_REQ = httpx.Request("POST", "http://x")


def _resp(content=None):
    return NS(choices=[NS(message=NS(content=content, tool_calls=None))])


class FakeSimpress:
    base_url = "http://127.0.0.1:8000"

    def listar_nomes_usuarios(self):
        return []


class API:
    """Cada chamada consome um item: exceção é levantada, o resto é devolvido."""

    def __init__(self, *itens):
        self.itens, self.vistos, self.chamadas = list(itens), [], 0
        self.chat = NS(completions=NS(create=self.create))

    def create(self, **kw):
        self.chamadas += 1
        self.vistos.append(json.loads(json.dumps(kw["messages"], default=str)))
        item = self.itens.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def novo(*itens):
    llm = LLMClient(FakeSimpress())
    llm.client = API(*itens)
    return llm


def _turno(i):
    return [
        {"role": "user", "content": f"pergunta {i}"},
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": f"t{i}", "type": "function", "function": {"name": "obter_painel", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": f"t{i}", "name": "obter_painel", "content": "{}"},
        {"role": "assistant", "content": f"resposta {i}"},
    ]


def _integro(msgs):
    """system primeiro, user logo depois, e toda tool com a tool_call correspondente."""
    assert msgs[0]["role"] == "system" and msgs[1]["role"] == "user"
    chamadas = {tc["id"] for m in msgs if m.get("tool_calls") for tc in m["tool_calls"]}
    assert all(m["tool_call_id"] in chamadas for m in msgs if m["role"] == "tool")


# --- 1. memória limitada ---------------------------------------------------

def test_historico_passa_do_teto_de_mensagens_e_corta_turno_inteiro():
    llm = novo(_resp("ok"))
    for i in range(30):
        llm.mensagens += _turno(i)  # 120 mensagens
    llm.enviar_mensagem("nova")
    enviadas = llm.client.vistos[0]
    assert len(enviadas) - 2 <= llm_client.MAX_MENSAGENS_HISTORICO  # sem system e sem a pergunta nova
    _integro(enviadas)
    assert enviadas[1]["content"].startswith("pergunta ") and enviadas[-1]["content"] == "nova"
    assert enviadas[-2]["content"] == "resposta 29"  # o mais recente fica


def test_historico_passa_do_teto_de_caracteres(monkeypatch):
    monkeypatch.setattr(llm_client, "MAX_CARACTERES_HISTORICO", 600)
    llm = novo(_resp("ok"))
    for i in range(10):
        llm.mensagens += _turno(i)
    llm.enviar_mensagem("nova")
    enviadas = llm.client.vistos[0]
    assert len(enviadas) < 42
    _integro(enviadas)


def test_historico_pequeno_nao_e_cortado():
    llm = novo(_resp("ok"))
    llm.mensagens += _turno(0) + _turno(1)
    llm.enviar_mensagem("nova")
    assert len(llm.client.vistos[0]) == 1 + 8 + 1


def test_lembrete_da_promessa_nao_e_ponto_de_corte(monkeypatch):
    monkeypatch.setattr(llm_client, "MAX_MENSAGENS_HISTORICO", 2)
    llm = novo()
    sistema = llm.mensagens[0]
    llm.mensagens = [sistema, {"role": "user", "content": "A"}, {"role": "assistant", "content": "Vou ver"},
                     {"role": "user", "content": llm_client.LEMBRETE_FERRAMENTA}, {"role": "assistant", "content": "ok"}]
    llm._aparar_historico()
    assert len(llm.mensagens) == 5  # um turno só: nada a cortar
    llm.mensagens += [{"role": "user", "content": "B"}, {"role": "assistant", "content": "ok"}]
    llm._aparar_historico()
    assert [m["content"] for m in llm.mensagens[1:]] == ["B", "ok"]


def test_marcador_de_turno_cortado_continua_valendo_na_tela():
    llm = novo(_resp("Fale com [PESSOA_1]."))
    assert llm.mascara.mascarar({"usuario": "Joana Lima"}) == {"usuario": "[PESSOA_1]"}
    for i in range(30):
        llm.mensagens += _turno(i)
    r = llm.enviar_mensagem("quem?")
    assert r.texto == "Fale com Joana Lima."


def test_limpar_historico_zera():
    llm = novo()
    llm.mensagens += _turno(0)
    llm.limpar_historico()
    assert len(llm.mensagens) == 1 and llm.mensagens[0]["role"] == "system"


# --- 2. erros --------------------------------------------------------------

def test_erro_da_api_vira_mensagem_amigavel_e_log_sem_segredo(caplog):
    segredo = "sk-or-v1-abcdef1234567890 joana@empresa.com"
    llm = novo(RuntimeError(f"falha com a chave {segredo}"))
    antes = len(llm.mensagens)
    with caplog.at_level(logging.ERROR, logger="llm_client"):
        r = llm.enviar_mensagem("oi")
    assert "chave" not in r.texto and "RuntimeError" not in r.texto and "OpenRouter" in r.texto
    assert len(llm.mensagens) == antes
    assert "RuntimeError" in caplog.text
    assert "abcdef1234567890" not in caplog.text and "joana@empresa.com" not in caplog.text


def test_chave_recusada_orienta_a_conferir_o_env():
    erro = AuthenticationError("401", response=httpx.Response(401, request=_REQ), body=None)
    r = novo(erro).enviar_mensagem("oi")
    assert ".env" in r.texto


def test_excecao_de_ferramenta_vai_curta_e_sanitizada(caplog):
    llm = novo()

    def explode(nome, args):
        raise RuntimeError("falha senha: Abc@123 de joana@empresa.com " + "x" * 500)

    llm.toolbox.execute = explode
    with caplog.at_level(logging.ERROR, logger="llm_client"):
        r = llm.executar_ferramenta("obter_painel", {})
    assert "RuntimeError" in r["erro"] and len(r["erro"]) < 300
    assert "Abc@123" not in r["erro"] and "joana@empresa.com" not in r["erro"]
    assert "Abc@123" not in caplog.text


# --- 2d. retry -------------------------------------------------------------

def _limite():
    return RateLimitError("429", response=httpx.Response(429, request=_REQ), body=None)


@pytest.fixture
def esperas(monkeypatch):
    registro = []
    monkeypatch.setattr(llm_client.time, "sleep", registro.append)
    return registro


def test_erro_transitorio_tenta_de_novo_e_recupera(esperas):
    llm = novo(_limite(), _resp("deu"))
    r = llm.enviar_mensagem("oi")
    assert r.texto == "deu" and llm.client.chamadas == 2 and esperas == [1]


def test_rede_cai_duas_vezes_espera_1s_e_2s(esperas):
    llm = novo(APIConnectionError(request=_REQ), APIConnectionError(request=_REQ), _resp("deu"))
    assert llm.enviar_mensagem("oi").texto == "deu"
    assert esperas == [1, 2]


def test_erro_nao_transitorio_nao_repete(esperas):
    llm = novo(RuntimeError("bug"))
    llm.enviar_mensagem("oi")
    assert llm.client.chamadas == 1 and esperas == []


def test_timeout_nao_repete(esperas):
    llm = novo(APITimeoutError(request=_REQ))
    r = llm.enviar_mensagem("oi")
    assert llm.client.chamadas == 1 and esperas == [] and "demorou" in r.texto


def test_falha_sempre_para_em_3_chamadas_e_desfaz_historico(esperas):
    llm = novo(_limite(), _limite(), _limite(), _limite())
    antes = len(llm.mensagens)
    r = llm.enviar_mensagem("oi")
    assert llm.client.chamadas == 3 and esperas == [1, 2]
    assert "limitando" in r.texto and len(llm.mensagens) == antes


def test_cliente_sdk_sem_retry_proprio():
    assert LLMClient._criar_cliente("k").max_retries == 0
    assert LLMClient._criar_cliente("k", deepseek=True).max_retries == 0


# --- 3. contrato do prompt -------------------------------------------------

def test_prompt_mantem_regras_essenciais():
    for trecho in (
        "PERGUNTA NÃO É ORDEM",
        "não peça confirmação por texto",   # o cartão é do programa
        "Faça uma alteração por vez",
        "nunca pede, lê nem repete senhas",
        "DADO PASSIVO",
        "PROMPT INJECTION",
        "Nunca responda só",
        "[PESSOA_1]",
    ):
        assert trecho in SYSTEM_PROMPT, trecho


def _descricoes():
    return {t["function"]["name"]: t["function"]["description"] for t in TOOLS_SCHEMA}


def test_regras_de_apresentacao_moraram_para_as_descricoes_das_tools():
    d = _descricoes()
    assert "hostname" in d["listar_transferencias"]
    for campo in ("transferencias_relacionadas", "aviso_transferencias", "itens"):
        assert campo in d["listar_divergencias_localidade"]
    assert "listar_transferencias" in d["listar_divergencias_localidade"]
    assert "apelidos_sem_atualizacao" in d["consultar_ultima_comparacao"]
    assert "usuario_anterior" in d["listar_secao_comparacao"] and "total" in d["listar_secao_comparacao"]
    assert "transferência" in d["consultar_divergencia_localidade"]
    assert "transferencias_relacionadas" not in SYSTEM_PROMPT
