import pytest

from ui.theme import PARES_CONTRASTE, contraste


@pytest.mark.parametrize("fg,bg,minimo,nome", PARES_CONTRASTE)
def test_contraste_wcag_aa(fg, bg, minimo, nome):
    assert contraste(fg, bg) >= minimo, f"{nome}: {contraste(fg, bg):.2f} < {minimo}"
