import pytest

from ui.palavra_chave import QUADRO, QUADRO_BYTES, DetectorChamada, PalavraChaveWorker, limiar_do_ambiente

BLOCO = bytes(1600)  # 800 amostras Int16 = 50 ms


class ModeloFalso:
    """Devolve as pontuações da lista, uma por quadro; 0.0 quando acaba."""

    def __init__(self, pontuacoes=()):
        self.pontuacoes = list(pontuacoes)
        self.quadros = []
        self.resets = 0

    def predict(self, quadro):
        self.quadros.append(len(quadro))
        return self.pontuacoes.pop(0) if self.pontuacoes else 0.0

    def reset(self):
        self.resets += 1


def test_blocos_de_800_viram_quadros_de_1280():
    m = ModeloFalso()
    d = DetectorChamada(m, limiar=0.5)
    for _ in range(8):  # 6400 amostras = 5 quadros de 1280
        d.alimentar(BLOCO)
    assert m.quadros == [QUADRO_BYTES] * 5
    assert QUADRO == 1280


def test_resto_entre_blocos_nao_perde_amostras():
    m = ModeloFalso()
    d = DetectorChamada(m, limiar=0.5)
    d.alimentar(BLOCO)           # 800 < 1280: nada ainda
    assert m.quadros == []
    d.alimentar(BLOCO)           # 1600 -> 1 quadro, sobram 320
    assert m.quadros == [QUADRO_BYTES]


def test_limiar_dispara_so_quando_alcanca():
    d = DetectorChamada(ModeloFalso([0.49, 0.5]), limiar=0.5)
    assert d.alimentar(bytes(QUADRO_BYTES)) is False
    assert d.alimentar(bytes(QUADRO_BYTES)) is True


def test_repouso_impede_segundo_disparo_e_depois_volta():
    m = ModeloFalso([0.9] * 100)
    d = DetectorChamada(m, limiar=0.5, repouso_ms=800)  # 10 quadros
    quadro = bytes(QUADRO_BYTES)
    disparos = [d.alimentar(quadro) for _ in range(12)]
    assert disparos == [True] + [False] * 10 + [True]
    assert m.resets == 2  # reset do modelo a cada disparo


def test_limpar_zera_resto_repouso_e_modelo():
    m = ModeloFalso([0.9, 0.9])
    d = DetectorChamada(m, limiar=0.5)
    assert d.alimentar(bytes(QUADRO_BYTES))
    d.alimentar(BLOCO)
    d.limpar()
    assert d.alimentar(bytes(QUADRO_BYTES))  # repouso acabou e o resto de 800 amostras foi descartado
    assert m.quadros == [QUADRO_BYTES] * 2


def test_limiar_do_ambiente(monkeypatch):
    monkeypatch.delenv("JARVIS_WAKE_LIMIAR", raising=False)
    assert limiar_do_ambiente() == 0.4
    monkeypatch.setenv("JARVIS_WAKE_LIMIAR", "0.7")
    assert limiar_do_ambiente() == 0.7
    monkeypatch.setenv("JARVIS_WAKE_LIMIAR", "alto")
    assert limiar_do_ambiente() == 0.4


def test_worker_plano_b_quando_o_modelo_falta():
    def sem_modelo():
        raise FileNotFoundError("hey_jarvis_v0.1.onnx")

    w = PalavraChaveWorker(criar_modelo=sem_modelo)
    msgs = []
    w.falhou.connect(msgs.append)
    w.run()  # síncrono: sem iniciar a thread
    assert len(msgs) == 1 and "hey_jarvis_v0.1.onnx" in msgs[0]


def test_worker_emite_ouviu_e_esvazia_a_fila():
    class Worker(PalavraChaveWorker):
        parar = False

        def isInterruptionRequested(self):  # run() síncrono: o QThread não iniciado ignora requestInterruption
            return self.parar

    w = Worker(criar_modelo=lambda: ModeloFalso([0.9]))
    ouvidos = []
    w.ouviu.connect(lambda: (ouvidos.append(1), setattr(w, "parar", True)))
    for _ in range(10):
        w.alimentar(BLOCO)
    w.run()
    assert ouvidos == [1] and w._fila.empty()
