import voice
from voice import AVISO_RESTANTE, resumo_para_fala


def test_texto_curto_fica_inteiro():
    assert resumo_para_fala("Tudo certo.") == "Tudo certo."
    assert resumo_para_fala("") == ""


def test_texto_longo_vira_poucas_frases_e_avisa():
    longo = "Encontrei 12 chamados abertos. " + "Os mais antigos são de Curitiba. " * 10
    fala = resumo_para_fala(longo)
    assert fala.startswith("Encontrei 12 chamados abertos.")
    assert fala.endswith(AVISO_RESTANTE)
    assert fala.count("Curitiba") == voice.MAX_FRASES_FALA - 1


def test_tabela_nao_e_lida():
    fala = resumo_para_fala("Pronto.\n| serial | local |\n|---|---|\n| A1 | Curitiba |")
    assert fala == f"Pronto. {AVISO_RESTANTE}"


def test_frase_unica_gigante_e_cortada_em_palavra_inteira():
    fala = resumo_para_fala("palavra " * 200)
    assert len(fala) <= voice.MAX_CHARS_FALA + len(AVISO_RESTANTE) + 2
    assert fala.endswith(AVISO_RESTANTE)
