"""Cliente de comunicação com a API local do Simpress (http://127.0.0.1:8000).

Consulta o inventário, chamados e relatórios, e dispara as ações de escrita que
o usuário confirmou. Aplica a sanitização de dados pessoais (LGPD) antes de
qualquer dado seguir para a inteligência artificial.
"""

import os
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

from lgpd import limpar_texto_sensivel

SIMPRESS_URL = os.environ.get("SIMPRESS_URL", "http://127.0.0.1:8000").rstrip("/")
TIMEOUT = 10.0
PORTAS_VARREDURA = range(8000, 8100)
TIMEOUT_VARREDURA = 0.3

ROTINAS_VALIDAS = ("login", "os", "inventarios", "ambas", "usuarios", "sebrae")
DECISOES_VALIDAS = ("permitir", "recusar", "remover", "manter")
EXPORTACOES = {
    "equipamentos": "/api/exportar-equipamentos",
    "chamados": "/api/operacoes/chamados/exportar",
    "historico": "/api/historico-comparacoes/exportar/excel",
}
PASTA_DOWNLOADS = Path.home() / "Downloads"

# Limites para o texto devolvido à IA não estourar o contexto do modelo.
MAX_ITENS_LISTA = 20
MAX_CARACTERES_RESPOSTA = 6000
# Teto de páginas (100 itens cada) ao carregar os nomes da base para a máscara.
# shortcut: acima de 20.000 equipamentos com usuário a lista fica parcial; aumentar se a base crescer.
MAX_PAGINAS_NOMES = 200


def sanitizar_equipamento(equip: Dict[str, Any]) -> Dict[str, Any]:
    """Remove endereços detalhados e mantém apenas Cidade/UF e informações da máquina."""
    if not isinstance(equip, dict):
        return {}
    return {
        "serial": equip.get("serial", ""),
        "modelo": equip.get("modelo", ""),
        "tipo": equip.get("tipo", ""),
        "categoria": equip.get("categoria", ""),
        "apelido": equip.get("apelido", ""),
        "cidade": equip.get("retirada_cidade", "") or equip.get("cidade", ""),
        "uf": equip.get("retirada_uf", "PR"),
        "usuario_logado": equip.get("usuarios_logados", "") or equip.get("usuario_manual", "") or "Sem usuário registrado",
        "contrato": equip.get("contrato", ""),
    }


