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


def test_anotacao_com_nome_e_mascarada_mesmo_antes_do_campo_usuario():
    m = Mascara()
    dados = {"itens": [
        {"anotacao": "Maria Souza foi transferida para Cascavel", "serie": "S1"},
        {"usuario": "Maria Souza", "serie": "S1"},
    ]}
    mascarado = m.mascarar(dados)
    assert "Maria" not in str(mascarado)
    assert mascarado["itens"][0]["anotacao"] == "[PESSOA_1] foi transferida para Cascavel"


def test_nome_curto_nao_corrompe_palavra_maior():
    m = Mascara()
    m.mascarar({"usuario": "Ana"})
    assert m.ocultar_conhecidos("Anabela e Ana") == "Anabela e [PESSOA_1]"
    # Campo técnico (modelo) não passa pela troca de texto livre.
    assert m.mascarar({"modelo": "Ana Pro"})["modelo"] == "Ana Pro"


def test_nomes_da_base_mascaram_texto_e_sobrevivem_a_limpar():
    m = Mascara()
    m.registrar_base(["Joana Lima", "TI", " ", "Sem usuário registrado"])
    assert m.ocultar_conhecidos("cadê a JOANA LIMA da TI?") == "cadê a [PESSOA_1] da TI?"
    m.limpar()
    assert m.ocultar_conhecidos("Joana Lima") == "[PESSOA_1]"
    assert m.restaurar("[PESSOA_1]") == "Joana Lima"


def test_mascara_contatos_de_transferencia():
    m = Mascara()
    dados = {"itens": [{"entrega_contato": "Ana Lima", "retirada_contato": "Rui Costa", "serie": "X1"}]}
    mascarado = m.mascarar(dados)
    assert "Ana" not in str(mascarado) and "Rui" not in str(mascarado)
    assert m.restaurar(mascarado) == dados


def test_mascara_campos_de_mudanca_de_usuario_e_apelido():
    m = Mascara()
    dados = {
        "serie": "X1",
        "usuario_anterior": "asoliveira", "usuario_novo": "",
        "nome_pessoa_anterior": "Andre Oliveira", "nome_pessoa_novo": "",
        "apelido_manual": "PC Diretoria", "apelido_anterior": "PC1", "apelido_novo": "PC2",
        "apelido_na_simpress": "PC3", "apelido_no_endpoint": "PC4",
        "motivo": "O Endpoint deixou de informar o usuário asoliveira.",
    }
    mascarado = m.mascarar(dados)
    texto = str(mascarado)
    for valor in ("asoliveira", "Andre Oliveira", "PC Diretoria", "PC1", "PC2", "PC3", "PC4"):
        assert valor not in texto
    # o nome já conhecido some também do texto livre (motivo)
    assert "asoliveira" not in mascarado["motivo"]
    assert m.restaurar(mascarado) == dados


def test_mascara_campos_brutos_do_historico_de_comparacao():
    # chaves cruas (pré-rótulo) usadas por consultar_historico_comparacao, que não passa por _rotular_item.
    m = Mascara()
    dados = {
        "serie": "X1",
        "apelido_equipamentos_detalhes": "PRNOTETI096",
        "apelido_invall": "PRNOTETI096",
        "computador": "PRNOTETI096 - Backup Diretoria (M)",
    }
    mascarado = m.mascarar(dados)
    texto = str(mascarado)
    for valor in ("PRNOTETI096", "PRNOTETI096 - Backup Diretoria (M)"):
        assert valor not in texto
    assert m.restaurar(mascarado) == dados


def test_mascara_cpf_formatado_no_meio_da_frase():
    limpo = limpar_texto_sensivel("Titular CPF 123.456.789-00, favor conferir.")
    assert limpo == "Titular CPF ***.***.***-**, favor conferir."


def test_mascara_cpf_solto_so_com_digito_verificador_valido():
    assert limpar_texto_sensivel("CPF 52998224725 ok") == "CPF ***.***.***-** ok"
    # 11 dígitos inválidos (ou todos iguais) ficam intactos
    assert limpar_texto_sensivel("protocolo 12345678900") == "protocolo 12345678900"
    assert limpar_texto_sensivel("11111111111") == "11111111111"


def test_cpf_nao_mascara_os_serie_nem_telefone():
    texto = "OS 12345678 serie CMVXKV7YCM chamado 987654321"
    assert limpar_texto_sensivel(texto) == texto
    limpo = limpar_texto_sensivel("CPF 123.456.789-00 tel (41) 99876-5432")
    assert limpo == "CPF ***.***.***-** tel [TELEFONE OCULTADO]"


def test_omite_senha_mas_preserva_texto_comum():
    limpo = limpar_texto_sensivel("login ana senha: Abc@123 e Password=xyz9. Senha expirada")
    assert "Abc@123" not in limpo and "xyz9" not in limpo
    assert limpo == "login ana senha: [DADO SENSÍVEL OMITIDO] e Password=[DADO SENSÍVEL OMITIDO] Senha expirada"


def test_mascarar_aplica_cpf_em_resultado_de_ferramenta():
    m = Mascara()
    assert m.mascarar({"descricao": "CPF 123.456.789-00"})["descricao"] == "CPF ***.***.***-**"
