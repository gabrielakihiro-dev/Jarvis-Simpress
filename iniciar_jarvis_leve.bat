@echo off
chcp 65001 > nul
title J.A.R.V.I.S Simpress - Modo Leve
echo ========================================================
echo      INICIANDO O J.A.R.V.I.S SIMPRESS (MODO LEVE)
echo ========================================================
echo.
cd /d "%~dp0"
rem Modo leve: sem janela, voz nem Chrome. So o servidor local que o painel do Simpress usa.
if not exist ".venv-leve\Scripts\python.exe" (
    echo [1/3] Criando ambiente virtual .venv-leve...
    py -3.13 --version > nul 2>&1
    if errorlevel 1 (
        py -3 --version > nul 2>&1
        if errorlevel 1 (python -m venv .venv-leve) else (py -3 -m venv .venv-leve)
    ) else (
        py -3.13 -m venv .venv-leve
    )
)
if not exist ".venv-leve\Scripts\python.exe" (
    echo Nao foi possivel criar o ambiente virtual. Instale o Python 3.13.
    pause
    exit /b 1
)
set "PY=%~dp0.venv-leve\Scripts\python.exe"
rem So reinstala quando requirements-leve.txt mudou desde a ultima instalacao.
fc /b "requirements-leve.txt" ".venv-leve\requirements.instalado" > nul 2>&1
if errorlevel 1 (
    echo [2/3] Instalando dependencias leves...
    "%PY%" -m pip install -q -r requirements-leve.txt
    if errorlevel 1 (
        echo.
        echo Falha ao instalar as dependencias. Veja a mensagem acima.
        pause
        exit /b 1
    )
    copy /y "requirements-leve.txt" ".venv-leve\requirements.instalado" > nul
) else (
    echo [2/3] Dependencias ja instaladas.
)
echo [3/3] Iniciando o servidor do modo leve...
echo.
set "JARVIS_MODO_LEVE=1"
"%PY%" servidor_leve.py
if %errorlevel% neq 0 (echo.
    echo O Jarvis fechou com erro. Veja a mensagem acima.
    pause
)
exit
