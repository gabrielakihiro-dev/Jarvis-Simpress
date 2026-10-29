import http.client
import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from servidor_leve import criar_servidor

RAIZ = Path(__file__).resolve().parent.parent


class LLMFalso:
    """Imita o LLMClient: "altere" deixa uma alteração pendente, como o cartão de confirmação."""

    modelo_principal = "modelo/teste"

    def __init__(self):
        self.pendente = None
        self.limpou = False

    @property
    def aguardando_confirmacao(self):
        return self.pendente is not None

    @property
    def descricao_pendente(self):
        return self.pendente["descricao"] if self.pendente else None

    def enviar_mensagem(self, texto, callback_status=None):
        if texto.startswith("altere"):
            self.pendente = {"tool_call_id": "call_1", "nome": "atualizar_apelido",
                             "args": {"serial": "ABC1", "apelido": "Sala"},
                             "descricao": "Alterar o apelido do serial ABC1 para 'Sala'."}
            return SimpleNamespace(texto=self.pendente["descricao"], ferramentas=["atualizar_apelido"],
                                   pendente=dict(self.pendente))
        return SimpleNamespace(texto=f"eco: {texto}", ferramentas=["obter_painel"], pendente=None)

    def resolver_confirmacao(self, confirmado, callback_status=None):
        self.pendente = None
        return SimpleNamespace(texto="Feito." if confirmado else "Cancelado.", ferramentas=["atualizar_apelido"], pendente=None)

    def limpar_historico(self):
        self.limpou = True


@pytest.fixture
def servidor():
    llm = LLMFalso()
    srv = criar_servidor(llm, 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv, llm
    srv.shutdown()
    srv.server_close()


def chamar(srv, metodo, caminho, corpo=None, cabecalhos=None):
    porta = srv.server_address[1]
    con = http.client.HTTPConnection("127.0.0.1", porta, timeout=5)
    dados = corpo if isinstance(corpo, (bytes, type(None))) else json.dumps(corpo).encode()
    h = {"Content-Type": "application/json"} if dados is not None else {}
    h.update(cabecalhos or {})
    con.request(metodo, caminho, body=dados, headers=h)
    r = con.getresponse()
    status, resp = r.status, json.loads(r.read())
    con.close()
    return status, resp


def test_mensagem(servidor):
    srv, _ = servidor
    assert chamar(srv, "POST", "/mensagem", {"texto": "oi"}) ==         (200, {"texto": "eco: oi", "ferramentas": ["obter_painel"], "pendente": None})


def test_mensagem_com_cartao_aberto_devolve_o_cartao(servidor):
    srv, _ = servidor
    chamar(srv, "POST", "/mensagem", {"texto": "altere o apelido"})
    status, r = chamar(srv, "POST", "/mensagem", {"texto": "oi"})
    assert status == 200
    assert r["pendente"] == {"descricao": "Alterar o apelido do serial ABC1 para 'Sala'."}


def test_pendente_e_confirmar_sem_vazar_argumentos(servidor):
    srv, llm = servidor
    status, r = chamar(srv, "POST", "/mensagem", {"texto": "altere o apelido"})
    assert status == 200
    assert r["pendente"] == {"descricao": "Alterar o apelido do serial ABC1 para 'Sala'."}
    estado = chamar(srv, "GET", "/estado")[1]
    assert estado["aguardando_confirmacao"] is True
    assert estado["pendente"] == {"descricao": "Alterar o apelido do serial ABC1 para 'Sala'."}
    assert chamar(srv, "POST", "/confirmar", {"confirmado": True}) ==         (200, {"texto": "Feito.", "ferramentas": ["atualizar_apelido"], "pendente": None})
    assert llm.pendente is None


def test_pendente_e_cancelar(servidor):
    srv, _ = servidor
    chamar(srv, "POST", "/mensagem", {"texto": "altere"})
    assert chamar(srv, "POST", "/confirmar", {"confirmado": False})[1]["texto"] == "Cancelado."


def test_estado_e_limpar(servidor):
    srv, llm = servidor
    assert chamar(srv, "GET", "/estado") ==         (200, {"online": True, "modelo": "modelo/teste", "aguardando_confirmacao": False, "pendente": None})
    assert chamar(srv, "POST", "/limpar") == (200, {"ok": True}) and llm.limpou


@pytest.mark.parametrize("cabecalho", [{"Origin": "http://127.0.0.1:8000"}, {"Sec-Fetch-Site": "same-origin"},
                                       {"Host": "evil.example:8766"}])
def test_recusa_navegador_e_host_estranho(servidor, cabecalho):
    srv, _ = servidor
    assert chamar(srv, "GET", "/estado", cabecalhos=cabecalho)[0] == 403
    assert chamar(srv, "POST", "/mensagem", {"texto": "oi"}, cabecalho)[0] == 403


def test_corpo_grande_413(servidor):
    srv, _ = servidor
    status, r = chamar(srv, "POST", "/mensagem", {"texto": "x" * 20000})
    assert status == 413 and "detail" in r


@pytest.mark.parametrize("corpo", [{}, {"texto": ""}, {"texto": "   "}, {"texto": 5}, {"texto": "x" * 4001}, [1]])
def test_mensagem_invalida_422(servidor, corpo):
    srv, _ = servidor
    assert chamar(srv, "POST", "/mensagem", corpo)[0] == 422


def test_confirmar_exige_booleano(servidor):
    srv, _ = servidor
    assert chamar(srv, "POST", "/confirmar", {"confirmado": 1})[0] == 422


def test_json_invalido_content_type_rota_e_metodo(servidor):
    srv, _ = servidor
    assert chamar(srv, "POST", "/mensagem", b"{oi")[0] == 400
    assert chamar(srv, "POST", "/mensagem", b'{"texto": "oi"}', {"Content-Type": "text/plain"})[0] == 400
    assert chamar(srv, "GET", "/nada")[0] == 404
    assert chamar(srv, "GET", "/mensagem")[0] == 405
    assert chamar(srv, "DELETE", "/estado")[0] == 405


def test_erro_inesperado_vira_500_generico(servidor):
    srv, llm = servidor

    def explode(*a, **k):
        raise RuntimeError("segredo interno")

    llm.enviar_mensagem = explode
    status, r = chamar(srv, "POST", "/mensagem", {"texto": "oi"})
    assert status == 500 and "segredo" not in r["detail"]


def test_modo_leve_sem_navegador_pc_nem_keyring():
    # Subprocesso: o catálogo é montado na importação e não pode vazar para o resto da suíte.
    codigo = "\n".join([
        "import sys, llm_client",
        "from tools.simpress_tools import NOMES_FERRAMENTAS as n",
        "assert not n & {'navegar', 'abrir', 'logar_site', 'clicar'}, n",
        "assert {'consultar_equipamento', 'atualizar_apelido'} <= n",
        "assert 'MODO LEVE' in llm_client.SYSTEM_PROMPT",
        "assert not {'keyring', 'navegador_jarvis', 'PyQt6'} & set(sys.modules)",
    ])
    r = subprocess.run([sys.executable, "-c", codigo], cwd=RAIZ, capture_output=True, text=True,
                       env={**os.environ, "JARVIS_MODO_LEVE": "1"})
    assert r.returncode == 0, r.stderr
