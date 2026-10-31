"""Ferramentas novas (espelho do assistente do site). Só cliente falso: nenhuma chamada real, nenhuma escrita em dados reais."""

import json

import httpx

from actions import carregar
from lgpd import Mascara
from simpress_client import MAX_ITENS_LISTA, SimpressClient
from tools.simpress_tools import MUTADORAS, SimpressToolbox, descrever_acao

LEITURAS = {"historico_chamados", "snapshot_chamados", "evolucao_chamados", "historico_sebrae", "usuarios_logados"}
ESCRITAS = {
    "registrar_transferencia", "resolver_apelido_manual", "salvar_nome_pessoa", "excluir_chamados_antigos", "recarregar_base",
}


def cliente(rotas):
    """`rotas`: (método, caminho) -> corpo JSON (ou função da requisição). Guarda as requisições em `.vistas`."""
    vistas = []

    def handler(req):
        vistas.append(req)
        corpo = rotas[(req.method, req.url.path)]
        return httpx.Response(200, json=corpo(req) if callable(corpo) else corpo)

    c = SimpressClient(base_url="http://127.0.0.1:8000", transport=httpx.MockTransport(handler))
    c.vistas = vistas
    return c


def corpo_enviado(req):
    return json.loads(req.content)


def test_registradas_com_natureza_e_schema_validos():
    todas = carregar()
    assert (LEITURAS | ESCRITAS) <= set(todas)
    assert not LEITURAS & MUTADORAS and ESCRITAS <= MUTADORAS
    for nome in LEITURAS | ESCRITAS:
        item = todas[nome]
        fn = item["schema"]["function"]
        assert fn["name"] == nome and fn["description"] and fn["parameters"]["type"] == "object"
        assert set(fn["parameters"].get("required", [])) <= set(fn["parameters"]["properties"])
        assert item["altera_dados"] is (nome in ESCRITAS)
        assert ("descrever" in item) is (nome in ESCRITAS)


def test_cartoes_montados_pelo_programa_sem_dado_sensivel():
    texto = descrever_acao("registrar_transferencia", {
        "serial": "abc1", "entrega_cnpj": "12345678000199", "entrega_endereco": "Rua X, 1",
        "entrega_contato": "Maria 111.444.777-35", "entrega_obs": "ligar 41 99999-1234",
    })
    assert "ABC1" in texto and "***.***.***-**" in texto and "[TELEFONE OCULTADO]" in texto and "não gera a planilha" in texto
    assert "Manter o apelido manual da série S1" in descrever_acao("resolver_apelido_manual", {"evento_id": "e1", "serial": "s1", "acao": "manter"})
    assert "volta a seguir as planilhas" in descrever_acao("resolver_apelido_manual", {"evento_id": "e1", "serial": "s1", "acao": "excluir"})
    assert "Salvar o nome 'Ana Lima'" in descrever_acao("salvar_nome_pessoa", {"serial": "s1", "nome": "Ana Lima"})
    assert "Remover o nome manual" in descrever_acao("salvar_nome_pessoa", {"serial": "s1", "nome": ""})
    assert "Não dá para desfazer" in descrever_acao("excluir_chamados_antigos", {})
    assert "planilhas em si não são alteradas" in descrever_acao("recarregar_base", {})


def test_historico_chamados_respeita_limite_e_aponta_erro():
    eventos = [{"id": f"e{i}", "atualizado_em": "2026-10-30"} for i in range(30)]
    c = cliente({("GET", "/api/operacoes/chamados/historico"): {"eventos": eventos}})
    res = SimpressToolbox(c).execute("historico_chamados", {"limite": 3})
    assert res["total"] == 30 and [e["id"] for e in res["eventos"]] == ["e0", "e1", "e2"]
    assert len(SimpressToolbox(c).execute("historico_chamados", {})["eventos"]) == 10


def test_snapshot_chamados_enxuga_e_recusa_id_invalido():
    chamados = [{"serie": f"S{i}", "relacao": f"OS{i}", "descricao": "grande"} for i in range(25)]
    c = cliente({("GET", "/api/operacoes/chamados/snapshot/abc"): {
        "id": "abc", "fontes": {"oracle": {"arquivo": "o.xlsx"}}, "resumo": {"total": 25}, "chamados": chamados,
    }})
    res = SimpressToolbox(c).execute("snapshot_chamados", {"id": "abc"})
    assert res["total_chamados"] == 25 and len(res["chamados"]) == MAX_ITENS_LISTA and res["omitidos"] == 5
    assert set(res["chamados"][0]) == {"serie", "relacao"} and res["fontes"] == {"oracle": "o.xlsx"}
    assert "inválido" in c.snapshot_chamados("a/b")["erro"] and len(c.vistas) == 1


def test_evolucao_chamados_mostra_so_nomes_dos_campos():
    c = cliente({("GET", "/api/operacoes/chamados/evolucao"): {
        "anterior": {"id": "a"}, "atual": {"id": "b"}, "contagens": {"novos": 1},
        "mudancas": {"novos": [{"serie": "N1"}], "alterados": [{"serie": "A1", "campos": [{"campo": "status", "antes": "x", "depois": "y"}]}],
                     "ausentes_arquivo": []},
        "aviso_ausentes": "aviso",
    }})
    res = c.evolucao_chamados("a", "b")
    assert res["alterados"] == [{"serie": "A1", "campos": ["status"]}] and res["aviso"] == "aviso"
    assert dict(c.vistas[0].url.params) == {"anterior": "a", "atual": "b"}
    assert "erro" in c.evolucao_chamados("a", "")


