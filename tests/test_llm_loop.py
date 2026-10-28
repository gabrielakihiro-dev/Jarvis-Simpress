import json
from types import SimpleNamespace as NS

from llm_client import LLMClient


class FakeSimpress:
    base_url = "http://127.0.0.1:8000"

    def __init__(self, nomes=None):
        self.chamadas = []
        self.nomes = nomes
        self.buscas_de_nomes = 0

    def listar_nomes_usuarios(self):
        self.buscas_de_nomes += 1
        return self.nomes

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
    assert r.texto_voz == "O usuário é Maria Souza."


def test_voz_troca_marcador_inventado_por_uma_pessoa():
    llm = novo([_resp(content="Fale com [PESSOA_9].")])
    r = llm.enviar_mensagem("oi")
    assert r.texto == "Fale com [PESSOA_9]." and r.texto_voz == "Fale com uma pessoa."


def test_erro_da_api_desfaz_mensagem_do_usuario():
    llm = novo([])
    llm.client.create = lambda **kw: (_ for _ in ()).throw(RuntimeError("falhou"))
    llm.client.chat = NS(completions=NS(create=llm.client.create))
    antes = len(llm.mensagens)
    r = llm.enviar_mensagem("oi")
    assert "falhou" in r.texto and len(llm.mensagens) == antes


def test_resposta_grande_e_cortada_depois_da_mascara():
    llm = novo([])
    itens = [{"usuario": f"Pessoa Numero {i}", "serie": f"S{i:04d}", "modelo": "x" * 200} for i in range(40)]
    msg = llm._msg_tool("t1", "pesquisar_catalogo", {"dados": {"itens": itens}})
    assert "trecho" in msg["content"]
    assert "Pessoa Numero" not in msg["content"]


def test_divergencias_localidade_manda_itens_pro_modelo():
    llm = novo([])
    resultado = {"total": 6, "itens": [{"serie": "BRJ1", "computador": "PC1"}], "aviso_transferencias": "x"}
    msg = llm._msg_tool("t1", "listar_divergencias_localidade", resultado)
    assert "BRJ1" in msg["content"] and '"total": 6' in msg["content"] and "x" in msg["content"]


def test_nome_da_base_digitado_vai_mascarado_e_volta_na_tela():
    llm = LLMClient(FakeSimpress(nomes=["Joana Lima", "TI"]))
    llm.client = FakeAPI([_resp(content="[PESSOA_1] está no notebook X.")])
    r = llm.enviar_mensagem("onde está joana lima? fale com TI")
    enviado = json.dumps(llm.client.vistos[0], ensure_ascii=False)
    assert "Joana" not in enviado and "joana" not in enviado and "[PESSOA_1]" in enviado
    assert "fale com TI" in enviado  # nome curto da base não é mascarado
    assert "Joana Lima" in r.texto


def test_base_offline_tenta_de_novo_na_proxima_mensagem():
    simpress = FakeSimpress(nomes=None)
    llm = LLMClient(simpress)
    llm.client = FakeAPI([_resp(content="ok"), _resp(content="ok"), _resp(content="ok")])
    llm.enviar_mensagem("oi")
    simpress.nomes = ["Joana Lima"]
    llm.enviar_mensagem("e a Joana Lima?")
    llm.enviar_mensagem("de novo")
    assert simpress.buscas_de_nomes == 2
    assert "Joana" not in json.dumps(llm.client.vistos[1], ensure_ascii=False)


def test_cpf_e_senha_digitados_nao_vao_para_a_ia():
    llm = novo([_resp(content="Ok.")])
    llm.enviar_mensagem("CPF 123.456.789-00, senha: Abc@123")
    enviado = llm.client.vistos[0][-1]["content"]
    assert "123.456.789-00" not in enviado and "Abc@123" not in enviado
    assert "***.***.***-**" in enviado
