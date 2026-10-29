import json

import httpx

import simpress_client
from actions import carregar
from lgpd import Mascara
from simpress_client import SimpressClient
from tools.simpress_tools import MUTADORAS, SimpressToolbox
from ui.cartoes import cartao_html

NOVAS = {
    "chamados_novos_sebrae", "chamados_antigos_abertos_sebrae", "estado_usuarios_entra", "listar_historico_alteracoes",
    "listar_apelidos_modificados", "evolucao_atualizacoes", "log_execucao_automacao",
}


def cliente(rotas):
    """`rotas`: caminho -> corpo JSON (ou função da requisição). Guarda as requisições em `.vistas`."""
    vistas = []

    def handler(req):
        vistas.append(req)
        corpo = rotas[req.url.path]
        return httpx.Response(200, json=corpo(req) if callable(corpo) else corpo)

    c = SimpressClient(base_url="http://127.0.0.1:8000", transport=httpx.MockTransport(handler))
    c.vistas = vistas
    return c


def test_ferramentas_novas_registradas_de_leitura_com_schema_valido():
    todas = carregar()
    assert NOVAS <= set(todas)
    assert not NOVAS & MUTADORAS
    for nome in NOVAS:
        item = todas[nome]
        fn = item["schema"]["function"]
        assert item["altera_dados"] is False and callable(item["executar"])
        assert fn["name"] == nome and fn["description"] and fn["parameters"]["type"] == "object"
        assert set(fn["parameters"].get("required", [])) <= set(fn["parameters"]["properties"])


def test_toolbox_despacha_as_novas_ferramentas():
    c = cliente({"/api/usuarios-entra/estado": {"updated_at": "2026-10-27", "users": 3}})
    assert SimpressToolbox(c).execute("estado_usuarios_entra", {})["dados"]["users"] == 3


SEBRAE = {
    "importado": {"arquivo": "dash.xlsx", "importado_em": "2026-10-27", "total": 100},
    "novos": {
        "lidos_em": "2026-10-28T08:00", "ignorados": 2,
        "pendentes": [{"numero": "N9", "motivo": "falta detalhe ana@x.com"}],
        "erros": {"N8": "falhou"},
        "formulario": [{
            "numero": f"N{i}",
            "linha": {"C": f"N{i}", "F": "ok", "G": "Notebook lento", "H": "Fulano 111.444.777-35 " + "x" * 500,
                      "I": "Maria Souza", "K": "BRJ1", "L": "HP", "N": "Curitiba", "P": "27/10/2026"},
            "cruzamento": {"status": "unico", "candidatos": 1},
        } for i in range(25)],
    },
}


def test_chamados_novos_sebrae_enxuga_limpa_e_nomeia_solicitante():
    c = cliente({"/api/sebrae/novos": SEBRAE})
    res = c.chamados_novos_sebrae()
    assert res["total_novos"] == 25 and len(res["chamados"]) == simpress_client.MAX_ITENS_LISTA and res["omitidos"] == 5
    ch = res["chamados"][0]
    assert ch["solicitante"] == "Maria Souza" and ch["serie"] == "BRJ1" and ch["cruzamento"] == "unico"
    assert len(ch["descricao"]) <= simpress_client.MAX_TEXTO_CHAMADO and "111.444.777-35" not in ch["descricao"]
    assert res["pendentes"] == [{"numero": "N9", "motivo": "falta detalhe [E-MAIL OCULTADO]"}]
    assert res["erros"] == [{"numero": "N8", "erro": "falhou"}]
    assert [r.method for r in c.vistas] == ["GET"]
    # a chave "solicitante" é sensível: a máscara troca o nome por marcador
    assert "Maria Souza" not in json.dumps(Mascara().mascarar(res))


def test_chamados_novos_sebrae_sem_leitura_e_erro_http():
    res = cliente({"/api/sebrae/novos": {"importado": None, "novos": None}}).chamados_novos_sebrae()
    assert res["dashboard_importado"] is False and "Ainda não" in res["mensagem"]
    c = SimpressClient(base_url="http://x", transport=httpx.MockTransport(lambda r: httpx.Response(500, json={"detail": "ruim"})))
    assert "500" in c.chamados_novos_sebrae()["erro"]