def sanitizar_chamado(chamado: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitiza campos de um chamado de suporte/ordem de serviço."""
    if not isinstance(chamado, dict):
        return {}
    simpress_info = chamado.get("simpress", {})
    return {
        "numero_chamado": chamado.get("numero_chamado", ""),
        "serie": chamado.get("serie", ""),
        "relacao_os": chamado.get("relacao", ""),
        "ordens_servico": simpress_info.get("ordens_servico", []) if isinstance(simpress_info, dict) else [],
        "pedidos": simpress_info.get("pedidos", []) if isinstance(simpress_info, dict) else [],
        "descricao": limpar_texto_sensivel(chamado.get("descricao", "")),
        "status": chamado.get("status", ""),
    }


def _aparar(dados: Any) -> Any:
    """Corta listas longas e limpa e-mails/telefones de textos, recursivamente."""
    if isinstance(dados, dict):
        return {k: _aparar(v) for k, v in dados.items()}
    if isinstance(dados, list):
        aparado: List[Any] = [_aparar(v) for v in dados[:MAX_ITENS_LISTA]]
        if len(dados) > MAX_ITENS_LISTA:
            aparado.append(f"... mais {len(dados) - MAX_ITENS_LISTA} itens omitidos")
        return aparado
    if isinstance(dados, str):
        return limpar_texto_sensivel(dados)
    return dados


def e_macbook(equip: Dict[str, Any]) -> bool:
    """Mesmo critério do Simpress (categorize_equipment): 'MACBOOK' no tipo ou no modelo."""
    texto = " ".join(str(equip.get(k) or "") for k in ("categoria", "tipo", "modelo")).upper()
    return "MACBOOK" in texto


class SimpressClient:
    """Cliente para as rotas do Simpress, com descoberta automática da porta."""

    def __init__(self, base_url: Optional[str] = None, transport: Optional[httpx.BaseTransport] = None):
        self.base_url = (base_url or SIMPRESS_URL).rstrip("/")
        self._transport = transport  # usado nos testes
        self._varredura_feita = False

    # --- infraestrutura -------------------------------------------------

    def _client(self, timeout: float = TIMEOUT) -> httpx.Client:
        return httpx.Client(base_url=self.base_url, timeout=timeout, transport=self._transport)

    def _msg_offline(self) -> str:
        return f"Simpress inacessível em {self.base_url}. O servidor está ligado? (iniciar_servidor.bat)"

    @staticmethod
    def _servidor_simpress(base_url: str, transport: Optional[httpx.BaseTransport], exigir_stats: bool) -> bool:
        """True se `base_url` responde como o Simpress (JSON de /api/prontidao)."""
        try:
            with httpx.Client(base_url=base_url, timeout=TIMEOUT_VARREDURA, transport=transport) as c:
                res = c.get("/api/prontidao")
                if res.status_code != 200 or not isinstance(res.json(), dict):
                    return False
                if exigir_stats:
                    stats = c.get("/api/stats")
                    return stats.status_code == 200 and "total_equipamentos" in stats.json()
                return True
        except Exception:
            return False

    def descobrir(self) -> bool:
        """Procura o Simpress: URL configurada primeiro, depois 127.0.0.1:8000–8099."""
        if self._servidor_simpress(self.base_url, self._transport, exigir_stats=False):
            return True
        urls = [f"http://127.0.0.1:{p}" for p in PORTAS_VARREDURA]
        urls = [u for u in urls if u != self.base_url]
        with ThreadPoolExecutor(max_workers=20) as pool:
            achados = list(pool.map(lambda u: self._servidor_simpress(u, self._transport, True), urls))
        for url, ok in zip(urls, achados):
            if ok:
                self.base_url = url
                return True
        return False

    def _chamar(
        self,
        metodo: str,
        caminho: str,
        params: Optional[Dict[str, Any]] = None,
        corpo: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Any]:
        """Faz a requisição. Devolve (ok, dados) ou (False, mensagem de erro em texto)."""
        for tentativa in (1, 2):
            try:
                with self._client() as c:
                    res = c.request(metodo, caminho, params=params, json=corpo)
            except httpx.ConnectError:
                # Sem conexão = nada foi enviado; seguro procurar outra porta e repetir.
                if tentativa == 1 and not self._varredura_feita:
                    self._varredura_feita = True
                    if self.descobrir():
                        continue
                return False, self._msg_offline()
            except httpx.TimeoutException:
                return False, "O Simpress demorou demais para responder."
            except Exception as e:
                return False, f"Falha na comunicação com o Simpress: {e}"

            if 200 <= res.status_code < 300:
                try:
                    return True, res.json()
                except ValueError:
                    return True, {}
            return False, self._erro_http(res)
        return False, self._msg_offline()

    @staticmethod
    def _erro_http(res: httpx.Response) -> str:
        try:
            detalhe = res.json().get("detail")
        except Exception:
            detalhe = None
        if isinstance(detalhe, list):
            detalhe = "; ".join(str(d.get("msg", d)) if isinstance(d, dict) else str(d) for d in detalhe)
        texto = detalhe if isinstance(detalhe, str) else res.text[:200]
        return f"Erro {res.status_code} do Simpress: {limpar_texto_sensivel(texto)}"

    def _leitura(self, caminho: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """GET genérico: devolve os dados aparados ou {"erro": ...}."""
        ok, dados = self._chamar("GET", caminho, params=params)
        if not ok:
            return {"erro": dados}
        # O corte por tamanho fica no LLMClient, depois da máscara (LGPD).
        return {"dados": _aparar(dados)}

    # --- consultas já existentes ----------------------------------------

    def consultar_equipamento(self, serial: str) -> Dict[str, Any]:
        """Consulta um equipamento pelo número de série.

        Aplica a regra de MacBooks do AGENTS.md (tenta o prefixo 'S' se não achar,
        e só aceita se o achado for MacBook) e, por último, busca por aproximação.
        """
        clean_serial = serial.strip().upper()
        if not clean_serial:
            return {"erro": "Número de série não informado."}

        ok, dados = self._chamar("GET", f"/api/equipamento/{clean_serial}")
        if ok and isinstance(dados, dict):
            return {"encontrado": True, "equipamento": sanitizar_equipamento(dados)}
        if not ok and "inacessível" in str(dados):
            return {"erro": dados}

        if not clean_serial.startswith("S"):
            ok, dados = self._chamar("GET", f"/api/equipamento/S{clean_serial}")
            if ok and isinstance(dados, dict) and e_macbook(dados):
                resultado = sanitizar_equipamento(dados)
                resultado["observacao"] = f"Equipamento localizado na base oficial com o prefixo 'S' (S{clean_serial})."
                return {"encontrado": True, "equipamento": resultado}

        ok, itens = self._chamar("GET", "/api/buscar", params={"q": clean_serial})
        if ok and isinstance(itens, list) and itens:
            return {
                "encontrado": True,
                "observacao": "Série exata não localizada, mas encontramos correspondências aproximadas:",
                "correspondencias": [sanitizar_equipamento(item) for item in itens[:3]],
            }

        return {"encontrado": False, "mensagem": f"O equipamento com número de série '{serial}' não foi encontrado no cadastro oficial."}

    def pesquisar_catalogo(
        self,
        termo: str = "",
        cidade: Optional[str] = None,
        categoria: Optional[str] = None,
        usuario: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Pesquisa equipamentos com filtros por texto, cidade, categoria ou status de usuário."""
        params: Dict[str, Any] = {"limit": 15, "offset": 0}
        if termo:
            params["q"] = termo
        if cidade:
            params["cidade"] = cidade
        if categoria:
            params["categoria"] = categoria
        if usuario in ("sem", "com"):
            params["usuario"] = usuario
        if not termo and usuario != "sem":
            params["listar_todos"] = "true"

        ok, dados = self._chamar("GET", "/api/buscar-expandida", params=params)
        if not ok:
            return {"erro": dados}
        return {
            "total_encontrados": dados.get("total", 0),
            "itens": [sanitizar_equipamento(item) for item in dados.get("items", [])],
        }

    def listar_nomes_usuarios(self) -> Optional[List[str]]:
        """Logins e nomes de pessoas da base, para a máscara LGPD reconhecer o que for digitado. None se falhar."""
        nomes = set()
        offset = 0
        for _ in range(MAX_PAGINAS_NOMES):
            ok, dados = self._chamar("GET", "/api/buscar-expandida", params={
                "listar_todos": "true", "usuario": "com", "limit": 100, "offset": offset,
            })
            if not ok or not isinstance(dados, dict):
                return None
            itens = dados.get("items") or []
            for item in itens:
                valores = [item.get("usuarios_logados"), item.get("nome_pessoa"), *(item.get("usuarios_logados_candidatos") or [])]
                nomes.update(v.strip() for v in valores if isinstance(v, str) and v.strip())
            if not dados.get("has_more") or not itens:
                break
            offset += len(itens)
        return sorted(nomes)

    def obter_totais_inventario(self) -> Dict[str, Any]:
        """Totais oficiais do cadastro da Simpress."""
        ok, stats = self._chamar("GET", "/api/stats")
        if not ok:
            return {"erro": stats}
        return {
            "total_equipamentos_oficial": stats.get("total_equipamentos", 0),
            "total_unidades": stats.get("total_unidades", 0),
            "base_importada": stats.get("base_importada", False),
            "arquivo_origem": stats.get("arquivo_origem", ""),
            "ultima_atualizacao": stats.get("ultima_atualizacao", ""),
            "alteracoes_exportaveis": stats.get("total_alteracoes_exportaveis", 0),
        }

    def listar_chamados_abertos(self) -> Dict[str, Any]:
        """Lista de chamados e a relação com as ordens de serviço (OS)."""
        ok, dados = self._chamar("GET", "/api/operacoes/chamados")
        if not ok:
            return {"erro": dados}
        chamados = dados.get("chamados", [])
        return {
            "atualizado_em": dados.get("atualizado_em", ""),
            "total_chamados": len(chamados),
            "resumo": dados.get("resumo", {}),
            "chamados": [sanitizar_chamado(ch) for ch in chamados[:MAX_ITENS_LISTA]],
        }

    def consultar_status_automacao(self) -> Dict[str, Any]:
        """Estado da rotina de automação em andamento (se houver)."""
        ok, dados = self._chamar("GET", "/api/automacao/estado")
        if not ok:
            return {"erro": dados}
        return {
            "executando": dados.get("estado") == "em_andamento",
            "rotina": dados.get("rotina") or "nenhuma",
            "estado": dados.get("estado", "livre"),
            "inicio": dados.get("inicio", ""),
            "aguardando_login": bool(dados.get("aguardando_login")),
            "cancelamento_pedido": bool(dados.get("cancelamento_pedido")),
        }

    def consultar_ultima_comparacao(self) -> Dict[str, Any]:
        """Resumo do último cruzamento de planilhas."""
        ok, dados = self._chamar("GET", "/api/historico-comparacoes")
        if not ok:
            return {"erro": dados}
        eventos = dados.get("eventos", [])
        if not eventos:
            return {"mensagem": "Nenhum histórico de comparação registrado até o momento."}
        ultimo = eventos[0]
        return {
            "horario": ultimo.get("horario", ""),
            "tipo": ultimo.get("tipo", ""),
            "resumo_divergencias": ultimo.get("resumo", {}),
        }

    # --- novas consultas (somente leitura) ------------------------------

    def obter_painel(self) -> Dict[str, Any]:
        return self._leitura("/api/painel")

    def obter_prontidao(self) -> Dict[str, Any]:
        return self._leitura("/api/prontidao")

    def listar_pendencias_operacionais(self) -> Dict[str, Any]:
        """Versão enxuta: contagem por seção e série/computador/motivo de cada item."""
        ok, dados = self._chamar("GET", "/api/operacoes/pendencias")
        if not ok:
            return {"erro": dados}
        itens = []
        for p in dados.get("pendencias") or []:
            item = p.get("item") if isinstance(p, dict) and isinstance(p.get("item"), dict) else {}
            itens.append({
                "secao": p.get("secao", "") if isinstance(p, dict) else "",
                "serie": item.get("serie", ""),
                "computador": item.get("computador", ""),
                "motivo": limpar_texto_sensivel(str(item.get("motivo") or "")),
            })
        return {
            "horario": (dados.get("evento") or {}).get("horario", ""),
            "total": len(itens),
            "por_secao": dict(Counter(i["secao"] for i in itens)),
            "itens": itens[:MAX_ITENS_LISTA],
            "omitidos": max(0, len(itens) - MAX_ITENS_LISTA),
        }

    def linha_do_tempo_chamados(self, serial: str) -> Dict[str, Any]:
        serial = serial.strip().upper()
        if not serial:
            return {"erro": "Número de série não informado."}
        return self._leitura(f"/api/operacoes/chamados/linha-do-tempo/{serial}")

    def obter_relatorio_mensal(self, mes: str) -> Dict[str, Any]:
        mes = mes.strip()
        if len(mes) != 7 or mes[4] != "-":
            return {"erro": "Informe o mês no formato AAAA-MM (ex.: 2026-10)."}
        return self._leitura("/api/relatorio-mensal/dados", params={"mes": mes})

    def listar_historico_automacao(self) -> Dict[str, Any]:
        return self._leitura("/api/automacao/historico")

    def resumo_sebrae(self) -> Dict[str, Any]:
        return self._leitura("/api/automacao/sebrae/resumo")

    def consultar_historico_comparacao(self, evento_id: str) -> Dict[str, Any]:
        evento_id = evento_id.strip()
        if not evento_id or "/" in evento_id:
            return {"erro": "Identificador do histórico inválido."}
        return self._leitura(f"/api/historico-comparacoes/{evento_id}")

    def listar_divergencias_localidade(self) -> Dict[str, Any]:
        """Lista completa da seção 'Localidade divergente' do último cruzamento de planilhas."""
        ok, dados = self._chamar("GET", "/api/historico-comparacoes")
        if not ok:
            return {"erro": dados}
        eventos = dados.get("eventos", [])
        if not eventos:
            return {"mensagem": "Nenhum histórico de comparação registrado até o momento."}
        evento_id = eventos[0].get("id")
        ok, detalhe = self._chamar("GET", f"/api/historico-comparacoes/{evento_id}")
        if not ok:
            return {"erro": detalhe}
        divergencias = ((detalhe.get("evento") or {}).get("comparacao") or {}).get("divergencias_local") or []
        itens = [
            {
                "serie": d.get("serie", ""),
                "computador": d.get("computador", ""),
                "local_previsto": d.get("local_previsto", ""),
                "local_na_simpress": d.get("local_detalhes", ""),
            }
            for d in divergencias
        ]
        resultado: Dict[str, Any] = {
            "total": len(itens),
            "horario_comparacao": eventos[0].get("horario", ""),
            "itens": _aparar(itens),
        }
        seriais = {str(d.get("serie", "")).strip().upper() for d in divergencias} - {""}
        if seriais:
            ok_transf, dados_transf = self._chamar("GET", "/api/historico-transferencias")
            if not ok_transf:
                resultado["aviso_transferencias"] = "Não foi possível consultar o histórico de transferências agora."
            elif isinstance(dados_transf, dict):
                relacionadas = []
                for t in dados_transf.get("itens") or []:
                    if not isinstance(t, dict):
                        continue
                    serie_t = str(t.get("serial") or "").strip().upper()
                    if serie_t in seriais:
                        relacionadas.append({
                            "serie": serie_t,
                            "de": t.get("retirada_cidade", ""),
                            "para": t.get("entrega_cidade", ""),
                            "contato_entrega": t.get("entrega_contato", ""),
                            "observacao": t.get("entrega_obs", ""),
                        })
                resultado["transferencias_relacionadas"] = _aparar(relacionadas)
        return resultado

    def consultar_divergencia_localidade(self, serial: str) -> Dict[str, Any]:
        """Verifica, no último cruzamento de planilhas, se a série está na seção 'Localidade divergente'."""
        serial = serial.strip().upper()
        if not serial:
            return {"erro": "Número de série não informado."}
        ok, dados = self._chamar("GET", "/api/historico-comparacoes")
        if not ok:
            return {"erro": dados}
        eventos = dados.get("eventos", [])
        if not eventos:
            return {"mensagem": "Nenhum histórico de comparação registrado até o momento."}
        evento_id = eventos[0].get("id")
        ok, detalhe = self._chamar("GET", f"/api/historico-comparacoes/{evento_id}")
        if not ok:
            return {"erro": detalhe}
        divergencias = ((detalhe.get("evento") or {}).get("comparacao") or {}).get("divergencias_local") or []
        item = next((d for d in divergencias if str(d.get("serie", "")).strip().upper() == serial), None)
        if not item:
            return {
                "divergente": False,
                "mensagem": f"Série '{serial}' não está na lista de localidade divergente do último cruzamento ({eventos[0].get('horario', '')}).",
            }
        return {
            "divergente": True,
            "serie": serial,
            "computador": item.get("computador", ""),
            "local_previsto": item.get("local_previsto", ""),
            "local_na_simpress": item.get("local_detalhes", ""),
            "horario_comparacao": eventos[0].get("horario", ""),
        }

    def listar_unidades(self) -> Dict[str, Any]:
        """Todas as unidades com o id, para a IA conseguir editar qualquer uma."""
        ok, dados = self._chamar("GET", "/api/unidades")
        if not ok:
            return {"erro": dados}
        campos = ("id", "cidade", "endereco", "uf", "cep", "cnpj")
        unidades = [{k: u.get(k, "") for k in campos} for u in (dados if isinstance(dados, list) else []) if isinstance(u, dict)]
        return {"total": len(unidades), "unidades": unidades}

    def exportar_planilha(self, tipo: str, data: str = "", destino: Optional[Path] = None) -> Dict[str, Any]:
        """Baixa a planilha da rota oficial e salva em Downloads, sem sobrescrever arquivo existente."""
        tipo = tipo.strip().lower()
        if tipo not in EXPORTACOES:
            return {"sucesso": False, "erro": f"Tipo inválido: '{tipo}'. Opções: {', '.join(EXPORTACOES)}."}
        params: Dict[str, Any] = {}
        if tipo == "historico":
            # a rota exige o dia; sem pedido explícito, usa o da última comparação
            data = data.strip() or str(self.consultar_ultima_comparacao().get("horario", ""))[:10]
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", data):
                return {"sucesso": False, "erro": "Não há comparação no histórico para exportar."}
            params["data"] = data
        try:
            with self._client(timeout=60.0) as c:
                res = c.get(EXPORTACOES[tipo], params=params)
        except httpx.ConnectError:
            return {"sucesso": False, "erro": self._msg_offline()}
        except httpx.TimeoutException:
            return {"sucesso": False, "erro": "O Simpress demorou demais para gerar a planilha."}
        except Exception as e:
            return {"sucesso": False, "erro": f"Falha na comunicação com o Simpress: {e}"}
        if res.status_code != 200:
            return {"sucesso": False, "erro": self._erro_http(res)}
        achado = re.search(r'filename="?([^";]+)"?', res.headers.get("content-disposition", ""))
        nome = os.path.basename(achado.group(1).strip()) if achado else ""
        if not nome.lower().endswith(".xlsx"):
            nome = f"{tipo}.xlsx"
        pasta = Path(destino or PASTA_DOWNLOADS)
        pasta.mkdir(parents=True, exist_ok=True)
        alvo, n = pasta / nome, 1
        while alvo.exists():
            alvo, n = pasta / f"{Path(nome).stem} ({n}).xlsx", n + 1
        alvo.write_bytes(res.content)
        return {"sucesso": True, "arquivo": alvo.name, "pasta": str(pasta)}

    def listar_transferencias(self) -> Dict[str, Any]:
        resultado = self._leitura("/api/historico-transferencias")
        dados = resultado.get("dados")
        itens = dados.get("itens") if isinstance(dados, dict) else None
        if isinstance(itens, list):
            seriais = sorted({str(item.get("serial") or "").strip().upper() for item in itens if isinstance(item, dict)} - {""})
            hostnames: Dict[str, str] = {}
            for serial in seriais:
                ok, equip = self._chamar("GET", f"/api/equipamento/{serial}")
                if ok and isinstance(equip, dict):
                    hostnames[serial] = equip.get("apelido", "")
            for item in itens:
                if isinstance(item, dict):
                    item["hostname"] = hostnames.get(str(item.get("serial") or "").strip().upper(), "")
        return resultado

    def listar_pendencias_usuarios(self) -> Dict[str, Any]:
        return self._leitura("/api/usuarios/pendencias")

    # --- ações que alteram dados (só após confirmação do usuário) -------

    def _acao(self, caminho: str, corpo: Optional[Dict[str, Any]], sucesso: str) -> Dict[str, Any]:
        ok, dados = self._chamar("POST", caminho, corpo=corpo)
        if not ok:
            return {"sucesso": False, "erro": dados}
        return {"sucesso": True, "mensagem": sucesso}

    def executar_automacao(self, rotina: str) -> Dict[str, Any]:
        """Dispara uma rotina de automação pelo servidor. Sem plano B: em erro, não executa."""
        rotina_clean = rotina.strip().lower()
        if rotina_clean not in ROTINAS_VALIDAS:
            return {"sucesso": False, "erro": f"Rotina inválida: '{rotina}'. Opções aceitas: {', '.join(ROTINAS_VALIDAS)}."}
        ok, dados = self._chamar("POST", "/api/automacao/executar", corpo={"rotina": rotina_clean})
        if not ok:
            if "Erro 409" in str(dados):
                return {"sucesso": False, "erro": "Já existe uma automação em andamento. Aguarde o término ou cancele."}
            return {"sucesso": False, "erro": dados}
        return {"sucesso": True, "rotina": rotina_clean, "mensagem": f"Rotina '{rotina_clean}' disparada pelo servidor Simpress."}

    def cancelar_automacao(self) -> Dict[str, Any]:
        return self._acao("/api/automacao/cancelar", None, "Cancelamento solicitado ao servidor Simpress.")

    def atualizar_apelido(self, serial: str, apelido: str) -> Dict[str, Any]:
        serial, apelido = serial.strip().upper(), apelido.strip()
        if not serial:
            return {"sucesso": False, "erro": "Número de série não informado."}
        if len(apelido) > 160:
            return {"sucesso": False, "erro": "O apelido pode ter no máximo 160 caracteres."}
        return self._acao(
            "/api/equipamento/atualizar-apelido", {"serial": serial, "apelido": apelido},
            f"Apelido do serial {serial} atualizado.",
        )

    def atualizar_usuario(self, serial: str, usuario: str) -> Dict[str, Any]:
        serial, usuario = serial.strip().upper(), usuario.strip()
        if not serial:
            return {"sucesso": False, "erro": "Número de série não informado."}
        return self._acao(
            "/api/equipamento/atualizar-usuario", {"serial": serial, "usuario": usuario},
            f"Usuário do serial {serial} atualizado.",
        )

    def salvar_unidade(
        self, cidade: str, endereco: str, cnpj: str, uf: str = "PR", cep: str = "", id: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Edita (com id) ou cria (sem id) uma unidade. Recusa id que não existe na lista atual."""
        corpo: Dict[str, Any] = {
            "cidade": cidade.strip(), "endereco": endereco.strip(), "cnpj": cnpj.strip(),
            "uf": (uf or "PR").strip().upper(), "cep": (cep or "").strip(),
        }
        if not corpo["cidade"] or not corpo["endereco"] or not corpo["cnpj"]:
            return {"sucesso": False, "erro": "Cidade, endereço e CNPJ são obrigatórios."}
        if id not in (None, ""):
            try:
                corpo["id"] = int(id)
            except (TypeError, ValueError):
                return {"sucesso": False, "erro": f"Identificador de unidade inválido: {id}."}
            atual = self.listar_unidades()
            if "erro" in atual:
                return {"sucesso": False, "erro": atual["erro"]}
            if not any(str(u.get("id")) == str(corpo["id"]) for u in atual["unidades"]):
                return {"sucesso": False, "erro": f"Não existe unidade com id {corpo['id']}. Nada foi alterado."}
        feito = f"Unidade #{corpo['id']} ({corpo['cidade']}) atualizada." if "id" in corpo else f"Unidade {corpo['cidade']} criada."
        return self._acao("/api/unidade/salvar", corpo, feito)

    def decidir_pendencia_usuario(self, pendencia_id: str, decisao: str) -> Dict[str, Any]:
        pendencia_id, decisao = str(pendencia_id).strip(), decisao.strip().lower()
        if decisao not in DECISOES_VALIDAS:
            return {"sucesso": False, "erro": f"Decisão inválida. Opções: {', '.join(DECISOES_VALIDAS)}."}
        if not pendencia_id or "/" in pendencia_id:
            return {"sucesso": False, "erro": "Identificador da pendência inválido."}
        return self._acao(
            f"/api/usuarios/pendencias/{pendencia_id}/decidir", {"decisao": decisao},
            f"Pendência {pendencia_id}: decisão '{decisao}' registrada.",
        )
