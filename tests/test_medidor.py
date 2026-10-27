from ui.widgets import texto_medidor


def test_texto_do_medidor_arredonda_e_limita():
    assert texto_medidor("CPU", 12.4) == "CPU 12%"
    assert texto_medidor("RAM", 99.6) == "RAM 100%"
    assert texto_medidor("CPU", 140) == "CPU 100%"
    assert texto_medidor("CPU", -3) == "CPU 0%"
