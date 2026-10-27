"""Tokens e folha de estilo do HUD do Jarvis (só vale para o Jarvis, não para o Simpress web)."""

import os

BG = "#0B1320"
SURFACE = "#111C2E"
SURFACE_ALT = "#16253B"
BORDER = "#1F3550"          # divisor decorativo
BORDER_STRONG = "#5B7CA3"   # contorno de campos e botões (≥ 3:1)
CYAN = "#40CFFF"
CYAN_HOVER = "#7BDCFF"
CYAN_PRESSED = "#2BA8D6"
TEXT = "#E6F1FF"
TEXT_SECONDARY = "#9FB3C8"
SUCCESS = "#3DDC97"
WARNING = "#FFB547"
ERROR = "#FF5C7A"
ON_CYAN = "#06101C"          # texto sobre botão ciano
BALAO_EU = "#1B3350"         # balão das mensagens do usuário

SP = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24}
RAIO = {"sm": 6, "md": 10}
FONTE = "'Segoe UI', Arial, sans-serif"

# (primeiro plano, fundo, mínimo exigido, descrição)
PARES_CONTRASTE = [
    (TEXT, BG, 4.5, "texto sobre fundo"),
    (TEXT, SURFACE, 4.5, "texto sobre superfície"),
    (TEXT, SURFACE_ALT, 4.5, "texto sobre superfície alta"),
    (TEXT_SECONDARY, BG, 4.5, "texto secundário sobre fundo"),
    (TEXT_SECONDARY, SURFACE, 4.5, "texto secundário sobre superfície"),
    (TEXT_SECONDARY, SURFACE_ALT, 4.5, "texto secundário sobre superfície alta"),
    (CYAN, BG, 4.5, "ciano sobre fundo"),
    (CYAN, SURFACE, 4.5, "ciano sobre superfície"),
    (ON_CYAN, CYAN, 4.5, "texto do botão primário"),
    (ON_CYAN, CYAN_HOVER, 4.5, "botão primário em hover"),
    (ON_CYAN, CYAN_PRESSED, 4.5, "botão primário pressionado"),
    (SUCCESS, SURFACE, 4.5, "sucesso sobre superfície"),
    (WARNING, SURFACE, 4.5, "alerta sobre superfície"),
    (ERROR, SURFACE, 4.5, "erro sobre superfície"),
    (BORDER_STRONG, SURFACE, 3.0, "contorno de campo"),
    (BORDER_STRONG, BG, 3.0, "contorno sobre fundo"),
    (CYAN, SURFACE, 3.0, "anel de foco"),
    (TEXT, BALAO_EU, 4.5, "texto no balão do usuário"),
    (TEXT_SECONDARY, BALAO_EU, 4.5, "nome no balão do usuário"),
    (CYAN, SURFACE_ALT, 4.5, "cabeçalho de cartão de resposta"),
    (SUCCESS, BG, 4.5, "exportação concluída na conversa"),
    (ERROR, BG, 3.0, "anel do orbe ouvindo"),
]


def _lin(c: int) -> float:
    v = c / 255
    return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4


