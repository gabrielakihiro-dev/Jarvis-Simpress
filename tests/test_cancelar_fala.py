import voice
from ui.chat_panel import e_cancelar


def test_cancelar_por_voz():
    for t in ("Cancelar", "cancela.", "Jarvis, cancele o comando", "pode cancelar"):
        assert e_cancelar(t), t
    for t in ("", "quantos cancelamentos hoje", "cancelar a importação do lote de ontem", "listar chamados"):
        assert not e_cancelar(t), t


def test_trechos_primeira_frase_sozinha():
    t = "Encontrei 12 chamados. " + "Os mais antigos são de Curitiba. " * 20
    partes = voice.trechos(t)
    assert partes[0] == "Encontrei 12 chamados."
    assert all(len(p) < 300 for p in partes)
    assert " ".join(partes).split() == voice.limpar_markdown_para_fala(t).split()
    assert voice.trechos("**Pronto**") == ["Pronto"]


def test_nao_cancela_nao_cancela():
    assert not e_cancelar("não cancela")
