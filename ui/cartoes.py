"""Respostas em cartões: tabelas HTML (subconjunto do QTextBrowser) com os dados reais das ferramentas."""

import html
from typing import Any, Dict, Optional

from ui import theme

MAX_LINHAS = 10

# ferramenta: (caminho da lista no resultado, [(cabeçalho, campo)], campo do total)
TABELAS = {
    "listar_chamados_abertos": ("chamados", [("Série", "serie"), ("Relação", "relacao_os"), ("OS", "ordens_servico"), ("Pedidos", "pedidos")], "total_chamados"),
    "listar_pendencias_operacionais": ("itens", [("Seção", "secao"), ("Série", "serie"), ("Computador", "computador"), ("Motivo", "motivo")], "total"),
    "listar_unidades": ("unidades", [("Cidade", "cidade"), ("Endereço", "endereco"), ("CEP", "cep"), ("CNPJ", "cnpj")], "total"),
    "pesquisar_catalogo": ("itens", [("Série", "serial"), ("Modelo", "modelo"), ("Apelido", "apelido"), ("Cidade", "cidade"), ("Usuário", "usuario_logado")], "total_encontrados"),
    "listar_pendencias_usuarios": ("dados.pendencias", [("Série", "serie"), ("Computador", "computador"), ("Tipo", "tipo"), ("Usuário atual", "usuario_atual")], ""),
}
FICHA = {"consultar_equipamento": ("equipamento", [("Série", "serial"), ("Modelo", "modelo"), ("Tipo", "tipo"), ("Apelido", "apelido"),
                                                   ("Cidade", "cidade"), ("UF", "uf"), ("Usuário", "usuario_logado"), ("Contrato", "contrato")])}


def _pegar(dados: Any, caminho: str) -> Any:
    for parte in caminho.split("."):
        dados = dados.get(parte) if isinstance(dados, dict) else None
    return dados


def _valor(v: Any) -> str:
    if isinstance(v, list):
        v = ", ".join(map(str, v))
    texto = str(v if v not in (None, "") else "—").replace("_", " ")
    return html.escape(texto)


def _tabela(cabecalho: str, linhas: str) -> str:
    return (f"<table width='100%' cellspacing='0' cellpadding='4' style='border:1px solid {theme.BORDER_STRONG};"
            f" background:{theme.SURFACE_ALT}'>{cabecalho}{linhas}</table>")


def cartao_html(ferramenta: str, resultado: Dict[str, Any]) -> Optional[str]:
    """Tabela com até 10 linhas e "+ N itens"; None se a ferramenta não tem cartão ou o formato mudou."""
    if not isinstance(resultado, dict) or "erro" in resultado:
        return None
    th = f"style='color:{theme.CYAN}; text-align:left'"
    if ferramenta in FICHA:
        chave, campos = FICHA[ferramenta]
        reg = resultado.get(chave)
        if not isinstance(reg, dict):
            return None
        linhas = "".join(f"<tr><td {th}>{c}</td><td>{_valor(reg.get(k))}</td></tr>" for c, k in campos)
        return _tabela("", linhas)
    if ferramenta not in TABELAS:
        return None
    caminho, campos, campo_total = TABELAS[ferramenta]
    lista = _pegar(resultado, caminho)
    if not isinstance(lista, list) or not lista:
        return None
    cab = "<tr>" + "".join(f"<th {th}>{c}</th>" for c, _ in campos) + "</tr>"
    linhas = "".join("<tr>" + "".join(f"<td>{_valor(i.get(k) if isinstance(i, dict) else '')}</td>" for _, k in campos) + "</tr>"
                     for i in lista[:MAX_LINHAS])
    total = resultado.get(campo_total) if campo_total else None
    resto = (total if isinstance(total, int) else len(lista)) - min(len(lista), MAX_LINHAS)
    if resto > 0:
        linhas += f"<tr><td colspan='{len(campos)}' style='color:{theme.TEXT_SECONDARY}'>+ {resto} itens</td></tr>"
    return _tabela(cab, linhas)