def test_chamados_antigos_abertos_sebrae_lista_inclusive_composto_e_limpa_texto():
    abertos = [{"numero": f"UTIC-2026-{i:04d}", "titulo": "Fulano 111.444.777-35 " + "x" * 500,
                "valores": {"A": "" if i else "Ana", "B": "", "D": "EM ABERTO", "J": "INCIDENTE"}} for i in range(25)]
    c = cliente({"/api/sebrae/novos": {"importado": {"arquivo": "d.xlsx", "importado_em": "h", "total": 9, "abertos": abertos}, "novos": None}})
    res = c.chamados_antigos_abertos_sebrae()
    assert res["total_abertos"] == 25 and len(res["abertos"]) == simpress_client.MAX_ITENS_LISTA and res["omitidos"] == 25 - simpress_client.MAX_ITENS_LISTA
    assert res["sem_responsavel"] == 24 and res["abertos"][0]["responsavel"] == "Ana" and res["abertos"][1]["status"] == "EM ABERTO"
    assert len(res["abertos"][0]["titulo"]) <= simpress_client.MAX_TEXTO_CHAMADO and "111.444.777-35" not in res["abertos"][0]["titulo"]
    assert [r.method for r in c.vistas] == ["GET"]


def test_chamados_antigos_abertos_sebrae_sem_dashboard_e_erro_http():
    res = cliente({"/api/sebrae/novos": {"importado": None, "novos": None}}).chamados_antigos_abertos_sebrae()
    assert res["dashboard_importado"] is False and "Ainda não" in res["mensagem"]
    c = SimpressClient(base_url="http://x", transport=httpx.MockTransport(lambda r: httpx.Response(500, json={"detail": "ruim"})))
    assert "500" in c.chamados_antigos_abertos_sebrae()["erro"]


def test_historico_alteracoes_limita_e_mapeia_valor_anterior():
    eventos = [{"id": str(i), "tipo": "apelido", "serial": f"S{i}", "horario": "h", "apelido_anterior": "A", "apelido_novo": "B"}
               for i in range(30)]
    eventos[0] = {"id": "w", "tipo": "aviso", "serial": "S0", "motivo": "usuario_removido", "valor_anterior": "joao.silva"}
    c = cliente({"/api/historico-alteracoes": {"total": 30, "eventos": eventos}})
    res = c.listar_historico_alteracoes()
    assert res["total"] == 30 and len(res["eventos"]) == 10
    assert res["eventos"][0]["usuario_anterior"] == "joao.silva" and "valor_anterior" not in res["eventos"][0]
    assert len(c.listar_historico_alteracoes(99)["eventos"]) == simpress_client.MAX_ITENS_LISTA
    assert len(c.listar_historico_alteracoes("abc")["eventos"]) == 10
    assert "joao.silva" not in json.dumps(Mascara().mascarar(res))


def test_apelidos_modificados_vira_lista_com_chave_apelido():
    c = cliente({"/api/equipamento/apelidos-modificados": {"total": 2, "apelidos": {"S1": "PC da Ana", "S2": "PC do Beto"}}})
    res = c.listar_apelidos_modificados()
    assert res == {"total": 2, "itens": [{"serial": "S1", "apelido": "PC da Ana"}, {"serial": "S2", "apelido": "PC do Beto"}], "omitidos": 0}
    assert "PC da Ana" not in json.dumps(Mascara().mascarar(res))


def test_evolucao_usa_as_duas_ultimas_atualizacoes_sem_restauracao():
    evol = {
        "anterior": {"id": "b", "horario": "h1"}, "atual": {"id": "a", "horario": "h2"},
        "contagens": {"novos": 1, "continuam": 4, "resolvidos": 1},
        "mudancas": {
            "novos": [{"secao": "Sem acesso", "item": {"serie": "S1", "computador": "PC1", "motivo": "m"}}],
            "continuam": [{"secao": "x", "item": {"serie": "S9"}}],
            "resolvidos": [{"secao": "Local", "item": {"serial": "S2"}}],
        },
    }
    c = cliente({
        "/api/historico-comparacoes": {"eventos": [{"id": "r", "tipo": "restauracao"}, {"id": "a"}, {"id": "b"}, {"id": "c"}]},
        "/api/operacoes/evolucao": evol,
    })
    res = c.evolucao_atualizacoes()
    assert dict(c.vistas[-1].url.params) == {"anterior": "b", "atual": "a"}
    assert res["total_itens"] == 2 and res["contagens"]["continuam"] == 4
    assert [(i["situacao"], i["serie"]) for i in res["itens"]] == [("novo", "S1"), ("resolvido", "S2")]


