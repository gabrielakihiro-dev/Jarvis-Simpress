from array import array

from ui.escuta import CorteSilencio, DetectorPalmas, para_mono_16k, pico

QUIETO, ALTO = 0.01, 0.8


def sequencia(*partes):
    """partes: (pico, ms). Devolve os picos de cada bloco de 50 ms."""
    return [p for p, ms in partes for _ in range(ms // 50)]


def disparos(picos):
    d = DetectorPalmas(limiar=0.25)
    return sum(d.alimentar(p) for p in picos)


CALMA = (QUIETO, 2500)  # passa a calibração


def test_duas_palmas_disparam_uma_vez():
    assert disparos(sequencia(CALMA, (ALTO, 50), (QUIETO, 300), (ALTO, 50), (QUIETO, 1500))) == 1


def test_uma_palma_nao_dispara():
    assert disparos(sequencia(CALMA, (ALTO, 50), (QUIETO, 2000))) == 0


def test_tres_palmas_nao_disparam():
    assert disparos(sequencia(CALMA, (ALTO, 50), (QUIETO, 250), (ALTO, 50), (QUIETO, 250), (ALTO, 50), (QUIETO, 1500))) == 0


def test_ruido_continuo_nao_dispara():
    assert disparos(sequencia(CALMA, (ALTO, 1000), (QUIETO, 300), (ALTO, 1000), (QUIETO, 1500))) == 0


def test_palmas_muito_separadas_nao_disparam():
    assert disparos(sequencia(CALMA, (ALTO, 50), (QUIETO, 1000), (ALTO, 50), (QUIETO, 1500))) == 0


def test_palmas_durante_calibracao_nao_disparam():
    assert disparos(sequencia((QUIETO, 300), (ALTO, 50), (QUIETO, 300), (ALTO, 50), (QUIETO, 800))) == 0


def test_fala_alta_nao_dispara():
    # sílabas de 150 ms são longas demais para palma
    assert disparos(sequencia(CALMA, (ALTO, 150), (QUIETO, 200), (ALTO, 150), (QUIETO, 1500))) == 0


def test_corte_para_depois_do_silencio():
    c = CorteSilencio()
    fins = [c.alimentar(p) for p in sequencia((0.0, 400), (0.3, 1000), (0.0, 1200))]
    assert fins[-1] == "fim" and fins.count("fim") == 1 and fins[-2] is None


def test_corte_sem_voz_desiste_em_5s():
    c = CorteSilencio()
    fins = [c.alimentar(0.0) for _ in range(100)]
    assert fins.index("vazio") == 99


def test_corte_limite_de_20s():
    c = CorteSilencio()
    fins = [c.alimentar(0.3) for _ in range(400)]
    assert fins[-1] == "fim"


def test_conversao_48k_estereo_e_float():
    estereo = array("h", [1000, -5] * 4800).tobytes()  # 0,1 s a 48 kHz
    mono = array("h", para_mono_16k(estereo, 2, 48000))
    assert len(mono) == 1600 and set(mono) == {1000}
    flut = array("f", [0.5] * 441).tobytes()  # 10 ms a 44,1 kHz
    convertido = array("h", para_mono_16k(flut, 1, 44100, flutuante=True))
    assert len(convertido) == 160 and convertido[0] == 16383
    assert abs(pico(mono.tobytes()) - 1000 / 32768) < 1e-9


def test_palmas_em_microfone_com_ruido_alto():
    # ruído de fundo 0.2 (ganho alto): sem teto o limiar viraria 1.2 e nenhuma palma passaria
    assert disparos(sequencia((0.2, 2500), (0.95, 50), (0.2, 300), (0.95, 50), (0.2, 1500))) == 1


def test_voz_em_sala_barulhenta_conta_como_fala():
    c = CorteSilencio(ruido=0.3)
    assert c.minimo == 0.3
