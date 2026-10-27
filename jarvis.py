"""Aplicação Principal: Jarvis Simpress

Interface de terminal interativa com Rich, suporte a voz e conexão OpenRouter.
"""

import os
import sys
from dotenv import load_dotenv
from rich import print as rprint
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

# Carrega variáveis de ambiente do .env nesta pasta
load_dotenv()

from llm_client import LLMClient, MODELOS_CATALOGO
from simpress_client import SimpressClient
import voice

console = Console()


def exibir_banner(modelo_ativo: str, voz_ativa: bool, url_simpress: str = "http://127.0.0.1:8000"):
    """Exibe o cabeçalho inicial do Jarvis no terminal."""
    status_voz = "[bold green]LIGADA[/bold green]" if voz_ativa else "[dim]DESLIGADA[/dim]"
    info = (
        f"[bold cyan]Modelo Ativo:[/bold cyan] {modelo_ativo}\n"
        f"[bold cyan]Voz (Edge-TTS):[/bold cyan] {status_voz}\n"
        f"[bold cyan]Simpress Local:[/bold cyan] {url_simpress}\n\n"
        "[dim]Comandos rápidos: [bold]/modelos[/bold] (trocar IA) | [bold]/voz[/bold] (ligar/desligar áudio) | [bold]/ajuda[/bold] | [bold]sair[/bold][/dim]"
    )
    console.print(Panel(info, title="🤖 [bold white]JARVIS SIMPRESS[/bold white]", border_style="blue", expand=False))


def exibir_ajuda():
    """Exibe os comandos disponíveis."""
    tabela = Table(title="Comandos do Jarvis", border_style="cyan")
    tabela.add_column("Comando", style="bold yellow")
    tabela.add_column("Descrição")
    tabela.add_row("/modelos", "Lista os modelos mais rápidos e permite trocar na hora")
    tabela.add_row("/modelo <nome>", "Define diretamente qualquer modelo do OpenRouter")
    tabela.add_row("/voz", "Ativa ou desativa a fala por áudio")
    tabela.add_row("/chave <chave>", "Atualiza sua chave da API do OpenRouter")
    tabela.add_row("/limpar", "Limpa a memória recente da conversa")
    tabela.add_row("/ajuda", "Mostra esta lista de instruções")
    tabela.add_row("sair ou /sair", "Encerra o programa")
    console.print(tabela)


def listar_e_trocar_modelos(llm: LLMClient):
    """Exibe o catálogo de modelos recomendados e permite a seleção."""
    tabela = Table(title="Catálogo de Modelos Recomendados (OpenRouter)", border_style="magenta")
    tabela.add_column("Opção", justify="center", style="bold cyan")
    tabela.add_column("Identificador do Modelo", style="bold yellow")
    tabela.add_column("Vantagens / Perfil")

    for num, (slug, desc) in MODELOS_CATALOGO.items():
        marcador = " [bold green](Ativo)[/bold green]" if slug == llm.modelo_principal else ""
        tabela.add_row(num, f"{slug}{marcador}", desc)

    console.print(tabela)
    console.print("[dim]Você também pode digitar o nome exato de qualquer outro modelo do OpenRouter.[/dim]")

    escolha = Prompt.ask("\nEscolha o número ou digite o nome do modelo (ou Enter para cancelar)", default="").strip()
    if not escolha:
        return

    if escolha in MODELOS_CATALOGO:
        novo_slug = MODELOS_CATALOGO[escolha][0]
    else:
        novo_slug = escolha

    llm.trocar_modelo(novo_slug)
    console.print(f"[bold green]✔ Modelo alterado para:[/bold green] [yellow]{novo_slug}[/yellow]\n")


def checar_status_simpress(simpress: SimpressClient) -> bool:
    """Verifica se o servidor local do Simpress está respondendo."""
    try:
        res = simpress.consultar_status_automacao()
        return "erro" not in res
    except Exception:
        return False


