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


def test_risco_por_palavra_inteira():
    for t in (["Enviar"], ["Salvar alterações"], ["", "Excluir"], ["OK"], ["Concluír tarefa"]):
        assert nj.e_arriscado(t), t
    for t in (["Buscar"], ["Facebook"], ["Okta"], ["Pesquisar"], [""]):
        assert not nj.e_arriscado(t), t


def test_sharepoint_salva_sozinho():
    assert nj.salva_sozinho("https://simpress-my.sharepoint.com/:x:/r/x")
    assert not nj.salva_sozinho("https://www.youtube.com/")


class _Sessao:
    def __init__(self, tid):
        self.tid = tid

    def send(self, _):
        return {"targetInfo": {"targetId": self.tid}}

    def detach(self):
        pass


class _Pagina:
    def __init__(self, tid, visivel="hidden"):
        self.tid, self.visivel = tid, visivel

    def evaluate(self, _):
        if self.visivel is None:
            raise RuntimeError("aba caiu")
        return self.visivel


class _Contexto:
    def __init__(self, paginas):
        self.pages, self.novas = paginas, []

    def new_cdp_session(self, pagina):
        return _Sessao(pagina.tid)

    def new_page(self):
        self.novas.append(1)
        return "nova"


class _Browser:
    def __init__(self, paginas):
        self.contexts = [_Contexto(paginas)] if paginas is not None else []
        self.novo = _Contexto([])

    def new_context(self):
        self.contexts.append(self.novo)
        return self.novo


def _ordem(monkeypatch, ids):
    def f():
        if ids is None:
            raise OSError("sem /json/list")
        return ids
    monkeypatch.setattr(nj, "_ordem_das_abas", f)


def test_pagina_ativa_pela_ordem_do_json_list(monkeypatch):
    a, b = _Pagina("A", "visible"), _Pagina("B", "visible")
    _ordem(monkeypatch, ["B", "A"])
    assert nj.pagina_ativa(_Browser([a, b])) is b


def test_pagina_ativa_cai_para_visivel(monkeypatch):
    a, b, c = _Pagina("A", None), _Pagina("B", "visible"), _Pagina("C")
    _ordem(monkeypatch, None)
    assert nj.pagina_ativa(_Browser([a, b, c])) is b
    _ordem(monkeypatch, ["Z"])  # nenhum id bate
    assert nj.pagina_ativa(_Browser([a, b, c])) is b


def test_pagina_ativa_cai_para_ultima(monkeypatch):
    a, b = _Pagina("A"), _Pagina("B")
    _ordem(monkeypatch, None)
    assert nj.pagina_ativa(_Browser([a, b])) is b


def test_pagina_ativa_sem_paginas_abre_uma(monkeypatch):
    _ordem(monkeypatch, None)
    br = _Browser([])
    assert nj.pagina_ativa(br) == "nova" and br.contexts[0].novas


def test_pagina_ativa_sem_contexto_cria_contexto(monkeypatch):
    _ordem(monkeypatch, None)
    br = _Browser(None)
    assert nj.pagina_ativa(br) == "nova" and br.contexts == [br.novo]


def test_porta_invalida_ou_9333_cai_em_9334():
    assert [nj._porta(v) for v in ("abc", "", None, "9333", 9333, "9400")] == [9334, 9334, 9334, 9334, 9334, 9400]
