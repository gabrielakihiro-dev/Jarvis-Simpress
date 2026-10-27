"""Interface Gráfica Futurista do Jarvis para Simpress (baseada em PyQt5).

Inspirada no projeto Jarvis de Rahees Ahmed, adaptada para o ambiente corporativo
da Simpress com suporte a OpenRouter, síntese de voz (Edge-TTS) e execução assíncrona
em segundo plano (QThread) para que a interface NUNCA congele.
"""

import html
import os
import re
import sys
from typing import List, Optional

from dotenv import load_dotenv
from PyQt5.QtCore import Qt, QSize, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QIcon, QPixmap, QTextCursor
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# Carrega variáveis de ambiente (.env)
load_dotenv()

from llm_client import LLMClient, MODELOS_CATALOGO
from simpress_client import SimpressClient
import voice

# --- PALETA DE CORES FUTURISTA (HUD SCI-FI) ---
COLOR_BG = "#0B1320"               # Fundo geral ultra escuro (Espaço Profundo)
COLOR_PANEL = "#111D33"            # Painel ligeiramente mais claro
COLOR_CARD_JARVIS = "#0E1A2D"      # Cartão de mensagem do Jarvis
COLOR_CARD_USER = "#16233B"        # Cartão de mensagem do Usuário
COLOR_INPUT_BG = "#15243F"         # Fundo do campo de texto
COLOR_TEXT_PRIMARY = "#E2E8F0"     # Texto principal claro e legível
COLOR_TEXT_MUTED = "#8E9EB5"       # Texto secundário / metadados
COLOR_ACCENT = "#40CFFF"           # Ciano Neon clássico do Jarvis
COLOR_ACCENT_HOVER = "#6CE5FF"     # Ciano brilhante ao passar o mouse
COLOR_ACCENT_PRESSED = "#1FA8D4"   # Ciano escuro ao clicar
COLOR_BORDER = "#1F355B"           # Borda suave de componentes
COLOR_BORDER_FOCUS = "#40CFFF"     # Borda ciano ao focar no campo
COLOR_SUCCESS = "#10B981"          # Verde esmeralda para online
COLOR_DANGER = "#EF4444"           # Vermelho para offline/erro
COLOR_BADGE_BG = "#132D48"         # Fundo para badges de ferramentas
COLOR_BADGE_BORDER = "#2563EB"     # Borda de badges

