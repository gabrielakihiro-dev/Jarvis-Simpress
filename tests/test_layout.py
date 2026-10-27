from ui.shell import faixa


def test_faixa_e_diametro_do_orbe():
    assert faixa(1400, 860) == ("larga", 500)
    assert faixa(1400, 700) == ("larga", 400)
    assert faixa(1400, 600) == ("larga", 300)
    assert faixa(1000, 700) == ("media", 268)
    assert faixa(740, 600) == ("lista", 192)
