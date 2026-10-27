import json

import httpx

import simpress_client
from simpress_client import SimpressClient


def cliente(handler, base="http://127.0.0.1:8000"):
    return SimpressClient(base_url=base, transport=httpx.MockTransport(handler))


def test_macbook_sem_s_acha_com_prefixo_s():
    def handler(req):
        if req.url.path == "/api/equipamento/CMVXKV7YCM":
            return httpx.Response(404, json={"detail": "nao"})
        if req.url.path == "/api/equipamento/SCMVXKV7YCM":
            return httpx.Response(200, json={"serial": "SCMVXKV7YCM", "usuarios_logados": "Ana"})
        return httpx.Response(404)

    res = cliente(handler).consultar_equipamento("cmvxkv7ycm")
    assert res["encontrado"] and res["equipamento"]["serial"] == "SCMVXKV7YCM"
    assert "prefixo 'S'" in res["equipamento"]["observacao"]


def test_servidor_offline_nao_trava_e_avisa():
    def handler(req):
        raise httpx.ConnectError("sem conexão")

    c = cliente(handler)
    c._varredura_feita = True  # não varrer portas reais no teste
    assert "inacessível" in c.consultar_equipamento("X1")["erro"]


def test_descoberta_de_porta():
    def handler(req):
        if req.url.port == 8003:
            if req.url.path == "/api/prontidao":
                return httpx.Response(200, json={"ok": True})
            if req.url.path == "/api/stats":
                return httpx.Response(200, json={"total_equipamentos": 10})
        raise httpx.ConnectError("fechada")

    c = cliente(handler)
    assert c.descobrir()
    assert c.base_url == "http://127.0.0.1:8003"


def test_descoberta_ignora_servidor_que_nao_e_simpress():
    def handler(req):
        if req.url.port == 8005 and req.url.path == "/api/prontidao":
            return httpx.Response(200, json={"x": 1})
        if req.url.port == 8005:
            return httpx.Response(404)
        raise httpx.ConnectError("fechada")

    assert not cliente(handler).descobrir()


def test_automacao_erro_nao_executa_fallback(monkeypatch):
    chamadas = []

    def handler(req):
        chamadas.append(req.url.path)
        return httpx.Response(500, json={"detail": "falhou"})

    assert not hasattr(simpress_client, "subprocess")
    res = cliente(handler).executar_automacao("os")
    assert res["sucesso"] is False and "falhou" in res["erro"]
    assert chamadas == ["/api/automacao/executar"]


def test_automacao_rotina_invalida_nao_chama_api():
    def handler(req):
        raise AssertionError("não deveria chamar a API")

    assert cliente(handler).executar_automacao("apagar")["sucesso"] is False


def test_apelido_envia_payload_correto():
    vistos = {}

    def handler(req):
        vistos["corpo"] = json.loads(req.content)
        return httpx.Response(200, json={})

    res = cliente(handler).atualizar_apelido("abc123", " Recepção 2 ")
    assert res["sucesso"] and vistos["corpo"] == {"serial": "ABC123", "apelido": "Recepção 2"}


def test_leitura_apara_listas_e_limpa_email():
    def handler(req):
        return httpx.Response(200, json={"itens": [f"a{i}@x.com" for i in range(50)]})

    dados = cliente(handler).listar_transferencias()["dados"]
    assert len(dados["itens"]) == simpress_client.MAX_ITENS_LISTA + 1
    assert "@" not in json.dumps(dados)


def test_estado_automacao_usa_chaves_reais_do_simpress():
    corpos = {
        "em_andamento": {"estado": "em_andamento", "rotina": "os", "inicio": "10:00", "aguardando_login": True},
        "livre": {"estado": "livre", "rotina": ""},
    }
    for estado, corpo in corpos.items():
        res = cliente(lambda req, c=corpo: httpx.Response(200, json=c)).consultar_status_automacao()
        assert res["executando"] is (estado == "em_andamento")
    assert res["rotina"] == "nenhuma"