def test_evolucao_com_ids_explicitos_e_validacoes():
    c = cliente({"/api/operacoes/evolucao": {"mudancas": {}}})
    assert "mudancas" not in c.evolucao_atualizacoes("x", "y") and dict(c.vistas[0].url.params) == {"anterior": "x", "atual": "y"}
    assert "dois" in c.evolucao_atualizacoes("x")["erro"]
    assert "inválido" in c.evolucao_atualizacoes("a/b", "c")["erro"]
    assert "duas atualizações" in cliente({"/api/historico-comparacoes": {"eventos": [{"id": "a"}]}}).evolucao_atualizacoes()["mensagem"]


def test_log_limita_40_linhas_limpa_e_acha_ultima_falha():
    linhas = [f"linha {i} contato ana@x.com" for i in range(100)]
    c = cliente({
        "/api/automacao/historico": {"execucoes": [{"id": "e1", "status": "falha"}]},
        "/api/automacao/execucoes/e1/log": {
            "execucao": {"id": "e1", "rotina": "os", "status": "falha", "mensagem": "caiu", "log": "e1.log", "capturas": ["a.png"]},
            "arquivo": "e1.log", "linhas": linhas, "limitado": True,
        },
    })
    res = c.log_execucao_automacao()
    assert dict(c.vistas[0].url.params) == {"limite": "1", "status": "falha"}
    assert dict(c.vistas[1].url.params) == {"linhas": "40"}
    assert len(res["detalhes"]) == 40 and res["detalhes"][-1].startswith("linha 99") and "@" not in json.dumps(res)
    assert res["execucao"] == {"id": "e1", "rotina": "os", "status": "falha", "mensagem": "caiu"} and res["limitado"] is True


def test_log_sem_falha_e_id_invalido():
    assert "Nenhuma" in cliente({"/api/automacao/historico": {"execucoes": []}}).log_execucao_automacao()["mensagem"]
    assert "inválido" in cliente({}).log_execucao_automacao("../x")["erro"]
    c = cliente({"/api/automacao/execucoes/e2/log": {"execucao": {}, "linhas": ["a"]}})
    assert c.log_execucao_automacao(" e2 ")["detalhes"] == ["a"] and len(c.vistas) == 1


def test_cartoes_das_listas_novas():
    h = cartao_html("chamados_novos_sebrae", {"total_novos": 12, "chamados": [
        {"numero": "N1", "titulo": "<b>x</b>", "solicitante": "Ana", "serie": "S1", "cruzamento": "unico"}] * 10})
    assert "N1" in h and "&lt;b&gt;x" in h and "+ 2 itens" in h
    h = cartao_html("chamados_antigos_abertos_sebrae", {"total_abertos": 3, "abertos": [
        {"numero": "UTIC-1", "titulo": "t", "responsavel": "Ana", "status": "EM ABERTO", "tipo": "INCIDENTE"}]})
    assert "UTIC-1" in h and "EM ABERTO" in h and "+ 2 itens" in h
    h = cartao_html("listar_historico_alteracoes", {"total": 2, "eventos": [
        {"horario": "h", "serial": "S1", "tipo": "apelido", "apelido_anterior": "A", "apelido_novo": "B"},
        {"horario": "h", "serial": "S2", "tipo": "usuario", "usuario_anterior": "ana", "usuario_novo": "beto"}]})
    assert ">A<" in h and ">B<" in h and ">ana<" in h and ">beto<" in h
    assert "S1" in cartao_html("listar_apelidos_modificados", {"total": 1, "itens": [{"serial": "S1", "apelido": "P"}]})
    assert "novo" in cartao_html("evolucao_atualizacoes", {"total_itens": 1, "itens": [{"situacao": "novo", "serie": "S1"}]})
    assert cartao_html("estado_usuarios_entra", {"dados": {}}) is None
