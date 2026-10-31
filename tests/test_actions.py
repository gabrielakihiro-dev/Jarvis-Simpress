from actions import carregar
from actions._base import tool
from tools.simpress_tools import MUTADORAS, NOMES_FERRAMENTAS, SimpressToolbox, descrever_acao, requer_confirmacao

# Catálogo de antes da migração para actions/: nenhuma ferramenta pode sumir nem mudar de natureza.
NOMES_ESPERADOS = {
    "consultar_equipamento", "pesquisar_catalogo", "obter_totais_inventario", "listar_chamados_abertos",
    "consultar_status_automacao", "consultar_ultima_comparacao", "obter_painel", "obter_prontidao",
    "listar_pendencias_operacionais", "linha_do_tempo_chamados", "obter_relatorio_mensal",
    "listar_historico_automacao", "resumo_sebrae", "consultar_historico_comparacao", "listar_unidades",
    "exportar_planilha", "abrir_importacao", "listar_transferencias", "listar_pendencias_usuarios",
    "abrir", "executar_automacao_chrome", "cancelar_automacao_chrome", "atualizar_apelido", "atualizar_usuario",
    "salvar_unidade", "decidir_pendencia_usuario",
    "listar_divergencias_localidade", "consultar_divergencia_localidade", "listar_secao_comparacao",
    "navegar", "ler_pagina", "clicar", "clicar_confirmado", "digitar", "digitar_confirmado", "abas",
    "logar_site",
    "chamados_novos_sebrae", "chamados_antigos_abertos_sebrae", "estado_usuarios_entra", "listar_historico_alteracoes",
    "listar_apelidos_modificados", "evolucao_atualizacoes", "log_execucao_automacao",
    "historico_chamados", "snapshot_chamados", "evolucao_chamados", "historico_sebrae", "usuarios_logados",
    "registrar_transferencia", "resolver_apelido_manual", "salvar_nome_pessoa", "excluir_chamados_antigos", "recarregar_base",
}
MUTADORAS_ESPERADAS = {
    "executar_automacao_chrome", "cancelar_automacao_chrome", "atualizar_apelido",
    "atualizar_usuario", "decidir_pendencia_usuario", "salvar_unidade",
    "clicar_confirmado", "digitar_confirmado",
    "registrar_transferencia", "resolver_apelido_manual", "salvar_nome_pessoa", "excluir_chamados_antigos", "recarregar_base",
}


def test_paridade_de_nomes_e_mutadoras():
    assert NOMES_FERRAMENTAS == NOMES_ESPERADOS
    assert MUTADORAS == MUTADORAS_ESPERADAS


def test_sem_altera_dados_explicito_conta_como_mutadora():
    item = tool("x", "d", lambda c, a: {})
    del item["altera_dados"]
    assert item.get("altera_dados", True) is True


def test_cartao_de_confirmacao_e_montado_pelo_programa():
    assert descrever_acao("atualizar_apelido", {"serial": " abc1 ", "apelido": "Sala"}) == \
        "Alterar o apelido do serial ABC1 para 'Sala'."
    assert descrever_acao("consultar_equipamento", {}) == "Executar consultar_equipamento."
    assert requer_confirmacao("salvar_unidade") and not requer_confirmacao("listar_unidades")


def test_execute_despacha_para_o_cliente_e_recusa_desconhecida():
    class Cliente:
        def consultar_equipamento(self, serial):
            return {"serial": serial}

    box = SimpressToolbox(Cliente())
    assert box.execute("consultar_equipamento", {"serial": "X1"}) == {"serial": "X1"}
    assert "desconhecida" in box.execute("rm_rf", {})["erro"]


def test_toda_ferramenta_tem_schema_valido():
    for nome, item in carregar().items():
        fn = item["schema"]["function"]
        assert fn["name"] == nome and fn["description"] and fn["parameters"]["type"] == "object"
        assert callable(item["executar"])