def test_unidades_enxutas_trazem_id_de_todas():
    unidades = [{"id": i, "cidade": f"C{i}", "endereco": "Rua X", "uf": "PR", "cep": "80000-000",
                 "cnpj": "1", "label": "x" * 300, "endereco_completo": "y" * 300} for i in range(30)]
    res = cliente(lambda req: httpx.Response(200, json=unidades)).listar_unidades()
    assert res["total"] == 30 and res["unidades"][-1] == {
        "id": 29, "cidade": "C29", "endereco": "Rua X", "uf": "PR", "cep": "80000-000", "cnpj": "1"}


def test_pendencias_contam_por_secao():
    corpo = {"evento": {"horario": "2026-10-27T10:00"}, "pendencias": [
        {"secao": "A", "item": {"serie": f"S{i}", "computador": "PC", "motivo": "m", "usuario": "Ana"}} for i in range(25)
    ] + [{"secao": "B", "item": {"serie": "Z"}}]}
    res = cliente(lambda req: httpx.Response(200, json=corpo)).listar_pendencias_operacionais()
    assert res["total"] == 26 and res["por_secao"] == {"A": 25, "B": 1}
    assert len(res["itens"]) == simpress_client.MAX_ITENS_LISTA and res["omitidos"] == 6
    assert "Ana" not in json.dumps(res)


def test_exportar_salva_sem_sobrescrever(tmp_path):
    def handler(req):
        return httpx.Response(200, content=b"PK-xlsx", headers={"Content-Disposition": 'attachment; filename="../Equip.xlsx"'})

    c = cliente(handler)
    (tmp_path / "Equip.xlsx").write_bytes(b"antigo")
    res = c.exportar_planilha("equipamentos", destino=tmp_path)
    assert res == {"sucesso": True, "arquivo": "Equip (1).xlsx", "pasta": str(tmp_path)}
    assert (tmp_path / "Equip.xlsx").read_bytes() == b"antigo"
    assert (tmp_path / "Equip (1).xlsx").read_bytes() == b"PK-xlsx"


def test_exportar_historico_usa_dia_da_ultima_comparacao(tmp_path):
    vistos = []

    def handler(req):
        if req.url.path == "/api/historico-comparacoes":
            return httpx.Response(200, json={"eventos": [{"horario": "2026-10-27T15:07:49"}]})
        vistos.append(dict(req.url.params))
        return httpx.Response(200, content=b"x", headers={"Content-Disposition": 'attachment; filename="h.xlsx"'})

    assert cliente(handler).exportar_planilha("historico", destino=tmp_path)["sucesso"]
    assert vistos == [{"data": "2026-10-27"}]


def test_exportar_erro_http_nao_cria_arquivo(tmp_path):
    res = cliente(lambda req: httpx.Response(404, json={"detail": "sem eventos"})).exportar_planilha("chamados", destino=tmp_path)
    assert res["sucesso"] is False and "404" in res["erro"] and not list(tmp_path.iterdir())


def test_salvar_unidade_recusa_id_inexistente():
    posts = []

    def handler(req):
        if req.method == "POST":
            posts.append(req)
        return httpx.Response(200, json=[{"id": 1, "cidade": "Curitiba"}])

    res = cliente(handler).salvar_unidade(cidade="X", endereco="Rua", cnpj="1", id=99)
    assert res["sucesso"] is False and not posts


def test_salvar_unidade_envia_payload_com_id():
    vistos = {}

    def handler(req):
        if req.method == "POST":
            vistos["corpo"] = json.loads(req.content)
            return httpx.Response(200, json={})
        return httpx.Response(200, json=[{"id": 7, "cidade": "Maringá"}])

    res = cliente(handler).salvar_unidade(cidade=" Maringá ", endereco="Av. Brasil, 1", cnpj="12", uf="pr", cep="87000000", id="7")
    assert res["sucesso"]
    assert vistos["corpo"] == {"id": 7, "cidade": "Maringá", "endereco": "Av. Brasil, 1", "cnpj": "12", "uf": "PR", "cep": "87000000"}