def luminancia(hex_cor: str) -> float:
    h = hex_cor.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contraste(a: str, b: str) -> float:
    la, lb = sorted((luminancia(a), luminancia(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def movimento_reduzido() -> bool:
    return os.environ.get("JARVIS_REDUZIR_MOVIMENTO", "").strip() in ("1", "true", "sim")


def duracao(ms: int = 200) -> int:
    """Duração das animações (150–300 ms); 0 quando o movimento está reduzido."""
    return 0 if movimento_reduzido() else max(150, min(300, ms))


def qss() -> str:
    return f"""
QWidget {{ color: {TEXT}; font-family: {FONTE}; font-size: 10pt; }}
QMainWindow, QWidget#raiz {{ background: {BG}; }}
QToolTip {{ background: {SURFACE_ALT}; color: {TEXT}; border: 1px solid {BORDER_STRONG}; padding: 4px 8px; }}

QFrame#hud {{ background: {SURFACE}; border-bottom: 1px solid {BORDER}; }}
QFrame#menu {{ background: {SURFACE}; border-right: 1px solid {BORDER}; }}
QFrame#chat {{ background: {BG}; }}
QFrame#status {{ background: {SURFACE}; border-right: 1px solid {BORDER}; }}
QTextBrowser#conversa {{ font-size: 11pt; border: none; }}
QLineEdit#entrada {{ font-size: 11pt; padding: 8px {SP['md']}px; }}
QPushButton[papel="status"] {{ text-align: left; padding: {SP['sm']}px {SP['md']}px; background: {SURFACE_ALT}; }}
QPushButton[papel="status"][nivel="aviso"] {{ border-left: 3px solid {WARNING}; }}
QPushButton[papel="status"][nivel="erro"] {{ border-left: 3px solid {ERROR}; }}
QPushButton[papel="status"][nivel="ok"] {{ border-left: 3px solid {SUCCESS}; }}
QLabel#escutando {{ color: {SUCCESS}; }}
QFrame#rodape {{ background: {SURFACE}; border-top: 1px solid {BORDER}; }}

QLabel#logo {{ color: {CYAN}; font-size: 14pt; font-weight: 700; letter-spacing: 2px; }}
QLabel#secundario {{ color: {TEXT_SECONDARY}; }}
QLabel#titulo {{ font-size: 12pt; font-weight: 600; }}

QPushButton {{ background: {SURFACE_ALT}; border: 1px solid {BORDER_STRONG}; border-radius: {RAIO['sm']}px;
    padding: 6px {SP['md']}px; min-height: 22px; }}
QPushButton:hover {{ border-color: {CYAN}; }}
QPushButton:pressed {{ background: {BG}; }}
QPushButton:focus {{ border: 2px solid {CYAN}; }}
QPushButton:disabled {{ color: {TEXT_SECONDARY}; border-color: {BORDER}; }}
QPushButton[papel="primario"] {{ background: {CYAN}; color: {ON_CYAN}; border-color: {CYAN}; font-weight: 600; }}
QPushButton[papel="primario"]:hover {{ background: {CYAN_HOVER}; }}
QPushButton[papel="primario"]:pressed {{ background: {CYAN_PRESSED}; }}
QPushButton[papel="primario"]:disabled {{ background: {BORDER}; color: {TEXT_SECONDARY}; }}
QPushButton[papel="fantasma"] {{ background: transparent; border-color: transparent; }}
QPushButton[papel="fantasma"]:hover {{ border-color: {BORDER_STRONG}; }}
QPushButton[papel="chip"] {{ background: {SURFACE_ALT}; border-radius: 12px; padding: 4px 10px; min-height: 18px; }}
QPushButton[papel="menu"] {{ text-align: left; background: transparent; border: 1px solid transparent; padding: 8px {SP['md']}px; }}
QPushButton[papel="menu"]:hover {{ background: {SURFACE_ALT}; }}
QPushButton[papel="menu"][ativo="true"] {{ background: {SURFACE_ALT}; border-left: 3px solid {CYAN}; color: {CYAN}; }}
QPushButton[papel="menu"]:focus {{ border: 2px solid {CYAN}; }}

QLineEdit, QComboBox {{ background: {BG}; border: 1px solid {BORDER_STRONG}; border-radius: {RAIO['sm']}px;
    padding: 6px {SP['sm']}px; selection-background-color: {CYAN}; selection-color: {ON_CYAN}; }}
QLineEdit:focus, QComboBox:focus {{ border: 2px solid {CYAN}; }}
QComboBox QAbstractItemView {{ background: {SURFACE_ALT}; border: 1px solid {BORDER_STRONG};
    selection-background-color: {CYAN}; selection-color: {ON_CYAN}; }}

QMenu {{ background: {SURFACE_ALT}; color: {TEXT}; border: 1px solid {BORDER_STRONG}; padding: 4px; }}
QMenu::item {{ padding: 6px {SP['lg']}px 6px 28px; border-radius: 4px; }}
QMenu::item:selected {{ background: {CYAN}; color: {ON_CYAN}; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 4px 8px; }}

QTextBrowser {{ background: {BG}; border: 1px solid {BORDER}; border-radius: {RAIO['sm']}px; padding: {SP['sm']}px; }}
QTextBrowser:focus {{ border: 2px solid {CYAN}; }}

QFrame#cartao_confirmacao {{ background: {SURFACE_ALT}; border: 2px solid {WARNING}; border-radius: {RAIO['md']}px; }}
QLabel#aviso {{ color: {WARNING}; font-weight: 600; }}

QScrollBar:vertical {{ background: {BG}; width: 10px; }}
QScrollBar::handle:vertical {{ background: {BORDER_STRONG}; border-radius: 5px; min-height: 24px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}
"""
