"""Mascaramento reversível de dados pessoais (LGPD) entre o Jarvis e a IA.

Valores sensíveis (usuário logado, apelido, nomes) viram marcadores como
`[PESSOA_1]` antes de ir ao modelo. O mapa vive só na memória do processo e
nunca é gravado. Os marcadores voltam ao valor real nos argumentos das
ferramentas, no texto mostrado na tela e na voz.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
# Telefone só com DDD, +55 ou hífen: números de OS/chamado (ex.: 12345678) ficam intactos.
PHONE_PATTERN = re.compile(
    r"(?<![\w-])(?:"
    r"(?:\+55\s?)?\(\d{2}\)\s?9?\d{4}[-\s]?\d{4}"
    r"|(?:\+55\s?)?\d{2}\s9?\d{4}[-\s]?\d{4}"
    r"|9?\d{4}-\d{4}"
    r")(?![\w-])"
)
TOKEN_PATTERN = re.compile(r"\[PESSOA_\d+\]")

# Chaves cujo valor identifica uma pessoa ou é escolhido por ela.
CHAVES_SENSIVEIS = frozenset({
    "usuario_logado", "usuarios_logados", "usuario_manual", "usuario", "apelido",
    "nome", "nome_pessoa", "solicitante", "responsavel", "login", "email",
    "entrega_contato", "retirada_contato",
    "usuario_anterior", "usuario_novo", "nome_pessoa_anterior", "nome_pessoa_novo",
    "apelido_manual", "apelido_anterior", "apelido_novo",
    "apelido_na_simpress", "apelido_no_endpoint",
    "apelido_equipamentos_detalhes", "apelido_invall", "computador",
})
# Textos livres (escritos por pessoas) onde um nome conhecido pode aparecer no meio da frase.
CHAVES_TEXTO_LIVRE = frozenset({
    "anotacao", "descricao", "observacao", "motivo", "detalhes", "comentario", "mensagem", "erro",
})
SEM_USUARIO = "Sem usuário registrado"
MIN_NOME_BASE = 3


def limpar_texto_sensivel(texto: Any) -> str:
    """Remove e-mails e telefones de textos livres."""
    if not texto:
        return ""
    limpo = EMAIL_PATTERN.sub("[E-MAIL OCULTADO]", str(texto))
    return PHONE_PATTERN.sub("[TELEFONE OCULTADO]", limpo).strip()


class Mascara:
    """Troca valores sensíveis por marcadores e desfaz a troca quando preciso."""

    def __init__(self) -> None:
        self._por_valor: Dict[str, str] = {}
        self._por_marcador: Dict[str, str] = {}
        self._base: List[str] = []
        self._busca: Optional[Tuple[re.Pattern, Dict[str, str]]] = None

    def _marcador(self, valor: str) -> str:
        chave = valor.strip()
        if chave not in self._por_valor:
            marcador = f"[PESSOA_{len(self._por_valor) + 1}]"
            self._por_valor[chave] = marcador
            self._por_marcador[marcador] = chave
            self._busca = None
        return self._por_valor[chave]

    def registrar_base(self, nomes: List[str]) -> None:
        """Nomes da base do Simpress: viram marcadores já no início e sobrevivem a `limpar()`."""
        # Nomes de 1–2 letras ("TI") trocariam pedaços comuns do texto.
        self._base = [n.strip() for n in nomes if len(n.strip()) >= MIN_NOME_BASE and n.strip() != SEM_USUARIO]
        for nome in self._base:
            self._marcador(nome)

    def mascarar(self, obj: Any, chave: str = "") -> Any:
        """Devolve cópia de `obj` com valores sensíveis trocados por marcadores.

        Primeiro registra todos os valores sensíveis do resultado, para que uma
        anotação que cite o nome seja mascarada mesmo vindo antes do campo do usuário.
        """
        self._registrar(obj, chave)
        return self._trocar(obj, chave)

    def _registrar(self, obj: Any, chave: str = "") -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                self._registrar(v, str(k).lower())
        elif isinstance(obj, (list, tuple)):
            for v in obj:
                self._registrar(v, chave)
        elif isinstance(obj, str) and chave in CHAVES_SENSIVEIS and obj.strip() and obj != SEM_USUARIO:
            self._marcador(obj)

    def _trocar(self, obj: Any, chave: str) -> Any:
        if isinstance(obj, dict):
            return {k: self._trocar(v, str(k).lower()) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [self._trocar(v, chave) for v in obj]
        if isinstance(obj, str):
            if chave in CHAVES_SENSIVEIS and obj.strip() and obj != SEM_USUARIO:
                return self._marcador(obj)
            limpo = limpar_texto_sensivel(obj)
            return self.ocultar_conhecidos(limpo) if chave in CHAVES_TEXTO_LIVRE else limpo
        return obj

    def ocultar_conhecidos(self, texto: str) -> str:
        """Troca por marcador os valores já conhecidos que aparecem no texto (palavra inteira).

        shortcut: só reconhece nomes já vistos nesta conversa; um nome nunca
        consultado, digitado ou citado em anotação, segue como está.
        """
        if not self._por_valor:
            return texto
        if self._busca is None:
            # Uma expressão só (a base pode ter milhares de nomes); mais longos primeiro: "Maria Souza" antes de "Maria".
            valores = sorted(self._por_valor, key=len, reverse=True)
            padrao = r"(?<!\w)(?:" + "|".join(re.escape(v) for v in valores) + r")(?!\w)"
            self._busca = (re.compile(padrao, re.IGNORECASE), {v.casefold(): m for v, m in self._por_valor.items()})
        busca, por_valor = self._busca
        return busca.sub(lambda m: por_valor.get(m.group(0).casefold(), m.group(0)), texto)

    def restaurar(self, obj: Any) -> Any:
        """Troca marcadores conhecidos pelo valor real, em texto, dict ou lista."""
        if isinstance(obj, dict):
            return {k: self.restaurar(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [self.restaurar(v) for v in obj]
        if isinstance(obj, str):
            return TOKEN_PATTERN.sub(lambda m: self._por_marcador.get(m.group(0), m.group(0)), obj)
        return obj

    @staticmethod
    def tem_marcador(obj: Any) -> bool:
        """True se sobrou algum marcador sem valor real (inventado pelo modelo)."""
        if isinstance(obj, dict):
            return any(Mascara.tem_marcador(v) for v in obj.values())
        if isinstance(obj, (list, tuple)):
            return any(Mascara.tem_marcador(v) for v in obj)
        return isinstance(obj, str) and bool(TOKEN_PATTERN.search(obj))

    def limpar(self) -> None:
        self._por_valor.clear()
        self._por_marcador.clear()
        self._busca = None
        for nome in self._base:
            self._marcador(nome)
