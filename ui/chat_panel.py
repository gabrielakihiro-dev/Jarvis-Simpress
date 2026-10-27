"""Centro do Jarvis: orbe, conversa em balões, cartões de resposta, sugestões e entrada por texto ou voz."""

import html
import os
import re
from pathlib import Path
from typing import Callable, Optional

from PyQt6.QtCore import Qt, QThread, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

import importacao
import voice
from llm_client import MODELOS_CATALOGO, LLMClient, Resposta, listar_modelos_ao_vivo
from ui import theme
from ui.cartoes import cartao_html
from ui.escuta import Escuta
from ui.orbe import ATIVOS, Orbe
from ui.widgets import CartaoConfirmacao, FluxoLayout, botao, renderizar

# Os cartões de status da esquerda já perguntam totais, chamados, automação e pendências.
ACOES_RAPIDAS = [
    ("Chamados parados", "Quais ordens de serviço estão paradas há mais tempo?"),
    ("Última comparação", "Resuma a última comparação de planilhas."),
    ("Relatório do mês", "Resuma o relatório mensal do mês atual."),
    ("Exportar equipamentos", "Exporte a planilha de equipamentos."),
]

# Próximas perguntas por ferramenta usada: fixas, sem chamada extra à IA.
SUGESTOES = {
    "listar_chamados_abertos": ["Quais estão parados há mais tempo?", "Exporte a planilha de chamados."],
    "listar_pendencias_operacionais": ["Quais séries estão sem local definido?", "Exporte o histórico da última comparação."],
    "consultar_ultima_comparacao": ["Quais são as pendências operacionais?", "Exporte o histórico da última comparação."],
    "obter_totais_inventario": ["Quantos notebooks estão sem usuário?", "Exporte a planilha de equipamentos."],
    "consultar_status_automacao": ["Mostre o histórico da automação.", "O sistema está pronto para as rotinas?"],
    "listar_unidades": ["Quero editar o endereço de uma unidade."],
    "consultar_equipamento": ["Em qual unidade fica esse equipamento?"],
    "exportar_planilha": ["Exporte a planilha de chamados.", "Exporte a planilha de equipamentos."],
}

INTERVALO_LOTE_MS = 5000
TENTATIVAS_LOTE = 60  # 5 min
CANCELAR = {"cancelar", "cancela", "cancele", "cancelo", "cancelem"}


def e_cancelar(texto: str) -> bool:
    """Frase curta com “cancelar” (ex.: “Jarvis, cancela”) cancela em vez de ir para a IA."""
    palavras = re.findall(r"\w+", texto.lower())
    return 0 < len(palavras) <= 4 and bool(CANCELAR & set(palavras)) and "não" not in palavras


class AgentWorker(QThread):
    """Roda uma chamada ao LLM fora da thread da tela, para a janela nunca congelar."""

    status = pyqtSignal(str)
    pronto = pyqtSignal(object)

    def __init__(self, tarefa: Callable[[Callable[[str], None]], Resposta], parent=None):
        super().__init__(parent)
        self._tarefa = tarefa

    def run(self) -> None:
        try:
            self.pronto.emit(self._tarefa(self.status.emit))
        except Exception as e:  # a tela nunca deve ficar presa em "pensando"
            self.pronto.emit(Resposta(texto=f"Erro inesperado: {e}"))


class ModelosWorker(QThread):
    """Busca a lista de modelos do OpenRouter fora da tela."""

    pronto = pyqtSignal(list)

    def run(self) -> None:
        self.pronto.emit(listar_modelos_ao_vivo())


class FalaWorker(QThread):
    """Gera a fala trecho a trecho fora da tela; o painel toca cada mp3 assim que chega."""

    pronto = pyqtSignal(str)  # um mp3 por trecho; "" se o primeiro falhar

    def __init__(self, texto: str, parent=None):
        super().__init__(parent)
        self._texto = texto

    def run(self) -> None:
        for i, trecho in enumerate(voice.trechos(self._texto)):
            if self.isInterruptionRequested():
                return
            caminho = voice.gerar_mp3(trecho)
            if caminho or i == 0:
                self.pronto.emit(caminho or "")
            if not caminho:
                return


