"""Mascaramento reversível de dados pessoais (LGPD) entre o Jarvis e a IA.

Valores sensíveis (usuário logado, apelido, nomes) viram marcadores como
`[PESSOA_1]` antes de ir ao modelo. O mapa vive só na memória do processo e
nunca é gravado. Os marcadores voltam ao valor real nos argumentos das
ferramentas e no texto mostrado na tela. A voz usa o texto mascarado.
"""

import re
from typing import Any, Dict

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
})


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

    def _marcador(self, valor: str) -> str:
        chave = valor.strip()
        if chave not in self._por_valor:
            marcador = f"[PESSOA_{len(self._por_valor) + 1}]"
            self._por_valor[chave] = marcador
            self._por_marcador[marcador] = chave
        return self._por_valor[chave]

    def mascarar(self, obj: Any, chave: str = "") -> Any:
        """Devolve cópia de `obj` com valores sensíveis trocados por marcadores."""
        if isinstance(obj, dict):
            return {k: self.mascarar(v, str(k).lower()) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [self.mascarar(v, chave) for v in obj]
        if isinstance(obj, str):
            if chave in CHAVES_SENSIVEIS and obj.strip() and obj != "Sem usuário registrado":
                return self._marcador(obj)
            return limpar_texto_sensivel(obj)
        return obj

    def ocultar_conhecidos(self, texto: str) -> str:
        """Troca por marcador os valores já conhecidos que o usuário digitou no texto."""
        for valor, marcador in self._por_valor.items():
            texto = re.sub(re.escape(valor), marcador, texto, flags=re.IGNORECASE)
        return texto

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