# Folha de Estilos Futurista (Qt Style Sheet)
FUTURISTIC_STYLESHEET = f"""
QMainWindow {{
    background-color: {COLOR_BG};
}}

QWidget {{
    color: {COLOR_TEXT_PRIMARY};
    font-family: 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif;
    font-size: 10pt;
}}

/* Barra Superior e Painéis */
QFrame#headerFrame {{
    background-color: {COLOR_PANEL};
    border-bottom: 2px solid {COLOR_BORDER};
    padding: 8px 16px;
}}

QFrame#statusFrame {{
    background-color: {COLOR_PANEL};
    border-top: 1px solid {COLOR_BORDER};
    padding: 4px 12px;
}}

/* Área de Conversa */
QTextEdit#chatArea {{
    background-color: {COLOR_BG};
    border: 1px solid {COLOR_BORDER};
    border-radius: 12px;
    padding: 14px;
    font-size: 11pt;
    line-height: 1.5;
    selection-background-color: {COLOR_ACCENT};
    selection-color: {COLOR_BG};
}}

/* Campo de Digitação */
QLineEdit#inputField {{
    background-color: {COLOR_INPUT_BG};
    border: 1.5px solid {COLOR_BORDER};
    border-radius: 20px;
    padding: 0 18px;
    font-size: 11pt;
    color: {COLOR_TEXT_PRIMARY};
    min-height: 42px;
}}

QLineEdit#inputField:focus {{
    border: 1.5px solid {COLOR_BORDER_FOCUS};
    background-color: #1A2C4D;
}}

QLineEdit#inputField:disabled {{
    background-color: #0E1726;
    color: {COLOR_TEXT_MUTED};
    border-color: #17243B;
}}

/* Botões Principais */
QPushButton#btnSend {{
    background-color: {COLOR_ACCENT};
    color: {COLOR_BG};
    border: none;
    border-radius: 21px;
    padding: 0 24px;
    min-height: 42px;
    font-weight: bold;
    font-size: 10pt;
    letter-spacing: 1px;
}}

QPushButton#btnSend:hover {{
    background-color: {COLOR_ACCENT_HOVER};
}}

QPushButton#btnSend:pressed {{
    background-color: {COLOR_ACCENT_PRESSED};
}}

QPushButton#btnSend:disabled {{
    background-color: #2D3E57;
    color: #6C7E96;
}}

/* Botões de Ação Secundários */
QPushButton.btnSecondary {{
    background-color: {COLOR_INPUT_BG};
    color: {COLOR_ACCENT};
    border: 1px solid {COLOR_BORDER};
    border-radius: 14px;
    padding: 6px 14px;
    font-size: 9pt;
    font-weight: 600;
}}

QPushButton.btnSecondary:hover {{
    background-color: #1E3357;
    border-color: {COLOR_ACCENT};
    color: #FFFFFF;
}}

/* Chips de Ação Rápida */
QPushButton.chipButton {{
    background-color: {COLOR_PANEL};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER};
    border-radius: 15px;
    padding: 5px 14px;
    font-size: 9pt;
}}

QPushButton.chipButton:hover {{
    border-color: {COLOR_ACCENT};
    color: {COLOR_ACCENT};
    background-color: #162645;
}}

/* Seletor de Modelo */
QComboBox {{
    background-color: {COLOR_INPUT_BG};
    border: 1px solid {COLOR_BORDER};
    border-radius: 14px;
    padding: 4px 12px;
    min-height: 28px;
    color: {COLOR_TEXT_PRIMARY};
    font-size: 9pt;
}}

QComboBox:hover {{
    border-color: {COLOR_ACCENT};
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox QAbstractItemView {{
    background-color: {COLOR_PANEL};
    border: 1px solid {COLOR_ACCENT};
    color: {COLOR_TEXT_PRIMARY};
    selection-background-color: {COLOR_ACCENT};
    selection-color: {COLOR_BG};
    padding: 4px;
}}

/* Barra de Rolagem Moderna */
QScrollBar:vertical {{
    border: none;
    background: {COLOR_BG};
    width: 8px;
    margin: 0px;
}}

QScrollBar::handle:vertical {{
    background: {COLOR_BORDER};
    min-height: 25px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical:hover {{
    background: {COLOR_ACCENT};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
"""


class AgentWorker(QThread):
    """Thread em segundo plano que executa as chamadas do agente para nunca travar a interface."""

    status_changed = pyqtSignal(str)
    response_ready = pyqtSignal(str, list)
    error_occurred = pyqtSignal(str)

    def __init__(self, user_input: str, llm_client: LLMClient, falar_audio: bool):
        super().__init__()
        self.user_input = user_input
        self.llm_client = llm_client
        self.falar_audio = falar_audio

    def run(self):
        try:
            self.status_changed.emit("⚡ Jarvis está consultando os sistemas...")

            def callback_status(msg: str):
                # Limpa tags rich caso venha da engine interna
                msg_limpa = re.sub(r"\[/?(cyan|green|yellow|red|bold)\]", "", msg)
                self.status_changed.emit(f"🔧 {msg_limpa}")

            resposta_texto, ferramentas = self.llm_client.enviar_mensagem(
                self.user_input, callback_status=callback_status
            )

            # Se a voz estiver habilitada, dispara síntese em segundo plano
            if self.falar_audio and resposta_texto:
                self.status_changed.emit("🔊 Sintetizando resposta em áudio...")
                voice.falar(resposta_texto)

            self.response_ready.emit(resposta_texto, ferramentas)
        except Exception as e:
            self.error_occurred.emit(str(e))


