from types import SimpleNamespace as NS

from ui.chat_panel import ChatPanel


def painel(estado="ocioso", ocupado=False):
    chamadas = []
    p = NS(
        escuta=NS(mudo=False, gravar=lambda: chamadas.append("gravar")),
        orbe=NS(estado=estado),
        _transcricao=None,
        _ocupado_agora=lambda: ocupado,
        cancelar=lambda: chamadas.append("cancelar"),
        _avisar_mudo=lambda: chamadas.append("mudo"),
    )
    return p, chamadas


def test_clique_no_orbe_ativo_cancela():
    for estado in ("ouvindo", "pensando", "falando"):
        p, chamadas = painel(estado)
        ChatPanel._clicou_orbe(p)
        assert chamadas == ["cancelar"], estado


def test_clique_com_cartao_ou_gravando_cancela():
    p, chamadas = painel(ocupado=True)
    ChatPanel._clicou_orbe(p)
    assert chamadas == ["cancelar"]


def test_clique_no_orbe_parado_comeca_a_gravar():
    for estado in ("ocioso", "dormindo"):
        p, chamadas = painel(estado)
        ChatPanel._clicou_orbe(p)
        assert chamadas == ["gravar"], estado
