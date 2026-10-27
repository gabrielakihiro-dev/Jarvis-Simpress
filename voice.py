"""Módulo de Síntese de Voz (Text-to-Speech) assíncrono para o Jarvis.

Gera áudio em português via Microsoft Edge TTS e reproduz em segundo plano
(em uma thread separada) para que o terminal NUNCA congele ou trave.
"""

import asyncio
import os
import re
import subprocess
import tempfile
import threading
import time
from typing import Optional

try:
    import edge_tts
    TTS_DISPONIVEL = True
except ImportError:
    TTS_DISPONIVEL = False

VOZ_PADRAO = os.environ.get("VOZ_NOME", "pt-BR-AntonioNeural")
HABILITAR_VOZ = os.environ.get("HABILITAR_VOZ", "true").lower() in ("1", "true", "yes", "sim")


def limpar_markdown_para_fala(texto: str) -> str:
    """Remove caracteres de formatação (asteriscos, tabelas, hashtags) para leitura natural."""
    if not texto:
        return ""
    limpo = re.sub(r"```[\s\S]*?```", "Código omitido.", texto)
    limpo = re.sub(r"`([^`]+)`", r"\1", limpo)
    limpo = re.sub(r"#+\s*", "", limpo)
    limpo = re.sub(r"\*\*([^*]+)\*\*", r"\1", limpo)
    limpo = re.sub(r"\*([^*]+)\*", r"\1", limpo)
    limpo = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", limpo)
    limpo = re.sub(r"[-_*]{3,}", "", limpo)
    limpo = re.sub(r"\|[\s\-:]+\|", "", limpo)
    limpo = limpo.replace("|", ", ")
    return limpo.strip()


def trechos(texto: str, limite: int = 300) -> list:
    """Divide a fala em trechos: o 1º é só a primeira frase, para a voz começar logo."""
    frases = [f for f in re.split(r"(?<=[.!?;:])\s+|\n+", limpar_markdown_para_fala(texto)) if f.strip()]
    saida: list = []
    for f in frases:
        if len(saida) > 1 and len(saida[-1]) + len(f) < limite:
            saida[-1] += " " + f
        else:
            saida.append(f)
    return saida


async def _gerar_audio_edge(texto: str, arquivo_destino: str, voz: str):
    """Gera o arquivo mp3 usando edge-tts assincronamente."""
    comunicador = edge_tts.Communicate(texto, voz)
    await comunicador.save(arquivo_destino)


def _executar_reproducao(arquivo_mp3: str):
    """Executa o player em segundo plano e apaga o arquivo temporário ao final."""
    caminho = os.path.abspath(arquivo_mp3).replace("'", "''")
    # Script PowerShell com encerramento garantido e sem loops infinitos
    ps_cmd = (
        f"$w = New-Object -ComObject WMPlayer.OCX; "
        f"$w.settings.volume = 100; "
        f"$w.URL = '{caminho}'; "
        f"$w.controls.play(); "
        f"$t = 0; while (($w.playState -eq 9 -or $w.playState -eq 0) -and $t -lt 200) {{ Start-Sleep -Milliseconds 50; $t++ }}; "
        f"while ($w.playState -eq 3 -or $w.playState -eq 6) {{ Start-Sleep -Milliseconds 50 }}; "
        f"$w.controls.stop(); $w.close()"
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=40,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        pass
    finally:
        try:
            if os.path.exists(arquivo_mp3):
                os.remove(arquivo_mp3)
        except Exception:
            pass


def _thread_falar(texto_fala: str, voz: str):
    """Thread em segundo plano que gera o mp3 e toca sem bloquear o terminal."""
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tf:
            temp_path = tf.name

        # Gera o áudio com o Microsoft Edge TTS
        asyncio.run(_gerar_audio_edge(texto_fala, temp_path, voz))

        # Toca o áudio
        _executar_reproducao(temp_path)
    except Exception:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


def gerar_mp3(texto: str, voz: Optional[str] = None) -> Optional[str]:
    """Gera o mp3 da fala e devolve o caminho (quem chama toca e apaga). None se não der."""
    fala = limpar_markdown_para_fala(texto)
    if not TTS_DISPONIVEL or not fala:
        return None
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tf:
        caminho = tf.name
    try:
        asyncio.run(_gerar_audio_edge(fala, caminho, voz or os.environ.get("VOZ_NOME", VOZ_PADRAO)))
        return caminho
    except Exception:
        os.path.exists(caminho) and os.remove(caminho)
        return None


def falar(texto: str, voz: Optional[str] = None) -> bool:
    """Dispara a síntese de voz em segundo plano (não trava o terminal para digitação)."""
    if not HABILITAR_VOZ or not TTS_DISPONIVEL:
        return False

    texto_fala = limpar_markdown_para_fala(texto)
    if not texto_fala:
        return False

    voz_escolhida = voz or os.environ.get("VOZ_NOME", VOZ_PADRAO)

    # Inicia em thread daemon para liberar o terminal IMEDIATAMENTE
    t = threading.Thread(target=_thread_falar, args=(texto_fala, voz_escolhida), daemon=True)
    t.start()
    return True


def alternar_voz(estado: Optional[bool] = None) -> bool:
    """Liga ou desliga o áudio dinamicamente."""
    global HABILITAR_VOZ
    if estado is None:
        HABILITAR_VOZ = not HABILITAR_VOZ
    else:
        HABILITAR_VOZ = estado
    return HABILITAR_VOZ