class TranscreveWorker(QThread):
    """Envia o áudio gravado ao modelo de transcrição sem travar a tela."""

    pronto = pyqtSignal(str)

    def __init__(self, llm: LLMClient, wav: bytes, parent=None):
        super().__init__(parent)
        self._llm, self._wav = llm, wav

    def run(self) -> None:
        self.pronto.emit(self._llm.transcrever_audio(self._wav))


class ChatPanel(QFrame):
    mudou_estado = pyqtSignal()     # modelo, voz ou escuta mudaram
    mudou_rodape = pyqtSignal(str)  # HTML do rodapé, repetido na barra inferior abaixo de 1100 px

    def __init__(self, llm: LLMClient, parent=None):
        super().__init__(parent)
        self.setObjectName("chat")
        self.llm = llm
        self._worker: Optional[AgentWorker] = None
        self._fala: Optional[FalaWorker] = None
        self._transcricao: Optional[TranscreveWorker] = None
        self._lote: Optional[str] = None
        self._lote_pedido: Optional[tuple] = None
        self._lote_tentativas = 0
        self._player = QMediaPlayer(self)
        self._saida = QAudioOutput(self)
        self._player.setAudioOutput(self._saida)
        self._player.mediaStatusChanged.connect(self._fim_fala)
        self._mp3_atual = ""
        self._fila_fala: list = []
        self._cancelado = False  # descarta a transcrição ou resposta que ainda vai chegar
        self._sem_volta = False  # alteração confirmada em execução: não dá mais para cancelar
        self._timer_lote = QTimer(self)
        self._timer_lote.setInterval(INTERVALO_LOTE_MS)
        self._timer_lote.timeout.connect(self._conferir_lote)

        self.escuta = Escuta(self)
        self.escuta.acordou.connect(self._acordou)
        self.escuta.gravando.connect(self._gravando)
        self.escuta.gravou.connect(self._transcrever)
        self.escuta.aviso.connect(lambda m: self._rodape(m, erro=True))
        self.escuta.cancelou.connect(self.cancelar)
        self.escuta.dormiu.connect(self._dormiu)
        self.escuta.mudou_mudo.connect(self._mudou_mudo)

        # controles que a janela leva para o topo e para o menu ⚙
        self.combo = QComboBox()
        self.combo.setAccessibleName("Modelo de IA")
        self.combo.setMaxVisibleItems(15)
        self._preencher_modelos([(s, s) for s, _ in MODELOS_CATALOGO.values()])
        self.combo.currentIndexChanged.connect(self._trocar_modelo)
        self._modelos = ModelosWorker(self)
        self._modelos.pronto.connect(self._modelos_ao_vivo)
        self._modelos.start()
        self.btn_voz = botao("", "fantasma")
        self.btn_voz.setCheckable(True)
        self.btn_voz.clicked.connect(self._alternar_voz)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(*(theme.SP["md"],) * 4)
        lay.setSpacing(theme.SP["sm"])

        self.orbe = Orbe()
        self.orbe.clicado.connect(self._clicou_orbe)
        self.escuta.nivel.connect(self.orbe.definir_nivel)  # a janela põe o orbe no trilho da esquerda

        self.texto = QTextBrowser()
        self.texto.setObjectName("conversa")
        self.texto.setOpenLinks(False)
        self.texto.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)  # tabelas largas quebram linha
        self.texto.anchorClicked.connect(self._abrir_link)
        self.texto.setAccessibleName("Conversa com o assistente")
        lay.addWidget(self.texto, 1)

        self.cartao = CartaoConfirmacao()
        self.cartao.decidido.connect(self._decidiu)
        lay.addWidget(self.cartao)

        self._linha_sugestoes = FluxoLayout(espaco=theme.SP["xs"])
        self._sugestoes: list = []
        lay.addLayout(self._linha_sugestoes)

        chips = QWidget()
        cl = FluxoLayout(chips, theme.SP["xs"])
        self._chips = []
        for rotulo, pergunta in ACOES_RAPIDAS:
            b = botao(rotulo, "chip", pergunta)
            b.clicked.connect(lambda _=False, p=pergunta: self.enviar(p))
            self._chips.append(b)
            cl.addWidget(b)
        lay.addWidget(chips)

        entrada = QHBoxLayout()
        self.campo = QLineEdit()
        self.campo.setObjectName("entrada")
        self.campo.setFixedHeight(40)
        self.campo.setPlaceholderText("Pergunte sobre equipamentos, chamados, automação…")
        self.campo.setAccessibleName("Mensagem para o assistente")
        self.campo.returnPressed.connect(self._enviar_campo)
        self.btn_mic = botao("🎤", "fantasma", "Falar com o Jarvis: clique para gravar; para sozinho quando você para de falar", "Falar com o Jarvis")
        self.btn_mic.clicked.connect(self._clicou_orbe)
        self.btn_mic.setFixedWidth(40)
        self.btn_enviar = botao("Enviar", "primario")
        self.btn_enviar.clicked.connect(self._enviar_campo)
        entrada.addWidget(self.campo, 1)
        entrada.addWidget(self.btn_mic)
        entrada.addWidget(self.btn_enviar)
        lay.addLayout(entrada)

        self.rodape = QLabel("")
        self.rodape.setObjectName("secundario")
        self.rodape.setWordWrap(True)
        self.rodape.setAccessibleName("Estado do assistente")
        self.rodape.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse
                                            | Qt.TextInteractionFlag.LinksAccessibleByKeyboard)
        self.rodape.linkActivated.connect(lambda _: self.escuta.definir_mudo(False))  # só o aviso de mudo tem link
        lay.addWidget(self.rodape)

        self.setTabOrder(self.texto, self.campo)
        self._atualizar_voz()
        self._mensagem("Jarvis", "Pronto. Pergunte, use um cartão ao lado ou chame pelo orbe. Alterações só acontecem depois da sua confirmação.")
        if not llm.client:
            self._rodape("A chave do OpenRouter não foi configurada. Edite o arquivo .env e reinicie.", erro=True)

    # --- interface --------------------------------------------------------

    def _mensagem(self, quem: str, texto: str, tipo: str = "jarvis") -> None:
        """Balão: "eu" à direita; "jarvis" e "aviso" à esquerda. Tabelas são o que o QTextBrowser alinha bem."""
        corpo = html.escape(texto).replace("\n", "<br>") if tipo == "eu" else renderizar(texto)
        cor = {"eu": theme.TEXT_SECONDARY, "jarvis": theme.CYAN, "aviso": theme.WARNING}[tipo]
        fundo = theme.BALAO_EU if tipo == "eu" else theme.SURFACE
        balao = (f"<td bgcolor='{fundo}' style='padding:8px'><span style='color:{cor}'><b>{html.escape(quem)}</b></span>"
                 f"<br>{corpo}</td>")
        vazio = "<td width='18%'></td>"
        linha = vazio + balao if tipo == "eu" else balao + vazio
        self._html(f"<table width='100%' cellspacing='0' cellpadding='0' style='margin-bottom:8px'><tr>{linha}</tr></table>")

    def _html(self, trecho: str) -> None:
        self.texto.append(trecho)
        barra = self.texto.verticalScrollBar()
        barra.setValue(barra.maximum())

    def _rodape(self, msg: str, erro: bool = False) -> None:
        cor = theme.ERROR if erro else theme.TEXT_SECONDARY
        self._definir_rodape(f"<span style='color:{cor}'>{html.escape(msg)}</span>")

    def _definir_rodape(self, trecho: str) -> None:
        self.rodape.setText(trecho)
        self.mudou_rodape.emit(trecho)

    def _ocupado(self, ocupado: bool) -> None:
        for w in (self.campo, self.btn_enviar, self.btn_mic, self.combo, *self._chips, *self._sugestoes):
            w.setEnabled(not ocupado)
        self.btn_enviar.setText("Pensando…" if ocupado else "Enviar")
        self.escuta.pausar("ia", ocupado)

    def _mostrar_sugestoes(self, ferramentas: list) -> None:
        for b in self._sugestoes:
            self._linha_sugestoes.removeWidget(b)
            b.deleteLater()
        self._sugestoes = []
        perguntas = []
        for f in ferramentas:
            for p in SUGESTOES.get(f, []):
                if p not in perguntas:
                    perguntas.append(p)
        for p in perguntas[:3]:
            b = botao(f"↳ {p}", "chip", "Sugestão de próxima pergunta", p)
            b.clicked.connect(lambda _=False, q=p: self.enviar(q))
            self._linha_sugestoes.addWidget(b)
            self._sugestoes.append(b)

    def focar_entrada(self) -> None:
        self.campo.setFocus()

    # --- ações ------------------------------------------------------------

    def _preencher_modelos(self, modelos: list) -> None:
        """Favoritos (catálogo) no topo, depois o resto; o modelo atual sempre fica na lista."""
        favoritos = [s for s, _ in MODELOS_CATALOGO.values()]
        rotulo = dict(modelos)
        atual = self.llm.modelo_principal
        ordem = [s for s in favoritos if s in rotulo] + [s for s in rotulo if s not in favoritos]
        if atual not in ordem:
            ordem.insert(0, atual)
        self.combo.blockSignals(True)
        self.combo.clear()
        for s in ordem:
            self.combo.addItem(("★ " if s in favoritos else "") + rotulo.get(s, s), s)
        self.combo.setCurrentIndex(ordem.index(atual))
        self.combo.blockSignals(False)

    def _modelos_ao_vivo(self, modelos: list) -> None:
        if modelos:  # sem rede, fica o catálogo fixo
            self._preencher_modelos(modelos)

    def _trocar_modelo(self, _indice: int) -> None:
        slug = self.combo.currentData()
        if slug:
            self.llm.trocar_modelo(slug)
            self.mudou_estado.emit()

    def _alternar_voz(self) -> None:
        if not voice.alternar_voz():
            self._parar_fala()  # desligou: cala na hora, sem esperar o trecho atual acabar
        self._atualizar_voz()
        self.mudou_estado.emit()

    def _atualizar_voz(self) -> None:
        ligada = voice.HABILITAR_VOZ
        self.btn_voz.setChecked(ligada)
        self.btn_voz.setText("🔊" if ligada else "🔇")
        self.btn_voz.setToolTip(f"Voz {'ligada' if ligada else 'desligada'}. Clique para alternar.")
        self.btn_voz.setAccessibleName(f"Voz {'ligada' if ligada else 'desligada'}. Clique para alternar.")

    def ligar_escuta(self, ligar: bool) -> bool:
        ok = self.escuta.ligar(ligar)
        self.orbe.escuta(self.escuta.ligada)
        if not self.escuta.ligada and self.orbe.estado == "dormindo":
            self.orbe.definir("ocioso")
        self.mudou_estado.emit()
        return ok

    def limpar(self) -> None:
        self.llm.limpar_historico()
        self.cartao.hide()
        self.escuta.pausar("cartao", False)
        self._lote_pedido = None
        self._ocupado(False)
        self._mostrar_sugestoes([])
        self.texto.clear()
        self._mensagem("Jarvis", "Conversa reiniciada.")

    def avisar(self, texto: str) -> None:
        """Aviso proativo: não chama a IA nem entra no histórico dela."""
        self._mensagem("Aviso", texto, "aviso")
        if voice.HABILITAR_VOZ and not self._ocupado_agora():
            self._falar(texto)

    def _ocupado_agora(self) -> bool:
        return (self._worker is not None and self._worker.isRunning()) or self.cartao.isVisible() or self.escuta.esta_gravando

    def _enviar_campo(self) -> None:
        texto = self.campo.text().strip()
        if texto:
            self.campo.clear()
            self.enviar(texto)

    def enviar(self, texto: str) -> None:
        if self._ocupado_agora():
            return
        self._mostrar_sugestoes([])
        self._mensagem("Você", texto, "eu")
        self._iniciar(lambda cb: self.llm.enviar_mensagem(texto, callback_status=cb))

    def _decidiu(self, confirmado: bool) -> None:
        self.escuta.pausar("cartao", False)
        self._mensagem("Você", "Confirmei a alteração." if confirmado else "Cancelei a alteração.", "eu")
        if self._lote_pedido is not None:
            pedido, self._lote_pedido = self._lote_pedido, None
            self._ocupado(False)
            if confirmado:
                self._publicar_lote(*pedido)
            else:
                self._rodape("Importação cancelada. Nada foi copiado.")
            return
        self._sem_volta = confirmado
        self._iniciar(lambda cb: self.llm.resolver_confirmacao(confirmado, callback_status=cb))

    def _iniciar(self, tarefa) -> None:
        self._ocupado(True)
        self.orbe.definir("pensando")
        self._rodape("Pensando…")
        self._worker = AgentWorker(tarefa, self)
        self._worker.status.connect(self._rodape)
        self._worker.pronto.connect(self._recebeu)
        self._worker.start()

    def _pedir_confirmacao(self, descricao: str) -> None:
        self._mensagem("Jarvis", "Preciso da sua confirmação para continuar.")
        self._ocupado(True)  # nada de nova pergunta até confirmar ou cancelar
        self.btn_enviar.setText("Enviar")
        self.escuta.pausar("cartao", True)
        self.cartao.mostrar(descricao)
        self._rodape("Aguardando sua confirmação.")

    def cancelar(self) -> None:
        """“Cancelar” por voz: cala a fala, recusa o cartão ou descarta o que ainda está a caminho."""
        self._parar_fala()
        if self.escuta.esta_gravando:
            self.escuta.parar(False)
        self.escuta.dormir()
        if self.cartao.isVisible():
            self.cartao.btn_cancelar.click()
            return
        if self._sem_volta and self._worker is not None and self._worker.isRunning():
            self._rodape("A alteração já confirmada está em execução; não dá para cancelar.", erro=True)
            return
        if any(t is not None and t.isRunning() for t in (self._worker, self._transcricao)):
            self._cancelado = True
            self.orbe.definir("ocioso")
        self._rodape("Cancelado.")

    def _recebeu(self, r: Resposta) -> None:
        self._ocupado(False)
        self.orbe.definir("ocioso")
        self._sem_volta = False
        if self._cancelado:
            if r.pendente:  # recusa a alteração pedida, para o histórico da IA não ficar pendurado
                self._iniciar(lambda cb: self.llm.resolver_confirmacao(False, callback_status=cb))
                return
            self._cancelado = False
            self._rodape("Cancelado.")
            for ferramenta, resultado in r.dados:  # o arquivo já foi salvo: avisa mesmo cancelado
                if ferramenta == "exportar_planilha":
                    self._mostrar_exportacao(resultado)
            return
        if r.pendente:
            self._pedir_confirmacao(r.pendente["descricao"])
            return
        self._mensagem("Jarvis", r.texto)
        abrir_importacao = False
        for ferramenta, resultado in r.dados:
            if ferramenta == "exportar_planilha":
                self._mostrar_exportacao(resultado)
            elif ferramenta == "abrir_importacao":
                abrir_importacao = True
            else:
                tabela = cartao_html(ferramenta, resultado)
                if tabela:
                    self._html(tabela + "<br>")
        usadas = ", ".join(r.ferramentas)
        erro = r.texto.startswith(("Erro", "A chave"))
        self._rodape(f"Ferramentas usadas: {usadas}" if usadas else ("Falhou — veja a mensagem acima." if erro else "Pronto."), erro=erro)
        self._mostrar_sugestoes(r.ferramentas)
        if r.texto_voz and voice.HABILITAR_VOZ:
            self._falar(r.texto_voz)
        self.campo.setFocus()
        if abrir_importacao:
            self.importar()

    def _mostrar_exportacao(self, resultado: dict) -> None:
        if not resultado.get("sucesso"):
            return
        pasta = QUrl.fromLocalFile(resultado.get("pasta", "")).toString()
        self._html(f"<p><span style='color:{theme.SUCCESS}'><b>Planilha Exportada com Sucesso!</b></span><br>"
                   f"{html.escape(resultado.get('arquivo', ''))} · <a href='{html.escape(pasta)}' style='color:{theme.CYAN}'>Abrir pasta</a></p>")

    def _abrir_link(self, url: QUrl) -> None:
        # só abre pastas locais criadas pela exportação; texto da IA não vira link clicável
        if url.isLocalFile() and Path(url.toLocalFile()).is_dir():
            QDesktopServices.openUrl(url)

    # --- importação de planilhas que o usuário já tem ------------------------

    def importar(self) -> None:
        if self._ocupado_agora() or self._lote is not None:
            self._rodape("Termine a ação em andamento antes de importar.", erro=True)
            return
        filtro = "Planilhas Excel (*.xlsx)"
        inicio = str(Path.home() / "Downloads")
        endpoint, _ = QFileDialog.getOpenFileName(self, "Planilha do Endpoint (.xlsx)", inicio, filtro)
        if not endpoint:
            return
        simpress, _ = QFileDialog.getOpenFileName(self, "Planilha da Simpress (.xlsx)", os.path.dirname(endpoint), filtro)
        if not simpress:
            return
        self._lote_pedido = (endpoint, simpress)
        self._pedir_confirmacao(
            "Importar planilhas no Simpress pela pasta de entrada automática:\n"
            f"• Planilha do Endpoint: {os.path.basename(endpoint)}\n"
            f"• Planilha da Simpress: {os.path.basename(simpress)}\n"
            "O Simpress processa o lote e atualiza a comparação e o histórico.")

    def _publicar_lote(self, endpoint: str, simpress: str) -> None:
        try:
            self._lote = importacao.criar_lote(endpoint, simpress)
        except (OSError, ValueError) as e:
            self._mensagem("Jarvis", f"Não consegui criar o lote de importação: {e}")
            return
        self._lote_tentativas = 0
        self._timer_lote.start()
        self._mensagem("Jarvis", f"Lote {self._lote} entregue ao Simpress. Aviso quando terminar (confiro a cada 5 s, por até 5 min).")

    def _conferir_lote(self) -> None:
        self._lote_tentativas += 1
        recibo = importacao.resultado_lote(self._lote)
        if recibo is None and self._lote_tentativas < TENTATIVAS_LOTE:
            return
        self._timer_lote.stop()
        lote, self._lote = self._lote, None
        if recibo is None:
            self.avisar(f"O lote {lote} ainda não terminou depois de 5 minutos. Confira a tela Automação do Simpress.")
        elif recibo.get("status") == "concluido":
            self.avisar(f"Importação do lote {lote} concluída. {recibo.get('detalhe', '')}".strip())
        else:
            self.avisar(f"A importação do lote {lote} falhou: {recibo.get('detalhe', 'sem detalhe')}")

    # --- voz: saída (fala) e entrada (microfone) ---------------------------

    def _falar(self, texto: str) -> None:
        self._parar_fala()
        self._fala = FalaWorker(texto, self)
        self._fala.pronto.connect(self._tocar)
        self._fala.finished.connect(self._fala_acabou)
        self._fala.start()

    def _tocar(self, caminho: str) -> None:
        origem = self.sender()
        if isinstance(origem, FalaWorker) and (origem is not self._fala or origem.isInterruptionRequested()):  # trecho de fala já interrompida
            if caminho and os.path.exists(caminho):
                os.remove(caminho)
            return
        if not caminho:
            self._rodape("Não consegui gerar a voz (sem internet para o Edge-TTS?). A resposta está no texto.", erro=True)
            return
        if self._mp3_atual:
            self._fila_fala.append(caminho)
            return
        self._mp3_atual = caminho
        self.escuta.pausar("fala", True)
        self.orbe.definir("falando")
        self._player.setSource(QUrl.fromLocalFile(caminho))
        self._saida.setVolume(1.0)
        self._player.play()

    def _fim_fala(self, estado) -> None:
        if estado in (QMediaPlayer.MediaStatus.EndOfMedia, QMediaPlayer.MediaStatus.InvalidMedia):
            proximo = self._fila_fala.pop(0) if self._fila_fala else ""
            # entre trechos o orbe segue “falando” e a escuta segue pausada
            seguindo = proximo or (self._fala is not None and self._fala.isRunning() and not self._fala.isInterruptionRequested())
            self._apagar_mp3(liberar=not seguindo)
            if proximo:
                self._tocar(proximo)

    def _fala_acabou(self) -> None:
        if self.sender() is self._fala and not self._mp3_atual:
            self._apagar_mp3()

    def _parar_fala(self) -> None:
        if self._fala is not None:
            self._fala.requestInterruption()
        fila, self._fila_fala = self._fila_fala, []
        for c in fila:
            try:
                os.remove(c)
            except OSError:
                pass
        self._player.stop()
        self._apagar_mp3()

    def _apagar_mp3(self, liberar: bool = True) -> None:
        if self._mp3_atual:
            self._player.setSource(QUrl())
            try:
                os.remove(self._mp3_atual)
            except OSError:
                pass
            self._mp3_atual = ""
        if not liberar:
            return
        if self.orbe.estado == "falando":
            self.orbe.definir("ocioso")
        self.escuta.pausar("fala", False)

    def _acordou(self, motivo: str) -> None:
        self._rodape("Chamou? Pode falar.")
        if self.orbe.estado == "dormindo":
            self.orbe.definir("ocioso")

    def _dormiu(self) -> None:
        self._rodape("Dormindo — diga Hey Jarvis ou clique no orbe.")
        self.orbe.definir("dormindo")

    def _mudou_mudo(self, mudo: bool) -> None:
        self.orbe.definir_mudo(mudo)
        if mudo:
            self._avisar_mudo()
        else:
            self._rodape("Microfone ligado.")

    def _avisar_mudo(self) -> None:
        self._definir_rodape(f"<a href='mudo' style='color:{theme.WARNING}'>Microfone mudo — clique para ativar</a>")

    def _clicou_orbe(self) -> None:
        if self.escuta.mudo:
            self._avisar_mudo()
            return
        # Ativo (ouvindo, pensando, falando ou com cartão aberto): o clique cancela, como dizer “cancelar”.
        if (self._ocupado_agora() or self.orbe.estado in ATIVOS
                or (self._transcricao is not None and self._transcricao.isRunning())):
            self.cancelar()
        else:
            self.escuta.gravar()

    def _gravando(self, sim: bool) -> None:
        self.orbe.definir("ouvindo" if sim else "ocioso")
        self.btn_mic.setText("⏹" if sim else "🎤")
        self.btn_mic.setAccessibleName("Parar e enviar a fala" if sim else "Falar com o Jarvis")
        if sim:
            self._rodape("Ouvindo… fale; eu paro sozinho quando você terminar.")

    def _transcrever(self, wav: bytes) -> None:
        self._rodape("Transcrevendo…")
        self.orbe.definir("pensando")
        self.btn_mic.setEnabled(False)
        self.escuta.pausar("ia", True)
        self._transcricao = TranscreveWorker(self.llm, wav, self)
        self._transcricao.pronto.connect(self._transcreveu)
        self._transcricao.start()

    def _transcreveu(self, texto: str) -> None:
        self.btn_mic.setEnabled(True)
        self.escuta.pausar("ia", False)
        self.orbe.definir("ocioso")
        if self._cancelado:
            self._cancelado = False
            return
        if e_cancelar(texto):
            self.escuta.dormir()
            self._rodape("Cancelado. Nada foi enviado.")
            return
        if not texto:
            self._rodape("Não consegui entender o áudio. Tente de novo ou digite.", erro=True)
            return
        self.enviar(texto)

    def aguardar_fim(self, ms: int = 2000) -> None:
        """Chamado no fechamento da janela: espera a chamada em andamento terminar."""
        self._timer_lote.stop()
        for t in (self._fala, self._transcricao, self._modelos):
            if t is not None and t.isRunning():
                t.wait(ms)
        self.escuta.encerrar()
        self._parar_fala()
        w = self._worker
        if w is not None and w.isRunning() and not w.wait(ms):
            w.terminate()
            w.wait(500)
