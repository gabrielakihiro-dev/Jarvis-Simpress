from ui.cartoes import cartao_html


def test_escapa_html_e_corta_em_10():
    itens = [{"secao": "S", "serie": f"<b>X{i}</b>", "computador": "PC", "motivo": "m"} for i in range(20)]
    h = cartao_html("listar_pendencias_operacionais", {"total": 51, "itens": itens})
    assert "<b>X" not in h and "&lt;b&gt;X0" in h
    assert "X9" in h and "X10" not in h
    assert "+ 41 itens" in h


def test_chamados_listas_viram_texto():
    h = cartao_html("listar_chamados_abertos", {"total_chamados": 1, "chamados": [
        {"serie": "ABC", "relacao_os": "somente_oracle", "ordens_servico": ["1", "2"], "pedidos": []}]})
    assert "1, 2" in h and "somente oracle" in h and "itens" not in h


def test_ficha_de_equipamento():
    h = cartao_html("consultar_equipamento", {"encontrado": True, "equipamento": {"serial": "S1", "modelo": "HP"}})
    assert "S1" in h and "HP" in h


def test_sem_cartao():
    assert cartao_html("ferramenta_nova", {"x": 1}) is None
    assert cartao_html("listar_unidades", {"erro": "offline"}) is None
    assert cartao_html("listar_unidades", {"total": 0, "unidades": []}) is None
    assert cartao_html("listar_pendencias_usuarios", {"dados": {"pendencias": [{"serie": "A"}]}}) is not None
