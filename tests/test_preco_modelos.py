import llm_client


class Resp:
    def raise_for_status(self):
        return self

    def json(self):
        return {"data": [
            {"id": "a/barato", "supported_parameters": ["tools"],
             "pricing": {"prompt": "0.00000015", "completion": "0.0000006"}},
            {"id": "b/sem-saida", "supported_parameters": ["tools"], "pricing": {"prompt": "0.0000001"}},
            {"id": "c/sem-ferramentas", "supported_parameters": [], "pricing": {}},
        ]}


def test_rotulo_mostra_entrada_e_saida(monkeypatch):
    monkeypatch.setattr(llm_client.httpx, "get", lambda *a, **k: Resp())
    assert llm_client.listar_modelos_ao_vivo() == [
        ("a/barato", "a/barato · entrada US$ 0.15/M · saída US$ 0.60/M"),
        ("b/sem-saida", "b/sem-saida · preço n/d"),
    ]
