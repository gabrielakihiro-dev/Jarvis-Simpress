from ui.shell import avisos


def test_primeiro_estado_nao_avisa():
    assert avisos({}, {"online": True, "chamados": 5}) == []


def test_conexao_e_chamados_e_automacao():
    on = {"online": True, "chamados": 2, "automacao": {"executando": True, "rotina": "sebrae"}}
    assert avisos(on, {"online": False}) == ["Perdi a conexão com o Simpress."]
    assert avisos({"online": False}, on) == ["Simpress de volta."]
    novo = {"online": True, "chamados": 5, "automacao": {"executando": False}}
    msgs = avisos(on, novo)
    assert "Chegaram 3 chamados novos (total 5)." in msgs
    assert any("sebrae terminou" in m for m in msgs)
    assert avisos(novo, dict(novo, chamados=4)) == []