def main():
    simpress = SimpressClient()
    llm = LLMClient(simpress)

    # Checagem de chave inicial
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key or api_key.startswith("sk-or-v1-coloque"):
        console.print(Panel(
            "[bold yellow]Atenção: Chave do OpenRouter não encontrada![/bold yellow]\n\n"
            "Abra o arquivo [bold].env[/bold] nesta pasta e cole a sua chave no campo:\n"
            "[green]OPENROUTER_API_KEY=sk-or-v1-...[/green]\n\n"
            "Ou digite agora mesmo o comando: [bold]/chave sk-or-v1-...[/bold]",
            title="🔑 Configuração Inicial",
            border_style="yellow",
        ))

    # Checagem do Simpress
    simpress_online = checar_status_simpress(simpress)
    if not simpress_online:
        console.print(f"[dim yellow]Aviso: O Simpress local em {simpress.base_url} parece estar desligado no momento.\n(Você pode conversar, mas as ferramentas de consulta ao inventário só funcionarão quando o Simpress for iniciado).[/dim yellow]\n")

    exibir_banner(llm.modelo_principal, voice.HABILITAR_VOZ, simpress.base_url)

    while True:
        try:
            pergunta = Prompt.ask("\n[bold green]Você[/bold green]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[bold cyan]Até logo![/bold cyan]")
            break

        if not pergunta:
            continue

        # Comandos internos
        cmd = pergunta.lower()
        if cmd in ("sair", "/sair", "exit", "quit"):
            console.print("[bold cyan]Encerrando o Jarvis. Até mais![/bold cyan]")
            break

        if cmd in ("/ajuda", "ajuda", "help", "/help"):
            exibir_ajuda()
            continue

        if cmd in ("/modelos", "/modelo"):
            listar_e_trocar_modelos(llm)
            continue

        if cmd.startswith("/modelo "):
            novo = pergunta.split(" ", 1)[1].strip()
            if novo:
                llm.trocar_modelo(novo)
                console.print(f"[bold green]✔ Modelo ativo:[/bold green] [yellow]{novo}[/yellow]")
            continue

        if cmd in ("/voz", "voz"):
            novo_estado = voice.alternar_voz()
            estado_texto = "[bold green]LIGADA[/bold green]" if novo_estado else "[bold red]DESLIGADA[/bold red]"
            console.print(f"Áudio e fala: {estado_texto}")
            continue

        if cmd.startswith("/chave "):
            nova_chave = pergunta.split(" ", 1)[1].strip()
            llm.atualizar_chave(nova_chave)
            console.print("[bold green]✔ Chave do OpenRouter atualizada com sucesso para esta sessão![/bold green]")
            continue

        if cmd == "/limpar":
            llm.limpar_historico()
            console.print("[bold cyan]✔ Memória recente da conversa foi reiniciada.[/bold cyan]")
            continue

        # Fluxo de consulta à IA com status animado
        status_msg = "Consultando Simpress / Pensando..."
        with console.status(f"[bold cyan]{status_msg}[/bold cyan]", spinner="dots") as spinner:
            def atualizar_spinner(msg: str):
                spinner.update(f"[bold cyan]{msg}[/bold cyan]")

            resposta = llm.enviar_mensagem(pergunta, callback_status=atualizar_spinner)

            # Alterações só acontecem depois da confirmação do usuário.
            while resposta.pendente:
                spinner.stop()
                console.print(Panel(
                    resposta.pendente["descricao"],
                    title="Confirmar alteração",
                    border_style="yellow",
                    expand=False,
                ))
                aceitou = Confirm.ask("Confirmar e executar?", default=False)
                spinner.start()
                resposta = llm.resolver_confirmacao(aceitou, callback_status=atualizar_spinner)

        # Exibe quais ferramentas foram acionadas (se houver)
        if resposta.ferramentas:
            ferramentas_fmt = ", ".join(f"[bold cyan]{f}[/bold cyan]" for f in resposta.ferramentas)
            console.print(f"[dim]Ferramentas acionadas: {ferramentas_fmt}[/dim]")

        # Exibe a resposta formatada
        console.print("\n[bold blue]🤖 Jarvis:[/bold blue]")
        console.print(Markdown(resposta.texto))

        # A voz fala os nomes reais; o Edge-TTS envia esse texto à Microsoft.
        voice.falar(resposta.texto_voz)


if __name__ == "__main__":
    main()
