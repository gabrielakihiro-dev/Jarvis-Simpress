import json
from types import SimpleNamespace as NS

from llm_client import LLMClient


class FakeSimpress:
    base_url = "http://127.0.0.1:8000"

    def __init__(self):
        self.chamadas = []

    def atualizar_apelido(self, serial, apelido):
        self.chamadas.append(("apelido", serial, apelido))
        return {"sucesso": True}

    def consultar_equipamento(self, serial):
        return {"encontrado": True, "equipamento": {"serial": serial, "usuario_logado": "Maria Souza"}}


def _tc(i, nome, args):
    return NS(id=i, function=NS(name=nome, arguments=json.dumps(args)))


def _resp(content=None, tool_calls=None):
    return NS(choices=[NS(message=NS(content=content, tool_calls=tool_calls))])


class FakeAPI:
    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.vistos = []
        self.chat = NS(completions=NS(create=self.create))

    def create(self, **kw):
        self.vistos.append(json.loads(json.dumps(kw["messages"], default=str)))
        return self.respostas.pop(0)


def novo(respostas):
    llm = LLMClient(FakeSimpress())
    llm.client = FakeAPI(respostas)
    return llm


def test_alteracao_para_no_cartao_e_so_executa_ao_confirmar():
    llm = novo([
        _resp(tool_calls=[_tc("t1", "atualizar_apelido", {"serial": "ABC1", "apelido": "Recepção"})]),
        _resp(content="Pronto."),
    ])
    r = llm.enviar_mensagem("mude o apelido")
    assert r.pendente and "ABC1" in r.pendente["descricao"]
    assert llm.simpress.chamadas == []

    r2 = llm.resolver_confirmacao(True)
    assert llm.simpress.chamadas == [("apelido", "ABC1", "Recepção")]
    assert r2.texto == "Pronto."
    # toda tool_call tem resposta role=tool antes da chamada seguinte à API
    ultimo = llm.client.vistos[-1]
    assert any(m.get("role") == "tool" and m["tool_call_id"] == "t1" for m in ultimo)


def test_cancelar_nao_executa_e_responde_a_tool_call():
    llm = novo([
        _resp(tool_calls=[_tc("t1", "atualizar_apelido", {"serial": "ABC1", "apelido": "X"})]),
        _resp(content="Cancelado."),
    ])
    llm.enviar_mensagem("mude")
    llm.resolver_confirmacao(False)
    assert llm.simpress.chamadas == []
    tools = [m for m in llm.client.vistos[-1] if m.get("role") == "tool"]
    assert len(tools) == 1 and "cancelou" in tools[0]["content"]


def test_duas_alteracoes_no_mesmo_turno_so_a_primeira_vira_cartao():
    llm = novo([
        _resp(tool_calls=[
            _tc("t1", "atualizar_apelido", {"serial": "A", "apelido": "1"}),
            _tc("t2", "atualizar_apelido", {"serial": "B", "apelido": "2"}),
        ]),
        _resp(content="ok"),
    ])
    r = llm.enviar_mensagem("mude dois")
    assert r.pendente["args"]["serial"] == "A"
    llm.resolver_confirmacao(False)
    tools = {m["tool_call_id"]: m["content"] for m in llm.client.vistos[-1] if m.get("role") == "tool"}
    assert set(tools) == {"t1", "t2"} and "Uma alteração por vez" in tools["t2"]


def test_usuario_nunca_vai_ao_modelo_mas_aparece_na_tela():
    llm = novo([
        _resp(tool_calls=[_tc("t1", "consultar_equipamento", {"serial": "ABC1"})]),
        _resp(content="O usuário é [PESSOA_1]."),
    ])
    r = llm.enviar_mensagem("quem usa ABC1?")
    enviado = json.dumps(llm.client.vistos[-1])
    assert "Maria" not in enviado
    assert r.texto == "O usuário é Maria Souza."
    assert "Maria" not in r.texto_voz and "uma pessoa" in r.texto_voz


def test_erro_da_api_desfaz_mensagem_do_usuario():
    llm = novo([])
    llm.client.create = lambda **kw: (_ for _ in ()).throw(RuntimeError("falhou"))
    llm.client.chat = NS(completions=NS(create=llm.client.create))
    antes = len(llm.mensagens)
    r = llm.enviar_mensagem("oi")
    assert "falhou" in r.texto and len(llm.mensagens) == antes
