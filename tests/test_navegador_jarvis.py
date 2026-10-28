from pathlib import Path

import pytest

import navegador_jarvis as nj


def test_perfil_nao_e_apagado_pela_limpeza_do_simpress():
    assert ".chrome-automation" not in str(nj.PERFIL).lower()
    cmd = nj.comando_chrome(Path("chrome.exe"))
    assert f"--remote-debugging-port={nj.PORTA}" in cmd and "--remote-debugging-address=127.0.0.1" in cmd
    assert f"--user-data-dir={nj.PERFIL}" in cmd


def test_chrome_fechado_sobe_de_novo(monkeypatch):
    estados, abertos = iter([False, False, True]), []
    monkeypatch.setattr(nj, "localizar_chrome", lambda: Path("chrome.exe"))
    nj.garantir_chrome(popen=abertos.append, ativo=lambda: next(estados), dormir=lambda s: None)
    assert len(abertos) == 1


def test_chrome_ja_aberto_nao_sobe_outro():
    abertos = []
    nj.garantir_chrome(popen=abertos.append, ativo=lambda: True, dormir=lambda s: None)
    assert abertos == []


def test_chrome_mudo_da_erro_claro(monkeypatch):
    monkeypatch.setattr(nj, "localizar_chrome", lambda: Path("chrome.exe"))
    with pytest.raises(nj.NavegadorErro):
        nj.garantir_chrome(espera_s=1, popen=lambda c: None, ativo=lambda: False, dormir=lambda s: None)
