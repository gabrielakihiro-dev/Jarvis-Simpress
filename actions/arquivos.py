"""Exportação e importação de planilhas (não alteram a base do Simpress)."""

from actions._base import tool
from simpress_client import EXPORTACOES

TOOLS = [
    tool(
        "exportar_planilha",
        "Gera a planilha oficial do Simpress e salva na pasta Downloads do usuário. 'equipamentos' usa o modelo de exportação; 'chamados' é o acompanhamento de chamados; 'historico' é o Histórico de Planilhas do dia (padrão: dia da última comparação).",
        lambda c, a: c.exportar_planilha(str(a.get("tipo", "")), str(a.get("data", "") or "")),
        {
            "tipo": {"type": "string", "enum": list(EXPORTACOES), "description": "Qual planilha exportar."},
            "data": {"type": "string", "description": "Só para 'historico': dia no formato AAAA-MM-DD."},
        },
        ["tipo"],
    ),
    tool(
        "abrir_importacao",
        "Abre na tela do Jarvis a janela para o usuário escolher as duas planilhas (Endpoint e Simpress) que já tem no computador e importá-las. Use quando ele quiser importar arquivos próprios; para baixar e importar automaticamente, use executar_automacao_chrome com 'inventarios'.",
        lambda c, a: {"abrir_importacao": True, "mensagem": "Janela de importação aberta na tela do usuário."},
    ),
]
