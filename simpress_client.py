"""Cliente de comunicação com a API local do Simpress (http://127.0.0.1:8000).

Implementa as 6 ferramentas de leitura do inventário e a camada de sanitização
de dados pessoais (LGPD) antes do envio para a inteligência artificial.
"""

import os
from pathlib import Path
import re
import subprocess
from typing import Any, Dict, List, Optional
import httpx

SIMPRESS_URL = os.environ.get("SIMPRESS_URL", "http://127.0.0.1:8000").rstrip("/")
TIMEOUT = 10.0

# Padrões para limpeza de dados sensíveis em textos livres (chamados e anotações)
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
PHONE_PATTERN = re.compile(r"(\(?\d{2}\)?\s?)?(\d{4,5}[-\s]?\d{4})")


def limpar_texto_sensivel(texto: Any) -> str:
    """Remove e-mails e telefones de textos livres para conformidade com a LGPD."""
    if not texto:
        return ""
    limpo = str(texto)
    limpo = EMAIL_PATTERN.sub("[E-MAIL OCULTADO]", limpo)
    limpo = PHONE_PATTERN.sub("[TELEFONE OCULTADO]", limpo)
    return limpo.strip()


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


class SimpressClient:
    """Cliente para consulta das rotas do Simpress."""

    def __init__(self, base_url: str = SIMPRESS_URL):
        self.base_url = base_url

    def _client(self) -> httpx.Client:
        return httpx.Client(base_url=self.base_url, timeout=TIMEOUT)

    def consultar_equipamento(self, serial: str) -> Dict[str, Any]:
        """Consulta os dados de um equipamento pelo número de série.

        Aplica a regra de MacBooks do AGENTS.md (adiciona 'S' se necessário)
        e fallback de busca por aproximação se o serial exato não for achado.
        """
        clean_serial = serial.strip().upper()
        if not clean_serial:
            return {"erro": "Número de série não informado."}

        with self._client() as client:
            # 1. Tentativa direta com o serial fornecido
            try:
                res = client.get(f"/api/equipamento/{clean_serial}")
                if res.status_code == 200:
                    return {"encontrado": True, "equipamento": sanitizar_equipamento(res.json())}
            except httpx.ConnectError:
                return {"erro": "Não foi possível conectar ao Simpress local (127.0.0.1:8000). O servidor está ligado?"}
            except Exception as e:
                return {"erro": f"Falha na consulta: {str(e)}"}

            # 2. Regra de MacBooks: se não achou e não tem 'S', tenta com 'S' inicial
            if not clean_serial.startswith("S"):
                try:
                    res_mac = client.get(f"/api/equipamento/S{clean_serial}")
                    if res_mac.status_code == 200:
                        dados = sanitizar_equipamento(res_mac.json())
                        dados["observacao"] = f"Equipamento localizado na base oficial com o prefixo 'S' (S{clean_serial})."
                        return {"encontrado": True, "equipamento": dados}
                except Exception:
                    pass

            # 3. Fallback: busca por correspondência parcial
            try:
                res_busca = client.get("/api/buscar", params={"q": clean_serial})
                if res_busca.status_code == 200:
                    itens = res_busca.json()
                    if isinstance(itens, list) and len(itens) > 0:
                        return {
                            "encontrado": True,
                            "observacao": "Série exata não localizada, mas encontramos correspondências aproximadas:",
                            "correspondencias": [sanitizar_equipamento(item) for item in itens[:3]],
                        }
            except Exception:
                pass

        return {"encontrado": False, "mensagem": f"O equipamento com número de série '{serial}' não foi encontrado no cadastro oficial."}

    def pesquisar_catalogo(
        self,
        termo: str = "",
        cidade: Optional[str] = None,
        categoria: Optional[str] = None,
        usuario: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Pesquisa equipamentos no catálogo com filtros por cidade, categoria ou status de usuário."""
        params: Dict[str, Any] = {"limit": 15, "offset": 0}
        if termo:
            params["q"] = termo
        if cidade:
            params["cidade"] = cidade
        if categoria:
            params["categoria"] = categoria
        if usuario in ("sem", "com"):
            params["usuario"] = usuario

        # Se não há termo e nem filtro de sem usuário, busca expandida requer listar_todos=true
        if not termo and usuario != "sem":
            params["listar_todos"] = "true"

        with self._client() as client:
            try:
                res = client.get("/api/buscar-expandida", params=params)
                if res.status_code == 200:
                    dados = res.json()
                    itens_brutos = dados.get("items", [])
                    return {
                        "total_encontrados": dados.get("total", 0),
                        "itens": [sanitizar_equipamento(item) for item in itens_brutos],
                    }
                return {"erro": f"Erro na pesquisa (Código {res.status_code}): {res.text}"}
            except httpx.ConnectError:
                return {"erro": "Servidor Simpress inacessível em http://127.0.0.1:8000."}
            except Exception as e:
                return {"erro": f"Erro na busca: {str(e)}"}

    def obter_totais_inventario(self) -> Dict[str, Any]:
        """Retorna os totais oficiais do cadastro da Simpress, unidades e pendências."""
        with self._client() as client:
            try:
                res = client.get("/api/stats")
                if res.status_code == 200:
                    stats = res.json()
                    return {
                        "total_equipamentos_oficial": stats.get("total_equipamentos", 0),
                        "total_unidades": stats.get("total_unidades", 0),
                        "base_importada": stats.get("base_importada", False),
                        "arquivo_origem": stats.get("arquivo_origem", ""),
                        "ultima_atualizacao": stats.get("ultima_atualizacao", ""),
                        "alteracoes_exportaveis": stats.get("total_alteracoes_exportaveis", 0),
                    }
                return {"erro": f"Não foi possível obter estatísticas ({res.status_code})."}
            except httpx.ConnectError:
                return {"erro": "Servidor Simpress local desconectado."}
            except Exception as e:
                return {"erro": str(e)}

    def listar_chamados_abertos(self) -> Dict[str, Any]:
        """Retorna a lista atual de chamados e a relação com as ordens de serviço (OS)."""
        with self._client() as client:
            try:
                res = client.get("/api/operacoes/chamados")
                if res.status_code == 200:
                    dados = res.json()
                    chamados_brutos = dados.get("chamados", [])
                    resumo = dados.get("resumo", {})
                    return {
                        "atualizado_em": dados.get("atualizado_em", ""),
                        "total_chamados": len(chamados_brutos),
                        "resumo": resumo,
                        "chamados": [sanitizar_chamado(ch) for ch in chamados_brutos[:20]],
                    }
                return {"erro": f"Erro ao consultar chamados ({res.status_code})."}
            except httpx.ConnectError:
                return {"erro": "Servidor Simpress local desconectado."}
            except Exception as e:
                return {"erro": str(e)}

    def consultar_status_automacao(self) -> Dict[str, Any]:
        """Verifica se há alguma rotina de automação no Google Chrome em andamento."""
        with self._client() as client:
            try:
                res = client.get("/api/automacao/estado")
                if res.status_code == 200:
                    dados = res.json()
                    return {
                        "executando": dados.get("executando", False),
                        "rotina": dados.get("rotina", "nenhuma"),
                        "status": dados.get("status", "ocioso"),
                        "progresso": dados.get("progresso", ""),
                        "mensagem": dados.get("mensagem", ""),
                    }
                return {"erro": f"Erro ao verificar automação ({res.status_code})."}
            except httpx.ConnectError:
                return {"erro": "Servidor Simpress local desconectado."}
            except Exception as e:
                return {"erro": str(e)}

    def consultar_ultima_comparacao(self) -> Dict[str, Any]:
        """Consulta o resumo do último cruzamento de planilhas realizado no Simpress."""
        with self._client() as client:
            try:
                res = client.get("/api/historico-comparacoes")
                if res.status_code == 200:
                    dados = res.json()
                    eventos = dados.get("eventos", [])
                    if not eventos:
                        return {"mensagem": "Nenhum histórico de comparação registrado até o momento."}
                    ultimo = eventos[0]
                    return {
                        "horario": ultimo.get("horario", ""),
                        "tipo": ultimo.get("tipo", ""),
                        "resumo_divergencias": ultimo.get("resumo", {}),
                    }
                return {"erro": f"Erro ao consultar histórico ({res.status_code})."}
            except httpx.ConnectError:
                return {"erro": "Servidor Simpress local desconectado."}
            except Exception as e:
                return {"erro": str(e)}

    def executar_automacao(self, rotina: str) -> Dict[str, Any]:
        """Dispara uma rotina de automação no Chrome (login, os, inventarios, ambas, usuarios, sebrae).

        Prioriza a rota da API do servidor FastAPI (127.0.0.1:8000). Caso o servidor
        esteja desligado, aciona diretamente o script Python de automação do projeto Simpress.
        """
        rotinas_validas = ("login", "os", "inventarios", "ambas", "usuarios", "sebrae")
        rotina_clean = rotina.strip().lower()
        if rotina_clean not in rotinas_validas:
            return {
                "sucesso": False,
                "erro": f"Rotina inválida: '{rotina}'. Opções aceitas: {', '.join(rotinas_validas)}.",
            }

        # 1. Tenta acionar via API do servidor Simpress
        with self._client() as client:
            try:
                res = client.post("/api/automacao/executar", json={"rotina": rotina_clean})
                if res.status_code in (200, 202):
                    return {
                        "sucesso": True,
                        "metodo": "api_simpress",
                        "rotina": rotina_clean,
                        "mensagem": f"Rotina de automação '{rotina_clean}' disparada com sucesso via servidor Simpress.",
                    }
                elif res.status_code == 409:
                    return {
                        "sucesso": False,
                        "erro": "Já existe uma automação em andamento no momento. Aguarde o término ou use cancelar.",
                    }
            except httpx.ConnectError:
                pass  # Servidor Simpress não está respondendo na porta 8000, usa fallback local
            except Exception as e:
                pass

        # 2. Fallback: Disparo direto do script Python do Simpress
        simpress_dir = Path(r"C:\Users\Gabriel\Desktop\Simpress")
        py_exe = simpress_dir / ".venv" / "Scripts" / "python.exe"
        script = simpress_dir / "scripts" / "automacao_rotinas_chrome.py"

        if not py_exe.is_file() or not script.is_file():
            return {
                "sucesso": False,
                "erro": "Ambiente de automação do Simpress não localizado em C:\\Users\\Gabriel\\Desktop\\Simpress.",
            }

        flags = 0
        if os.name == "nt":
            flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

        try:
            subprocess.Popen(
                [str(py_exe), str(script), "--rotina", rotina_clean],
                cwd=str(simpress_dir),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=flags,
                close_fds=True,
            )
            return {
                "sucesso": True,
                "metodo": "script_direto",
                "rotina": rotina_clean,
                "mensagem": f"Rotina de automação '{rotina_clean}' iniciada com sucesso no Chrome de automação (porta 9333).",
            }
        except Exception as e:
            return {"sucesso": False, "erro": f"Falha ao iniciar o script de automação: {str(e)}"}

    def cancelar_automacao(self) -> Dict[str, Any]:
        """Solicita o cancelamento seguro de qualquer rotina de automação em execução."""
        # 1. Tenta via API do servidor
        with self._client() as client:
            try:
                res = client.post("/api/automacao/cancelar")
                if res.status_code in (200, 202):
                    return {"sucesso": True, "mensagem": "Cancelamento solicitado com sucesso ao servidor Simpress."}
            except Exception:
                pass

        # 2. Fallback: sinaliza via script --cancelar
        simpress_dir = Path(r"C:\Users\Gabriel\Desktop\Simpress")
        py_exe = simpress_dir / ".venv" / "Scripts" / "python.exe"
        script = simpress_dir / "scripts" / "automacao_rotinas_chrome.py"

        if py_exe.is_file() and script.is_file():
            try:
                subprocess.run(
                    [str(py_exe), str(script), "--cancelar"],
                    cwd=str(simpress_dir),
                    capture_output=True,
                    timeout=10,
                )
                return {"sucesso": True, "mensagem": "Sinal de cancelamento enviado à rotina de automação."}
            except Exception as e:
                return {"sucesso": False, "erro": f"Erro ao cancelar: {str(e)}"}

        return {"sucesso": False, "erro": "Não foi possível enviar o sinal de cancelamento."}
