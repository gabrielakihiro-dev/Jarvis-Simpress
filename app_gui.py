"""Interface Gráfica Moderna (GUI) para o Jarvis Simpress.

Construída com CustomTkinter para Windows 11 com tema escuro,
painel lateral de atalhos, seleção de modelos e reprodução de voz assíncrona.
"""

import os
import sys
import threading
from typing import List, Optional

import customtkinter as ctk
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

from llm_client import LLMClient, MODELOS_CATALOGO
from simpress_client import SimpressClient
import voice

# Configurações visuais do CustomTkinter
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class JarvisGUI(ctk.CTk):
    """Janela principal do assistente Jarvis."""

    def __init__(self):
        super().__init__()

        self.title("Jarvis Simpress - Assistente Operacional")
        self.geometry("1100x720")
        self.minsize(850, 580)

        # Clientes de comunicação
        self.simpress = SimpressClient()
        self.llm = LLMClient(self.simpress)

        # Mapa de modelos para o combobox
        self.mapa_modelos = {
            desc: slug for slug, desc in MODELOS_CATALOGO.values()
        }
        # Adiciona os nomes amigáveis
        self.opcoes_modelos = list(self.mapa_modelos.keys())

        # Layout em Grid (Coluna 0: Barra lateral, Coluna 1: Chat)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._construir_barra_lateral()
        self._construir_area_chat()

        # Mensagem de boas-vindas inicial
        self._adicionar_mensagem_jarvis(
            "Olá! 👋 Sou o **Jarvis**, assistente inteligente do parque de equipamentos Simpress.\n\n"
            "Estou conectado para consultar máquinas por número de série, verificar chamados e ordens de serviço, acompanhar automações e métricas do inventário.\n\n"
            "Como posso te ajudar hoje?",
            ferramentas=[],
            falar_audio=False,
        )

        # Checagem inicial do Simpress
        self.after(500, self.verificar_status_simpress)

    def _construir_barra_lateral(self):
        """Cria a barra lateral de controles, atalhos e seleção de modelo."""
        self.sidebar = ctk.CTkFrame(self, width=280, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.sidebar.grid_rowconfigure(10, weight=1)

        # Título
        self.lbl_logo = ctk.CTkLabel(
            self.sidebar,
            text="🤖 JARVIS SIMPRESS",
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        self.lbl_logo.grid(row=0, column=0, padx=20, pady=(20, 5), sticky="w")

        self.lbl_sub = ctk.CTkLabel(
            self.sidebar,
            text="Inventário & Operações Locais",
            font=ctk.CTkFont(size=12),
            text_color="gray",
        )
        self.lbl_sub.grid(row=1, column=0, padx=20, pady=(0, 15), sticky="w")

        # Status do Simpress
        self.frame_status = ctk.CTkFrame(self.sidebar, fg_color="#1c1c1c", corner_radius=8)
        self.frame_status.grid(row=2, column=0, padx=15, pady=5, sticky="ew")

        self.lbl_status_simpress = ctk.CTkLabel(
            self.frame_status,
            text="● Verificando Simpress...",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#f39c12",
        )
        self.lbl_status_simpress.pack(side="left", padx=10, pady=8)

        self.btn_recheck = ctk.CTkButton(
            self.frame_status,
            text="↻",
            width=28,
            height=24,
            command=self.verificar_status_simpress,
            fg_color="#2b2b2b",
            hover_color="#3a3a3a",
        )
        self.btn_recheck.pack(side="right", padx=10, pady=8)

        # Seletor de Modelo de IA
        self.lbl_mod = ctk.CTkLabel(
            self.sidebar,
            text="Modelo de IA (OpenRouter):",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.lbl_mod.grid(row=3, column=0, padx=20, pady=(15, 5), sticky="w")

        # Seleciona o item correspondente ao modelo_principal atual
        modelo_atual_desc = next(
            (desc for desc, slug in self.mapa_modelos.items() if slug == self.llm.modelo_principal),
            self.opcoes_modelos[0],
        )

        self.combo_modelos = ctk.CTkComboBox(
            self.sidebar,
            values=self.opcoes_modelos,
            command=self._ao_trocar_modelo,
            width=240,
        )
        self.combo_modelos.set(modelo_atual_desc)
        self.combo_modelos.grid(row=4, column=0, padx=20, pady=(0, 10))

        # Switch de Voz
        self.switch_voz = ctk.CTkSwitch(
            self.sidebar,
            text="Falar Respostas (Voz)",
            command=self._ao_alternar_voz,
            font=ctk.CTkFont(size=13),
        )
        if voice.HABILITAR_VOZ:
            self.switch_voz.select()
        else:
            self.switch_voz.deselect()
        self.switch_voz.grid(row=5, column=0, padx=20, pady=10, sticky="w")

        # Separador de Atalhos
        self.lbl_atalhos = ctk.CTkLabel(
            self.sidebar,
            text="Consultas Rápidas:",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.lbl_atalhos.grid(row=6, column=0, padx=20, pady=(15, 5), sticky="w")

        self.btn_totais = ctk.CTkButton(
            self.sidebar,
            text="📊 Totais do Inventário",
            anchor="w",
            command=lambda: self.enviar_pergunta_direta("Quantos equipamentos temos no total hoje no cadastro oficial?"),
            fg_color="#23272d",
            hover_color="#313742",
        )
        self.btn_totais.grid(row=7, column=0, padx=20, pady=4, sticky="ew")

        self.btn_chamados = ctk.CTkButton(
            self.sidebar,
            text="⚠️ Chamados com Divergência",
            anchor="w",
            command=lambda: self.enviar_pergunta_direta("Quais chamados estão abertos e possuem ordens de serviço divergentes ou sem OS?"),
            fg_color="#23272d",
            hover_color="#313742",
        )
        self.btn_chamados.grid(row=8, column=0, padx=20, pady=4, sticky="ew")

        self.btn_automacao = ctk.CTkButton(
            self.sidebar,
            text="🔄 Status da Automação",
            anchor="w",
            command=lambda: self.enviar_pergunta_direta("Como está o status atual da automação do Chrome? Ela terminou ou está executando?"),
            fg_color="#23272d",
            hover_color="#313742",
        )
        self.btn_automacao.grid(row=9, column=0, padx=20, pady=4, sticky="ew")

        self.btn_comparacao = ctk.CTkButton(
            self.sidebar,
            text="📋 Última Comparação",
            anchor="w",
            command=lambda: self.enviar_pergunta_direta("Qual foi a data e o resultado do último cruzamento de planilhas realizado?"),
            fg_color="#23272d",
            hover_color="#313742",
        )
        self.btn_comparacao.grid(row=10, column=0, padx=20, pady=(4, 15), sticky="ew")

        # Botão Limpar Chat no rodapé da barra
        self.btn_limpar = ctk.CTkButton(
            self.sidebar,
            text="🧹 Limpar Histórico",
            command=self._limpar_chat,
            fg_color="#3a1e1e",
            hover_color="#5a2e2e",
        )
        self.btn_limpar.grid(row=11, column=0, padx=20, pady=20, sticky="ew")

    def _construir_area_chat(self):
        """Cria o painel principal de conversa com área de rolagem e campo de digitação."""
        self.chat_container = ctk.CTkFrame(self, fg_color="#18191c", corner_radius=0)
        self.chat_container.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        self.chat_container.grid_rowconfigure(0, weight=1)
        self.chat_container.grid_columnconfigure(0, weight=1)

        # Área de mensagens com rolagem
        self.scroll_chat = ctk.CTkScrollableFrame(self.chat_container, fg_color="transparent")
        self.scroll_chat.grid(row=0, column=0, sticky="nsew", padx=15, pady=(15, 5))
        self.scroll_chat.grid_columnconfigure(0, weight=1)

        # Barra inferior de envio
        self.frame_input = ctk.CTkFrame(self.chat_container, fg_color="transparent")
        self.frame_input.grid(row=1, column=0, sticky="ew", padx=15, pady=(5, 15))
        self.frame_input.grid_columnconfigure(0, weight=1)

        self.entry_pergunta = ctk.CTkEntry(
            self.frame_input,
            placeholder_text="Faça uma pergunta sobre equipamentos, filiais, chamados ou automações...",
            height=45,
            font=ctk.CTkFont(size=14),
        )
        self.entry_pergunta.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.entry_pergunta.bind("<Return>", lambda event: self._ao_enviar())

        self.btn_enviar = ctk.CTkButton(
            self.frame_input,
            text="Enviar 🚀",
            width=100,
            height=45,
            command=self._ao_enviar,
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.btn_enviar.grid(row=0, column=1)

        # Label de status / feedback
        self.lbl_feedback = ctk.CTkLabel(
            self.chat_container,
            text="Pronto para conversar",
            font=ctk.CTkFont(size=11),
            text_color="#888888",
        )
        self.lbl_feedback.grid(row=2, column=0, sticky="w", padx=20, pady=(0, 5))

    def verificar_status_simpress(self):
        """Checa se o Simpress local em http://127.0.0.1:8000 está online."""
        def checar():
            online = False
            try:
                res = self.simpress.consultar_status_automacao()
                online = "erro" not in res
            except Exception:
                online = False

            if online:
                self.after(0, lambda: self.lbl_status_simpress.configure(
                    text="● Simpress Conectado", text_color="#2ecc71"
                ))
            else:
                self.after(0, lambda: self.lbl_status_simpress.configure(
                    text="● Simpress Desconectado", text_color="#e74c3c"
                ))

        threading.Thread(target=checar, daemon=True).start()

    def _ao_trocar_modelo(self, descricao_escolhida: str):
        """Troca o modelo selecionado no OpenRouter."""
        slug = self.mapa_modelos.get(descricao_escolhida)
        if slug:
            self.llm.trocar_modelo(slug)
            self.lbl_feedback.configure(text=f"Modelo ativo alterado para: {slug}", text_color="#2ecc71")

    def _ao_alternar_voz(self):
        """Liga ou desliga o áudio."""
        estado = self.switch_voz.get() == 1
        voice.alternar_voz(estado)
        texto = "Voz ligada" if estado else "Voz desligada"
        self.lbl_feedback.configure(text=texto, text_color="gray")

    def _limpar_chat(self):
        """Limpa as mensagens na tela e reinicia o histórico de contexto."""
        for widget in self.scroll_chat.winfo_children():
            widget.destroy()
        self.llm.limpar_historico()
        self._adicionar_mensagem_jarvis("Histórico limpo. Como posso ajudar agora?", [], falar_audio=False)

    def enviar_pergunta_direta(self, texto: str):
        """Envia uma pergunta pré-programada dos botões de atalho."""
        self.entry_pergunta.delete(0, "end")
        self.entry_pergunta.insert(0, texto)
        self._ao_enviar()

    def _ao_enviar(self):
        """Captura o texto digitado e dispara o processamento em segundo plano."""
        pergunta = self.entry_pergunta.get().strip()
        if not pergunta:
            return

        self.entry_pergunta.delete(0, "end")
        self.entry_pergunta.configure(state="disabled")
        self.btn_enviar.configure(state="disabled")

        # Adiciona a mensagem do usuário na tela
        self._adicionar_mensagem_usuario(pergunta)

        # Inicia a consulta em thread separada para NÃO congelar a tela
        threading.Thread(target=self._processar_pergunta, args=(pergunta,), daemon=True).start()

    def _processar_pergunta(self, pergunta: str):
        """Executa a consulta na IA e atualiza a interface."""
        self.after(0, lambda: self.lbl_feedback.configure(text="Consultando o OpenRouter...", text_color="#3498db"))

        def callback_status(msg: str):
            texto_limpo = msg.replace("[cyan]", "").replace("[/cyan]", "")
            self.after(0, lambda: self.lbl_feedback.configure(text=texto_limpo, text_color="#f39c12"))

        resposta, ferramentas = self.llm.enviar_mensagem(pergunta, callback_status=callback_status)

        self.after(0, lambda: self._finalizar_resposta(resposta, ferramentas))

    def _finalizar_resposta(self, resposta: str, ferramentas: List[str]):
        """Renderiza a resposta do Jarvis e reativa os campos de entrada."""
        self._adicionar_mensagem_jarvis(resposta, ferramentas, falar_audio=True)
        self.entry_pergunta.configure(state="normal")
        self.btn_enviar.configure(state="normal")
        self.entry_pergunta.focus()
        self.lbl_feedback.configure(text="Pronto para conversar", text_color="#888888")

    def _adicionar_mensagem_usuario(self, texto: str):
        """Cria o balão visual da mensagem do usuário (alinhado à direita)."""
        card = ctk.CTkFrame(self.scroll_chat, fg_color="#1f538d", corner_radius=12)
        card.pack(anchor="e", padx=(80, 10), pady=6, fill="x")

        lbl_autor = ctk.CTkLabel(
            card,
            text="Você",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#a0c4ff",
        )
        lbl_autor.pack(anchor="w", padx=14, pady=(8, 2))

        lbl_conteudo = ctk.CTkLabel(
            card,
            text=texto,
            font=ctk.CTkFont(size=14),
            wraplength=650,
            justify="left",
            text_color="white",
        )
        lbl_conteudo.pack(anchor="w", padx=14, pady=(0, 10))

        self.after(50, self._rolar_para_o_final)

    def _adicionar_mensagem_jarvis(self, texto: str, ferramentas: List[str], falar_audio: bool = True):
        """Cria o balão visual da mensagem do Jarvis (alinhado à esquerda) com badges de ferramentas."""
        card = ctk.CTkFrame(self.scroll_chat, fg_color="#2b2d31", corner_radius=12)
        card.pack(anchor="w", padx=(10, 80), pady=6, fill="x")

        # Cabeçalho do Jarvis com indicador de modelo
        frame_topo = ctk.CTkFrame(card, fg_color="transparent")
        frame_topo.pack(anchor="w", fill="x", padx=14, pady=(8, 4))

        lbl_autor = ctk.CTkLabel(
            frame_topo,
            text="🤖 Jarvis",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#58a6ff",
        )
        lbl_autor.pack(side="left")

        # Badges das ferramentas acionadas
        if ferramentas:
            for fn in ferramentas:
                badge = ctk.CTkLabel(
                    frame_topo,
                    text=f"⚙ {fn}",
                    font=ctk.CTkFont(size=10, weight="bold"),
                    fg_color="#161b22",
                    corner_radius=6,
                    text_color="#3fb950",
                    padx=6,
                    pady=2,
                )
                badge.pack(side="left", padx=5)

        # Texto da resposta
        lbl_conteudo = ctk.CTkLabel(
            card,
            text=texto,
            font=ctk.CTkFont(size=13),
            wraplength=700,
            justify="left",
            text_color="#e6edf3",
        )
        lbl_conteudo.pack(anchor="w", padx=14, pady=(0, 12))

        self.after(50, self._rolar_para_o_final)

        if falar_audio:
            voice.falar(texto)

    def _rolar_para_o_final(self):
        """Rola a janela do chat automaticamente até a última mensagem."""
        try:
            self.scroll_chat._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass


def main():
    app = JarvisGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