def test_historico_sebrae_lista_filtra_e_detalha():
    c = cliente({
        ("GET", "/api/sebrae/historico"): {"entradas": []},
        ("GET", "/api/sebrae/historico/x1"): {"id": "x1"},
    })
    c.historico_sebrae("", "busca", 5)
    assert dict(c.vistas[0].url.params) == {"limite": "5", "tipo": "busca"}
    c.historico_sebrae("", "invalido", None)
    assert "tipo" not in dict(c.vistas[1].url.params)
    assert c.historico_sebrae("x1")["dados"] == {"id": "x1"}
    assert "inválido" in c.historico_sebrae("a/b")["erro"]


def test_usuarios_logados_normaliza_series_e_mascara_nomes():
    c = cliente({("POST", "/api/equipamentos/usuarios-logados"): lambda req: {"usuarios": {
        s: {"usuario": "ana.lima", "nome_pessoa": "Ana Lima", "origem": "entra", "hostname": "NOTE-ANA", "pendencia": "ligar ana@x.com"}
        for s in corpo_enviado(req)["series"]
    }}})
    res = SimpressToolbox(c).execute("usuarios_logados", {"series": [" a1 ", "A1", "b2"] + [f"z{i}" for i in range(30)]})
    assert corpo_enviado(c.vistas[0])["series"][:2] == ["A1", "B2"] and len(corpo_enviado(c.vistas[0])["series"]) == MAX_ITENS_LISTA
    assert res["total"] == MAX_ITENS_LISTA and "[E-MAIL OCULTADO]" in res["itens"][0]["pendencia"]
    visto_pelo_modelo = json.dumps(Mascara().mascarar(res), ensure_ascii=False)
    assert "Ana Lima" not in visto_pelo_modelo and "ana.lima" not in visto_pelo_modelo and "NOTE-ANA" not in visto_pelo_modelo
    assert "erro" in c.usuarios_logados([])


def test_registrar_transferencia_valida_antes_de_enviar():
    c = cliente({("POST", "/api/historico-transferencias"): {"ok": True}})
    base = {"serial": "ab1", "entrega_cnpj": "12.345.678/0001-99", "entrega_endereco": "Rua X", "entrega_contato": "Maria", "campo_estranho": "x"}
    assert c.registrar_transferencia({**base, "entrega_cnpj": "123"})["sucesso"] is False
    assert c.registrar_transferencia({**base, "entrega_contato": ""})["sucesso"] is False
    assert c.vistas == []
    res = SimpressToolbox(c).execute("registrar_transferencia", base)
    assert res["sucesso"] is True and "AB1" in res["mensagem"]
    assert corpo_enviado(c.vistas[0]) == {"serial": "AB1", "entrega_cnpj": "12.345.678/0001-99", "entrega_endereco": "Rua X", "entrega_contato": "Maria"}


def test_resolver_apelido_manual_valida_e_envia_a_acao():
    c = cliente({("POST", "/api/historico-comparacoes/ev1/apelido-manual/S1"): {"ok": True}})
    assert c.resolver_apelido_manual("ev1", "s1", "apagar")["sucesso"] is False
    assert c.resolver_apelido_manual("a/b", "s1", "manter")["sucesso"] is False
    assert c.vistas == []
    assert c.resolver_apelido_manual("ev1", "s1", "EXCLUIR")["sucesso"] is True
    assert corpo_enviado(c.vistas[0]) == {"acao": "excluir"}


def test_salvar_nome_pessoa_pega_login_do_servidor_e_nunca_do_modelo():
    c = cliente({
        ("POST", "/api/equipamentos/usuarios-logados"): {"usuarios": {"S1": {"usuario": "ana.lima", "serial_cadastro": "SS1"}}},
        ("POST", "/api/equipamento/nome-pessoa"): {"ok": True},
    })
    assert c.salvar_nome_pessoa("s1", "Ana Lima")["mensagem"] == "Nome da pessoa salvo."
    assert corpo_enviado(c.vistas[1]) == {"serial": "SS1", "login_atual": "ana.lima", "nome": "Ana Lima"}
    assert c.salvar_nome_pessoa("s1", "")["mensagem"] == "Nome da pessoa removido."
    sem = cliente({("POST", "/api/equipamentos/usuarios-logados"): {"usuarios": {}}})
    assert sem.salvar_nome_pessoa("s1", "Ana")["sucesso"] is False and len(sem.vistas) == 1


def test_excluir_chamados_antigos_e_recarregar_base_usam_as_rotas_do_site():
    c = cliente({
        ("DELETE", "/api/operacoes/chamados/historico/antigas"): {"removidas": 4},
        ("POST", "/api/recarregar-base"): {"arquivo_origem": "base.xlsx", "total_equipamentos": 10},
    })
    assert "4 importação" in c.excluir_chamados_antigos()["mensagem"]
    res = c.recarregar_base()
    assert res["sucesso"] and "base.xlsx" in res["mensagem"] and res["total_equipamentos"] == 10


def test_escrita_devolve_erro_do_servidor_sem_levantar():
    def falha(_req):
        return httpx.Response(409, json={"detail": "ocupado"})

    c = SimpressClient(base_url="http://127.0.0.1:8000", transport=httpx.MockTransport(falha))
    res = c.recarregar_base()
    assert res["sucesso"] is False and "409" in res["erro"]
