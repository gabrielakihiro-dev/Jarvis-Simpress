"""Módulo de ferramentas do Simpress para o Jarvis.

Define as funções de consulta ao parque de computadores e ordens de serviço,
abertura segura do Chrome de automação e o catálogo de ferramentas (OpenAI / OpenRouter).
"""

import json
import os
from pathlib import Path
import subprocess
import time
from typing import Any, Dict, List, Optional
import urllib.parse
import urllib.request

from simpress_client import SimpressClient

# Diretório e porta do Chrome de Automação (alinhado com as regras do Simpress)
CHROME_PROFILE_DIR = Path(os.environ.get("SIMPRESS_CHROME_PROFILE", str(Path.home() / ".chrome-automation")))
CDP_PORT = int(os.environ.get("SIMPRESS_CHROME_PORT", "9333"))
CDP_URL = f"http://127.0.0.1:{CDP_PORT}"

URL_ORACLE = "https://simpress.custhelp.com/AgentWeb/"
URL_UX = "https://ux.simpress.com.br/MeusEquipamentos/Index"
URL_ENDPOINT = "https://centralendpoint.pr.sebrae.com.br/webclient#/uems/inventory/computers"


def localizar_chrome() -> Optional[Path]:
    """Procura pelo executável do Google Chrome nos locais padrão do Windows."""
    candidatos = [
        Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
    ]
    for c in candidatos:
        if c.is_file():
            return c
    return None


def chrome_cdp_ativo() -> bool:
    """Verifica se o Chrome de automação já está escutando na porta CDP local."""
    try:
        with urllib.request.urlopen(f"{CDP_URL}/json/version", timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False


def obter_abas_ativas() -> List[Dict[str, Any]]:
    """Consulta a lista de alvos (abas) abertas no Chrome via protocolo CDP."""
    try:
        req = urllib.request.Request(f"{CDP_URL}/json/list")
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode("utf-8"))
    except Exception:
        pass
    return []


def abrir_aba_cdp(url: str) -> bool:
    """Abre uma nova aba com a URL indicada no Chrome em execução via API do CDP."""
    try:
        url_escaped = urllib.parse.quote(url, safe=":/?=&-_.~")
        endpoint = f"{CDP_URL}/json/new?{url_escaped}"
        req = urllib.request.Request(endpoint, method="PUT")
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            return resp.status in (200, 201)
    except Exception:
        try:
            req = urllib.request.Request(f"{CDP_URL}/json/new?{urllib.parse.quote(url, safe=':/?=&-_.~')}")
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                return resp.status in (200, 201)
        except Exception:
            return False


