from lgpd import Mascara, limpar_texto_sensivel


def test_limpa_email_e_telefone_mas_preserva_numero_de_os():
    texto = "Fale com ana@empresa.com ou (41) 99876-5432. OS 12345678 e chamado 987654321."
    limpo = limpar_texto_sensivel(texto)
    assert "ana@empresa.com" not in limpo
    assert "99876-5432" not in limpo
    assert "12345678" in limpo and "987654321" in limpo


def test_mascara_ida_e_volta():
    m = Mascara()
    dados = {"usuario_logado": "Maria Souza", "serial": "ABC123", "itens": [{"apelido": "Recepção 2"}]}
    mascarado = m.mascarar(dados)
    assert mascarado["serial"] == "ABC123"
    assert mascarado["usuario_logado"] == "[PESSOA_1]"
    assert "Maria" not in str(mascarado)
    assert m.restaurar({"usuario": "[PESSOA_1]"}) == {"usuario": "Maria Souza"}
    # mesmo valor reutiliza o mesmo marcador
    assert m.mascarar({"usuario_logado": "Maria Souza"})["usuario_logado"] == "[PESSOA_1]"


def test_marcador_inventado_e_detectado():
    m = Mascara()
    assert Mascara.tem_marcador(m.restaurar({"usuario": "[PESSOA_9]"}))
    assert not Mascara.tem_marcador({"usuario": "João"})


def test_sem_usuario_registrado_nao_vira_marcador():
    m = Mascara()
    assert m.mascarar({"usuario_logado": "Sem usuário registrado"})["usuario_logado"] == "Sem usuário registrado"


def test_texto_do_usuario_com_valor_conhecido_e_mascarado():
    m = Mascara()
    m.mascarar({"usuario_logado": "Maria Souza"})
    assert m.ocultar_conhecidos("quem é maria souza?") == "quem é [PESSOA_1]?"
