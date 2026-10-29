"""Modo leve do Jarvis: servidor HTTP local para o painel de chat do Simpress.

Sem janela, voz, "Hey Jarvis" nem Chrome. Só o cérebro (`LLMClient`) atrás de um
servidor mínimo em 127.0.0.1, chamado apenas pelo proxy do servidor Simpress.

Contrato (JSON):
- POST /mensagem  {"texto": str}       -> {"texto", "ferramentas", "pendente": {"descricao"} | null}
- POST /confirmar {"confirmado": bool} -> mesmo formato
- POST /limpar                         -> {"ok": true}
- GET  /estado                         -> {"online": true, "modelo", "aguardando_confirmacao", "pendente": {"descricao"} | null}
- Erros: {"detail": str}
"""

import json
import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional

MAX_CORPO = 16 * 1024
MAX_DESCARTE = 1024 * 1024
MAX_TEXTO = 4000
PORTA_PADRAO = 8766  # 8765 é do ui-fixture (testes de interface) do Simpress

_logger = logging.getLogger(__name__)


def _resposta_json(resposta: Any) -> Dict[str, Any]:
    # Do pendente só sai a descrição montada pelo programa; argumentos e tool_call_id ficam aqui.
    pendente = {"descricao": str(resposta.pendente["descricao"])} if resposta.pendente else None
    return {"texto": resposta.texto, "ferramentas": [str(f) for f in resposta.ferramentas], "pendente": pendente}


def criar_handler(llm: Any) -> type:
    """Handler ligado a um `LLMClient` (ou um falso nos testes). Uma conversa por notebook."""
    trava = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def _enviar(self, status: int, dados: Dict[str, Any]) -> None:
            corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)

        def _erro(self, status: int, detalhe: str) -> None:
            self._enviar(status, {"detail": detalhe})

        def _ler_corpo(self) -> Optional[bytes]:
            """Lê o corpo inteiro (ou descarta o excesso) antes de responder: no Windows, responder
            com bytes não lidos no socket faz o cliente receber reset em vez da resposta."""
            try:
                tamanho = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                tamanho = -1
            if tamanho < 0:
                self._erro(400, "Content-Length inválido.")
                return None
            if tamanho > MAX_CORPO:
                restante = min(tamanho, MAX_DESCARTE)
                while restante > 0:
                    lido = self.rfile.read(min(restante, 65536))
                    if not lido:
                        break
                    restante -= len(lido)
                self._erro(413, "Corpo grande demais.")
                return None
            return self.rfile.read(tamanho) if tamanho else b""

        def _permitido(self) -> bool:
            # Navegador sempre manda Origin ou Sec-Fetch-Site: só o proxy do Simpress (servidor) pode chamar.
            if self.headers.get("Origin") is not None or self.headers.get("Sec-Fetch-Site") is not None:
                self._erro(403, "Acesso direto pelo navegador não é permitido.")
                return False
            porta = self.server.server_address[1]
            if (self.headers.get("Host") or "").lower() not in {f"127.0.0.1:{porta}", f"localhost:{porta}"}:
                self._erro(403, "Host não permitido.")
                return False
            return True

        def _json(self, corpo: bytes) -> Optional[Dict[str, Any]]:
            tipo = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            if tipo != "application/json":
                self._erro(400, "Content-Type deve ser application/json.")
                return None
            try:
                dados = json.loads(corpo.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                self._erro(400, "JSON inválido.")
                return None
            if not isinstance(dados, dict):
                self._erro(422, "O corpo deve ser um objeto JSON.")
                return None
            return dados

        def _tratar(self, metodo: str) -> None:
            try:
                corpo = self._ler_corpo()
                if corpo is None or not self._permitido():
                    return
                rotas = {"/mensagem": "POST", "/confirmar": "POST", "/limpar": "POST", "/estado": "GET"}
                caminho = self.path.split("?", 1)[0]
                if caminho not in rotas:
                    self._erro(404, "Rota não encontrada.")
                    return
                if metodo != rotas[caminho]:
                    self._erro(405, "Método não permitido.")
                    return

                if caminho == "/estado":
                    # Sem a trava: uma mensagem longa não pode travar a checagem de saúde do proxy.
                    descricao = llm.descricao_pendente
                    self._enviar(200, {
                        "online": True,
                        "modelo": str(llm.modelo_principal),
                        "aguardando_confirmacao": bool(llm.aguardando_confirmacao),
                        # O painel recarregado precisa mostrar o que será executado, não um cartão genérico.
                        "pendente": {"descricao": str(descricao)} if descricao else None,
                    })
                    return
                if caminho == "/limpar":
                    with trava:
                        llm.limpar_historico()
                    self._enviar(200, {"ok": True})
                    return

                dados = self._json(corpo)
                if dados is None:
                    return
                if caminho == "/mensagem":
                    texto = dados.get("texto")
                    if not isinstance(texto, str) or not texto.strip() or len(texto) > MAX_TEXTO:
                        self._erro(422, f"'texto' deve ser um texto não vazio de até {MAX_TEXTO} caracteres.")
                        return
                    with trava:
                        descricao = llm.descricao_pendente
                        if descricao:
                            # Painel recarregado com cartão em aberto: devolve o cartão em vez de perdê-lo.
                            self._enviar(200, {"texto": "Há uma alteração aguardando sua confirmação.",
                                               "ferramentas": [], "pendente": {"descricao": str(descricao)}})
                            return
                        resposta = llm.enviar_mensagem(texto)
                else:
                    confirmado = dados.get("confirmado")
                    if not isinstance(confirmado, bool):
                        self._erro(422, "'confirmado' deve ser true ou false.")
                        return
                    with trava:
                        resposta = llm.resolver_confirmacao(confirmado)
                self._enviar(200, _resposta_json(resposta))
            except Exception:
                _logger.exception("Erro ao atender %s %s", metodo, self.path)
                try:
                    self._erro(500, "Erro interno do Jarvis.")
                except OSError:
                    pass

        def do_GET(self) -> None:
            self._tratar("GET")

        def do_POST(self) -> None:
            self._tratar("POST")

        # Sem estes, o http.server responde 501 em HTML.
        def do_PUT(self) -> None:
            self._tratar("PUT")

        def do_DELETE(self) -> None:
            self._tratar("DELETE")

        def do_PATCH(self) -> None:
            self._tratar("PATCH")

        def do_HEAD(self) -> None:
            self._tratar("HEAD")

        def do_OPTIONS(self) -> None:
            self._tratar("OPTIONS")

    return Handler


def criar_servidor(llm: Any, porta: int = PORTA_PADRAO) -> ThreadingHTTPServer:
    """Servidor só em 127.0.0.1 (porta 0 = livre, usada nos testes)."""
    return ThreadingHTTPServer(("127.0.0.1", porta), criar_handler(llm))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    from dotenv import load_dotenv

    # Ordem importa: o .env (SIMPRESS_URL) e o modo leve precisam valer antes de importar o cérebro,
    # porque o catálogo de ferramentas é montado na importação.
    load_dotenv()
    os.environ.setdefault("JARVIS_MODO_LEVE", "1")
    from llm_client import LLMClient
    from simpress_client import SimpressClient

    llm = LLMClient(SimpressClient())
    porta = int(os.environ.get("JARVIS_LEVE_PORTA") or PORTA_PADRAO)
    servidor = criar_servidor(llm, porta)
    print(f"Jarvis (modo leve) ouvindo em http://127.0.0.1:{porta} - modelo {llm.modelo_principal}. Ctrl+C encerra.", flush=True)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()


if __name__ == "__main__":
    main()
