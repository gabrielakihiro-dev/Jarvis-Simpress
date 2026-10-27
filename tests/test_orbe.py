import math

from ui.orbe import envelope_fala, girar, pontos_esfera, projetar


def norma(p):
    return math.sqrt(sum(c * c for c in p))


def test_pontos_esfera_ficam_no_raio_1_e_cobrem_os_dois_polos():
    pts = pontos_esfera(500)
    assert len(pts) == 500
    assert all(abs(norma(p) - 1) < 1e-9 for p in pts)
    assert max(p[1] for p in pts) > 0.99 and min(p[1] for p in pts) < -0.99


def test_girar_zero_nao_muda_e_giro_preserva_distancia():
    pts = pontos_esfera(50)
    assert girar(pts, 0, 0) == pts
    assert all(abs(norma(p) - 1) < 1e-9 for p in girar(pts, 0.7, -1.3))


def test_girar_90_graus_em_y_leva_x_para_tras():
    (x, y, z), = girar([(1.0, 0.0, 0.0)], 0, math.pi / 2)
    assert abs(x) < 1e-9 and abs(y) < 1e-9 and abs(z + 1) < 1e-9


def test_projetar_aumenta_o_que_esta_mais_perto():
    assert projetar(0, 0, 0, 100) == (0, 0, 1)
    perto, longe = projetar(1, 1, 0.5, 100), projetar(1, 1, -0.5, 100)
    assert perto[2] > 1 > longe[2]
    assert perto[0] > 100 > longe[0] and perto[1] < 0  # y da tela cresce para baixo


def test_envelope_da_fala_fica_entre_0_e_1_e_varia():
    valores = [envelope_fala(i / 60) for i in range(600)]
    assert all(0 <= v <= 1 for v in valores)
    assert max(valores) - min(valores) > 0.5