def iniciar_chrome_automacao() -> Dict[str, Any]:
    """Inicia o Google Chrome em processo isolado na porta 9333 com perfil exclusivo.

    Se o Chrome já estiver aberto e o usuário tiver fechado uma ou todas as abas,
    detecta as abas faltantes e as reabre automaticamente!
    """
    sistemas = [
        ("Oracle Service Cloud", URL_ORACLE, "custhelp.com"),
        ("UX Simpress", URL_UX, "ux.simpress.com.br"),
        ("Endpoint Central", URL_ENDPOINT, "centralendpoint.pr.sebrae.com.br"),
    ]

    # 1. Se o Chrome já está ativo, verifica e restaura as abas
    if chrome_cdp_ativo():
        abas = obter_abas_ativas()
        urls_abertas = [a.get("url", "").lower() for a in abas if isinstance(a, dict)]

        reabertas = []
        for nome_sis, url_sis, dominio in sistemas:
            ja_aberta = any(dominio in u for u in urls_abertas)
            if not ja_aberta:
                if abrir_aba_cdp(url_sis):
                    reabertas.append(nome_sis)

        if reabertas:
            return {
                "sucesso": True,
                "status": "abas_restauradas",
                "mensagem": (
                    f"O Chrome de automação já estava ativo na porta {CDP_PORT}. "
                    f"Restaurei a(s) aba(s) que estavam fechadas: **{', '.join(reabertas)}**! "
                    "Agora você pode realizar o login com tranquilidade."
                ),
            }
        else:
            # Todas já estavam abertas ou o usuário quer reabri-las para garantir
            for _, url_sis, _ in sistemas:
                abrir_aba_cdp(url_sis)
            return {
                "sucesso": True,
                "status": "reabertas",
                "mensagem": (
                    f"O Chrome de automação está ativo na porta {CDP_PORT}. "
                    "Reabri as abas do Oracle, UX Simpress e Endpoint Central conforme solicitado."
                ),
            }

    # 2. Se o Chrome não está ativo, inicia o processo do zero
    caminho_chrome = localizar_chrome()
    if not caminho_chrome:
        return {
            "sucesso": False,
            "erro": "Google Chrome não encontrado nos caminhos padrão do sistema. Instale o Chrome para utilizar a automação.",
        }

    CHROME_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    flags = 0
    if os.name == "nt":
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

    try:
        subprocess.Popen(
            [
                str(caminho_chrome),
                f"--remote-debugging-port={CDP_PORT}",
                f"--user-data-dir={CHROME_PROFILE_DIR}",
                "--no-first-run",
                "--no-default-browser-check",
                "--start-maximized",
                "--restore-last-session",
                URL_ORACLE,
                URL_UX,
                URL_ENDPOINT,
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
            close_fds=True,
        )

        # Aguarda brevemente a porta responder
        limite = time.time() + 6
        while time.time() < limite:
            if chrome_cdp_ativo():
                break
            time.sleep(0.5)

        return {
            "sucesso": True,
            "status": "iniciado",
            "mensagem": (
                f"Chrome de automação aberto com sucesso na porta {CDP_PORT}!\n"
                f"Perfil dedicado: {CHROME_PROFILE_DIR}\n"
                "As abas do Oracle, UX Simpress e Endpoint Central foram carregadas. "
                "Você pode fazer seu login manualmente com total segurança; o navegador permanecerá aberto."
            ),
        }
    except Exception as e:
        return {"sucesso": False, "erro": f"Falha ao iniciar o Chrome de automação: {str(e)}"}


# Esquema oficial das ferramentas para o modelo de linguagem (OpenAI / OpenRouter)
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "executar_automacao_chrome",
            "description": "Executa uma das rotinas de automação no Google Chrome. Opções de rotina: 'login' (abre as abas do Oracle, UX Simpress e Endpoint para login), 'inventarios' (exporta e atualiza inventários do UX Simpress e Endpoint Central), 'os' (exporta chamados e ordens de serviço do Oracle e UX Simpress), 'ambas' (executa OS e Inventários em sequência), 'usuarios' (executa verificação de usuários logados), 'sebrae' (sincroniza chamados Sebrae do SoftExpert).",
            "parameters": {
                "type": "object",
                "properties": {
                    "rotina": {
                        "type": "string",
                        "enum": ["login", "inventarios", "os", "ambas", "usuarios", "sebrae"],
                        "description": "O nome da rotina que deve ser executada.",
                    }
                },
                "required": ["rotina"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancelar_automacao_chrome",
            "description": "Interrompe com segurança qualquer rotina de automação que esteja sendo executada no momento, sem fechar o navegador nem perder os logins.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "abrir_chrome_automacao",
            "description": "Abre o navegador Google Chrome em modo de automação próprio (porta 9333 e perfil isolado ~/.chrome-automation) com as abas do Oracle Service Cloud, UX Simpress e Endpoint Central prontas para o usuário realizar login manualmente. Use sempre que o usuário pedir para abrir o Chrome, autenticar ou preparar os acessos.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_equipamento",
            "description": "Consulta detalhes de um equipamento específico pelo número de série (localização, modelo, tipo, cidade e usuário associado). Trata automaticamente MacBooks que possam vir sem a letra 'S'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "serial": {
                        "type": "string",
                        "description": "O número de série da máquina (exemplo: 'BRJ149SCJG', 'CMVXKV7YCM', 'PF3ABC12').",
                    }
                },
                "required": ["serial"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pesquisar_catalogo",
            "description": "Pesquisa equipamentos no catálogo aplicando filtros de texto, cidade, categoria ou status de usuário logado.",
            "parameters": {
                "type": "object",
                "properties": {
                    "termo": {
                        "type": "string",
                        "description": "Termo de busca como modelo ou parte da série (ex.: 'ProBook', 'Dell').",
                    },
                    "cidade": {
                        "type": "string",
                        "description": "Filtrar por cidade (ex.: 'Curitiba', 'Maringá', 'Cascavel').",
                    },
                    "categoria": {
                        "type": "string",
                        "description": "Categoria do equipamento (ex.: 'notebook', 'macbook', 'desktop').",
                    },
                    "usuario": {
                        "type": "string",
                        "enum": ["sem", "com"],
                        "description": "'sem' para equipamentos sem usuário logado; 'com' para os que têm usuário.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "obter_totais_inventario",
            "description": "Retorna as estatísticas oficiais da base de equipamentos Simpress: total de máquinas cadastradas, total de unidades e alterações pendentes de exportação.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "listar_chamados_abertos",
            "description": "Lista os chamados técnicos e ordens de serviço (OS) em andamento, indicando quais estão conferidos e quais apresentam divergências.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_status_automacao",
            "description": "Verifica se alguma rotina de automação de navegador (Chrome) está sendo executada no momento, qual rotina e seu status de progresso.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_ultima_comparacao",
            "description": "Retorna a data e o resumo do último cruzamento de planilhas de inventário (total de divergências, equipamentos ausentes no Endpoint ou na Simpress).",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
]


class SimpressToolbox:
    """Caixa de ferramentas que executa as chamadas solicitadas pelo agente."""

    def __init__(self, client: Optional[SimpressClient] = None):
        self.client = client or SimpressClient()

    def execute(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Despacha a ferramenta correta conforme o nome retornado pela IA."""
        if tool_name == "executar_automacao_chrome":
            rotina = args.get("rotina", "os")
            if rotina == "login":
                return iniciar_chrome_automacao()
            return self.client.executar_automacao(rotina)
        elif tool_name == "cancelar_automacao_chrome":
            return self.client.cancelar_automacao()
        elif tool_name == "abrir_chrome_automacao":
            return iniciar_chrome_automacao()
        elif tool_name == "consultar_equipamento":
            return self.client.consultar_equipamento(args.get("serial", ""))
        elif tool_name == "pesquisar_catalogo":
            return self.client.pesquisar_catalogo(
                termo=args.get("termo", ""),
                cidade=args.get("cidade"),
                categoria=args.get("categoria"),
                usuario=args.get("usuario"),
            )
        elif tool_name == "obter_totais_inventario":
            return self.client.obter_totais_inventario()
        elif tool_name == "listar_chamados_abertos":
            return self.client.listar_chamados_abertos()
        elif tool_name == "consultar_status_automacao":
            return self.client.consultar_status_automacao()
        elif tool_name == "consultar_ultima_comparacao":
            return self.client.consultar_ultima_comparacao()
        else:
            return {"erro": f"Ferramenta desconhecida: {tool_name}"}
