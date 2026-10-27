from types import SimpleNamespace as NS

import voice
from ui.chat_panel import ChatPanel, FalaWorker


class FalaInterrompida(FalaWorker):
    def isInterruptionRequested(self) -> bool:
        return True


def test_desligar_voz_cala_na_hora(monkeypatch):
    monkeypatch.setattr(voice, "HABILITAR_VOZ", True)
    chamadas = []
    p = NS(_parar_fala=lambda: chamadas.append("parar"), _atualizar_voz=lambda: None,
           mudou_estado=NS(emit=lambda: None))
    ChatPanel._alternar_voz(p)  # desliga
    assert chamadas == ["parar"]
    ChatPanel._alternar_voz(p)  # liga de novo: nada a calar
    assert chamadas == ["parar"]


def test_trecho_que_chega_depois_de_parar_nao_toca(tmp_path):
    mp3 = tmp_path / "trecho.mp3"
    mp3.write_bytes(b"x")
    fala = FalaInterrompida("oi")
    tocou = []
    p = NS(sender=lambda: fala, _fala=fala, _mp3_atual="", orbe=NS(definir=tocou.append))
    ChatPanel._tocar(p, str(mp3))
    assert not tocou and not mp3.exists()
