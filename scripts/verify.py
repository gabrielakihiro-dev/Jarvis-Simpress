"""Verificação local e de CI: compileall, pytest e busca de credenciais nos arquivos rastreados."""
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PADROES = [re.compile(r"sk-or-[A-Za-z0-9-]{20,}"), re.compile(r"OPENROUTER_API_KEY\s*=\s*(?!\S*\.\.\.)\S{10,}")]  # "..." = placeholder em mensagens
EXCLUIR = r"[\/](\.venv|\.venv313|\.claude|\.git|data|modelos_voz)([\/]|$)"
IGNORADOS = {".env.example", "scripts/verify.py"}  # o script contém os próprios padrões


def comando(nome, args):
    print(f"\n== {nome}: {' '.join(args[1:])}", flush=True)
    return subprocess.run(args, cwd=RAIZ).returncode == 0


def credenciais():
    print("\n== credenciais: git ls-files", flush=True)
    r = subprocess.run(["git", "ls-files"], cwd=RAIZ, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr.strip() or "git ls-files falhou")
        return False
    achados = []
    for rel in r.stdout.splitlines():
        if rel in IGNORADOS or not (RAIZ / rel).is_file():
            continue
        try:
            linhas = (RAIZ / rel).read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        achados += [f"{rel}:{n}" for n, l in enumerate(linhas, 1) if any(p.search(l) for p in PADROES)]
    for a in achados:
        print("possível credencial em", a)
    return not achados


def main():
    py = sys.executable
    etapas = [
        ("compileall", comando("compileall", [py, "-m", "compileall", "-q", "-x", EXCLUIR, "."])),
        ("pytest", comando("pytest", [py, "-m", "pytest", "-q"])),
        ("credenciais", credenciais()),
    ]
    print("\n== Resumo")
    for nome, ok in etapas:
        print(f"  {'OK   ' if ok else 'FALHOU'} {nome}")
    return 0 if all(ok for _, ok in etapas) else 1


if __name__ == "__main__":
    sys.exit(main())