class JarvisUIWindow(QMainWindow):
    """Janela principal do Jarvis Simpress com estética HUD e arquitetura assíncrona."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("J.A.R.V.I.S — Assistente Operacional Simpress")
        self.resize(1080, 800)
        self.setMinimumSize(850, 600)

        # Inicializa clientes de dados
        self.simpress_client = SimpressClient()
        self.llm_client = LLMClient(self.simpress_client)
        self.voz_habilitada = voice.HABILITAR_VOZ
        self.worker: Optional[AgentWorker] = None

        # Configura ícone da janela se existir
        icone_path = os.path.join(os.path.dirname(__file__), "icons", "jarvis_logo.png")
        if os.path.exists(icone_path):
            self.setWindowIcon(QIcon(icone_path))

        self.init_ui()
        self.verificar_conexao_simpress()

        # Timer para verificar conexão com o Simpress a cada 30 segundos
        self.timer_status = QTimer(self)
        self.timer_status.timeout.connect(self.verificar_conexao_simpress)
        self.timer_status.start(30000)

    def init_ui(self):
        """Constrói a interface com cabeçalho HUD, chat, chips rápidos e input."""
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(10)

        # 1. CABEÇALHO HUD (Barra Superior)
        header_frame = QFrame()
        header_frame.setObjectName("headerFrame")
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(12, 8, 12, 8)
        header_layout.setSpacing(14)

        # Logo / Título
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        lbl_title = QLabel("J.A.R.V.I.S // SIMPRESS CORE")
        lbl_title.setStyleSheet(f"font-size: 14pt; font-weight: bold; color: {COLOR_ACCENT}; letter-spacing: 1.5px;")
        lbl_sub = QLabel("Assistente Inteligente do Parque de Computadores & Chamados")
        lbl_sub.setStyleSheet(f"font-size: 8.5pt; color: {COLOR_TEXT_MUTED};")
        title_box.addWidget(lbl_title)
        title_box.addWidget(lbl_sub)
        header_layout.addLayout(title_box)

        header_layout.addStretch(1)

        # Status Simpress
        self.lbl_simpress_status = QLabel("⚪ Verificando Simpress...")
        self.lbl_simpress_status.setStyleSheet(f"font-size: 9pt; font-weight: 600; color: {COLOR_TEXT_MUTED};")
        header_layout.addWidget(self.lbl_simpress_status)

        # Seletor de Modelo OpenRouter
        self.combo_modelo = QComboBox()
        for key, (mod_id, rotulo) in MODELOS_CATALOGO.items():
            self.combo_modelo.addItem(f"{key}: {rotulo.split('(')[0].strip()}", mod_id)
        self.combo_modelo.setCurrentIndex(0)
        self.combo_modelo.currentIndexChanged.connect(self.ao_mudar_modelo)
        header_layout.addWidget(self.combo_modelo)

        # Botão Voz (Áudio On/Off)
        self.btn_voz = QPushButton("🔊 ÁUDIO ATIVO" if self.voz_habilitada else "🔇 MUDO")
        self.btn_voz.setProperty("class", "btnSecondary")
        self.btn_voz.setCursor(Qt.PointingHandCursor)
        self.btn_voz.clicked.connect(self.alternar_voz_ui)
        header_layout.addWidget(self.btn_voz)

        # Botão Limpar Memória
        btn_limpar = QPushButton("🗑️ LIMPAR")
        btn_limpar.setProperty("class", "btnSecondary")
        btn_limpar.setCursor(Qt.PointingHandCursor)
        btn_limpar.clicked.connect(self.limpar_historico_ui)
        header_layout.addWidget(btn_limpar)

        main_layout.addWidget(header_frame)

        # 2. ÁREA CENTRAL DE CONVERSA
        self.chat_area = QTextEdit()
        self.chat_area.setObjectName("chatArea")
        self.chat_area.setReadOnly(True)
        main_layout.addWidget(self.chat_area, 1)

        # 3. BARRA DE CHIPS DE AÇÕES RÁPIDAS
        chips_layout = QHBoxLayout()
        chips_layout.setSpacing(6)

        chips = [
            ("🌐 Chrome Login", "Abra o Google Chrome de automação para que eu possa fazer o login manualmente."),
            ("📦 Inventários", "Execute a rotina de automação de inventários no Chrome."),
            ("🎫 OS & Chamados", "Execute a rotina de automação de chamados e ordens de serviço (OS) no Chrome."),
            ("⚡ Ambas as Rotinas", "Execute ambas as rotinas de automação (OS e Inventários em sequência) no Chrome."),
            ("👥 Verificar Usuários", "Execute a rotina de verificação de usuários logados."),
            ("📊 Totais", "Qual é o total oficial de equipamentos e unidades no Simpress?"),
            ("🛑 Cancelar Rotina", "Cancele a rotina de automação que estiver em andamento."),
        ]

        for rotulo, prompt in chips:
            btn_chip = QPushButton(rotulo)
            btn_chip.setProperty("class", "chipButton")
            btn_chip.setCursor(Qt.PointingHandCursor)
            btn_chip.clicked.connect(lambda checked, p=prompt: self.enviar_prompt_rapido(p))
            chips_layout.addWidget(btn_chip)

        chips_layout.addStretch(1)
        main_layout.addLayout(chips_layout)

        # 4. ÁREA DE ENTRADA (Input + Botão Enviar)
        input_layout = QHBoxLayout()
        input_layout.setSpacing(10)

        self.input_field = QLineEdit()
        self.input_field.setObjectName("inputField")
        self.input_field.setPlaceholderText("Faça uma pergunta sobre equipamentos, chamados técnicos ou automações (pressione Enter)...")
        self.input_field.returnPressed.connect(self.enviar_mensagem_ui)
        input_layout.addWidget(self.input_field, 1)

        self.btn_send = QPushButton("ENVIAR ⚡")
        self.btn_send.setObjectName("btnSend")
        self.btn_send.setCursor(Qt.PointingHandCursor)
        self.btn_send.clicked.connect(self.enviar_mensagem_ui)
        input_layout.addWidget(self.btn_send)

        main_layout.addLayout(input_layout)

        # 5. BARRA DE STATUS INFERIOR (HUD FOOTER)
        status_frame = QFrame()
        status_frame.setObjectName("statusFrame")
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(8, 4, 8, 4)

        self.lbl_status = QLabel("● Sistema operacional online. Pronto para comandos.")
        self.lbl_status.setStyleSheet(f"font-size: 8.5pt; color: {COLOR_TEXT_MUTED};")
        status_layout.addWidget(self.lbl_status)

        status_layout.addStretch(1)

        self.lbl_info = QLabel("OpenRouter AI • Loopback Seguro 127.0.0.1 • LGPD Sanitized")
        self.lbl_info.setStyleSheet(f"font-size: 8pt; color: {COLOR_BORDER};")
        status_layout.addWidget(self.lbl_info)

        main_layout.addWidget(status_frame)

        # Aplica Stylesheet Global
        self.setStyleSheet(FUTURISTIC_STYLESHEET)

        # Mensagem inicial de boas-vindas do Jarvis
        self.exibir_boas_vindas()

    def exibir_boas_vindas(self):
        """Apresenta a saudação inicial do Jarvis no chat."""
        msg_inicial = (
            "**Sistemas online.** Olá, sou o **Jarvis**, assistente do inventário e chamados da Simpress.<br><br>"
            "Você pode me comandar por texto ou voz para:<br>"
            "• **Automações no Chrome:** abrir o Chrome para login manual, rodar **Inventários**, **OS & Chamados**, **Ambas** ou **Verificar Usuários**.<br>"
            "• **Equipamentos:** consultar localização por número de série (ex: `CMVXKV7YCM`), modelo e usuário logado.<br>"
            "• **Operações & Inventário:** métricas oficiais, chamados abertos, pendências de exportação e cruzamento Simpress vs Endpoint."
        )
        self.append_message("JARVIS", msg_inicial, is_jarvis=True)

    def verificar_conexao_simpress(self):
        """Testa se a API local do Simpress (127.0.0.1:8000) está respondendo."""
        try:
            stats = self.simpress_client.obter_totais_inventario()
            if "erro" not in stats and stats.get("total_equipamentos_oficial", 0) > 0:
                total = stats.get("total_equipamentos_oficial", 0)
                self.lbl_simpress_status.setText(f"🟢 Simpress Online ({total} equipamentos)")
                self.lbl_simpress_status.setStyleSheet(f"font-size: 9pt; font-weight: bold; color: {COLOR_SUCCESS};")
            elif "erro" not in stats:
                self.lbl_simpress_status.setText("🟢 Simpress Online (127.0.0.1:8000)")
                self.lbl_simpress_status.setStyleSheet(f"font-size: 9pt; font-weight: bold; color: {COLOR_SUCCESS};")
            else:
                self.lbl_simpress_status.setText("🔴 Simpress Desconectado (Inicie o servidor)")
                self.lbl_simpress_status.setStyleSheet(f"font-size: 9pt; font-weight: bold; color: {COLOR_DANGER};")
        except Exception:
            self.lbl_simpress_status.setText("🔴 Simpress Offline")
            self.lbl_simpress_status.setStyleSheet(f"font-size: 9pt; font-weight: bold; color: {COLOR_DANGER};")

    def formatar_markdown_html(self, texto: str) -> str:
        """Converte marcações comuns (negrito, itálico, listas, tabelas) em HTML estilizado."""
        if not texto:
            return ""

        # Escapa caracteres perigosos de HTML inicial
        t = html.escape(texto)

        # Blocos de código ```codigo```
        t = re.sub(
            r"```(.*?)```",
            r"<pre style='background:#070E1A; border:1px solid #1E293B; border-radius:6px; padding:8px; color:#38BDF8; font-family:monospace; font-size:9.5pt;'>\1</pre>",
            t,
            flags=re.DOTALL,
        )

        # Código em linha `codigo`
        t = re.sub(
            r"`([^`]+)`",
            r"<code style='background:#17253D; color:#38BDF8; padding:2px 5px; border-radius:4px; font-family:monospace;'>\1</code>",
            t,
        )

        # Negrito **texto**
        t = re.sub(r"\*\*([^*]+)\*\*", r"<strong style='color:#FFFFFF;'>\1</strong>", t)

        # Itálico *texto*
        t = re.sub(r"\*([^*]+)\*", r"<em style='color:#CBD5E1;'>\1</em>", t)

        # Itens de lista • ou -
        t = re.sub(r"^[-•]\s+(.*)$", r"<li style='margin-left:16px; margin-bottom:4px;'>\1</li>", t, flags=re.MULTILINE)

        # Quebras de linha normais
        t = t.replace("\n", "<br>")

        return t

    def append_message(self, sender: str, message: str, is_jarvis: bool = False, ferramentas: Optional[List[str]] = None):
        """Adiciona um bloco de mensagem estilizado em forma de cartão no chat."""
        if not message:
            return

        formatted_body = self.formatar_markdown_html(message)

        # Constrói badges visuais para ferramentas executadas
        badges_html = ""
        if ferramentas:
            badges = []
            for fn in ferramentas:
                badges.append(
                    f"<span style='background-color:{COLOR_BADGE_BG}; color:{COLOR_ACCENT}; border:1px solid {COLOR_BADGE_BORDER}; border-radius:4px; padding:2px 7px; font-size:8.5pt; font-weight:600;'>🔧 {fn}</span>"
                )
            badges_html = f"<div style='margin-top:8px;'>{' '.join(badges)}</div>"

        if is_jarvis:
            card_html = f"""
            <div style='margin-bottom: 16px; background-color: {COLOR_CARD_JARVIS}; border-left: 4px solid {COLOR_ACCENT}; border-radius: 8px; padding: 12px 16px;'>
                <div style='font-weight: bold; color: {COLOR_ACCENT}; font-size: 10.5pt; letter-spacing: 0.5px;'>
                    ⚡ {sender}
                </div>
                <div style='color: {COLOR_TEXT_PRIMARY}; margin-top: 6px; font-size: 10pt; line-height: 1.5;'>
                    {formatted_body}
                </div>
                {badges_html}
            </div>
            """
        else:
            card_html = f"""
            <div style='margin-bottom: 16px; background-color: {COLOR_CARD_USER}; border-right: 4px solid #60A5FA; border-radius: 8px; padding: 12px 16px;'>
                <div style='font-weight: bold; color: #93C5FD; font-size: 10.5pt; text-align: right;'>
                    👤 VOCÊ
                </div>
                <div style='color: #F8FAFC; margin-top: 6px; font-size: 10pt; line-height: 1.5;'>
                    {formatted_body}
                </div>
            </div>
            """

        self.chat_area.append(card_html)
        self.chat_area.moveCursor(QTextCursor.End)

    def enviar_prompt_rapido(self, prompt: str):
        """Dispara imediatamente um prompt a partir de um chip de atalho."""
        self.input_field.setText(prompt)
        self.enviar_mensagem_ui()

    def enviar_mensagem_ui(self):
        """Processa o envio da mensagem do usuário sem travar a interface."""
        texto = self.input_field.text().strip()
        if not texto:
            return

        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "Aguarde", "O Jarvis ainda está processando a requisição anterior.")
            return

        # Adiciona a mensagem do usuário na tela
        self.append_message("VOCÊ", texto, is_jarvis=False)
        self.input_field.clear()
        self.set_interacao_ativa(False)

        # Inicia a thread trabalhadora em segundo plano
        self.worker = AgentWorker(texto, self.llm_client, self.voz_habilitada)
        self.worker.status_changed.connect(self.ao_atualizar_status)
        self.worker.response_ready.connect(self.ao_receber_resposta)
        self.worker.error_occurred.connect(self.ao_ocorrer_erro)
        self.worker.finished.connect(self.ao_finalizar_worker)
        self.worker.start()

    def ao_atualizar_status(self, msg: str):
        """Atualiza a mensagem da barra inferior durante o processamento."""
        self.lbl_status.setText(f"● {msg}")

    def ao_receber_resposta(self, resposta: str, ferramentas: list):
        """Exibe a resposta do Jarvis com os badges de ferramentas consultadas."""
        self.append_message("JARVIS", resposta, is_jarvis=True, ferramentas=ferramentas)

    def ao_ocorrer_erro(self, msg_erro: str):
        """Exibe o erro de forma clara sem quebrar o aplicativo."""
        self.append_message("JARVIS", f"⚠️ Ocorreu uma instabilidade: {msg_erro}", is_jarvis=True)

    def ao_finalizar_worker(self):
        """Restaura o estado da interface ao término do processamento."""
        self.set_interacao_ativa(True)
        modelo_nome = self.combo_modelo.currentText().split(":")[1].strip() if ":" in self.combo_modelo.currentText() else "DeepSeek"
        self.lbl_status.setText(f"● Pronto | Modelo ativo: {modelo_nome}")
        self.input_field.setFocus()

    def set_interacao_ativa(self, ativa: bool):
        """Habilita ou desabilita campos de entrada para evitar conflito de requisições."""
        self.input_field.setEnabled(ativa)
        self.btn_send.setEnabled(ativa)
        if ativa:
            self.input_field.setPlaceholderText("Faça uma pergunta sobre equipamentos, chamados ou automações...")
        else:
            self.input_field.setPlaceholderText("⚡ JARVIS está processando sua solicitação...")

    def ao_mudar_modelo(self, index: int):
        """Altera dinamicamente o modelo de IA do OpenRouter."""
        mod_id = self.combo_modelo.itemData(index)
        if mod_id:
            self.llm_client.trocar_modelo(mod_id)
            self.lbl_status.setText(f"● Modelo alterado para: {mod_id}")

    def alternar_voz_ui(self):
        """Liga ou desliga a síntese de voz (TTS)."""
        self.voz_habilitada = not self.voz_habilitada
        voice.alternar_voz(self.voz_habilitada)
        if self.voz_habilitada:
            self.btn_voz.setText("🔊 ÁUDIO ATIVO")
            self.lbl_status.setText("● Síntese de voz ativada.")
        else:
            self.btn_voz.setText("🔇 MUDO")
            self.lbl_status.setText("● Áudio desativado (somente texto).")

    def limpar_historico_ui(self):
        """Limpa a janela de conversa e a memória do modelo."""
        self.llm_client.limpar_historico()
        self.chat_area.clear()
        self.exibir_boas_vindas()
        self.lbl_status.setText("● Memória da conversa reiniciada.")


def main():
    """Ponto de entrada para inicialização da aplicação PyQt5."""
    app = QApplication(sys.argv)
    window = JarvisUIWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
