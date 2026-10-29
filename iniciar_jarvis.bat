@echo off
chcp 65001 > nul
title J.A.R.V.I.S Simpress - Interface Grafica
echo ========================================================
echo         INICIANDO O J.A.R.V.I.S SIMPRESS (GUI)          
echo ========================================================
echo.
cd /d "%~dp0"
set "VENV="
if exist ".venv313\Scripts\activate.bat" set "VENV=.venv313"
if not defined VENV if exist ".venv\Scripts\activate.bat" set "VENV=.venv"
if not defined VENV (
    echo [1/3] Criando ambiente virtual Python...
    py -3.13 --version > nul 2>&1
    if errorlevel 1 (python -m venv .venv) else (py -3.13 -m venv .venv313)
)
if not defined VENV if exist ".venv313\Scripts\activate.bat" set "VENV=.venv313"
if not defined VENV set "VENV=.venv"
echo [2/3] Preparando ambiente virtual...
rem Chama o python do venv direto: o activate.bat guarda o caminho de onde o venv foi criado e, se a pasta for movida,
rem o "python" cai no Python global (sem o modelo do Hey Jarvis).
set "PY=%~dp0%VENV%\Scripts\python.exe"
"%PY%" -m pip install -q -r requirements.txt
echo [3/3] Abrindo Interface Futurista PyQt6...
echo.
if not defined SIMPRESS_URL set "SIMPRESS_URL=http://127.0.0.1:8000"
rem Aberto oculto pelo iniciar_tudo.bat (JARVIS_OCULTO=1): ninguem ve a janela, entao a saida vai para jarvis.log
rem e um erro aparece numa caixa de aviso (um pause oculto travaria o cmd para sempre).
if defined JARVIS_OCULTO ("%PY%" jarvis_ui.py > "%~dp0jarvis.log" 2>&1) else "%PY%" jarvis_ui.py
if %errorlevel% neq 0 (
    if defined JARVIS_OCULTO (
        powershell -NoProfile -Command "Add-Type -AssemblyName PresentationFramework; [void][System.Windows.MessageBox]::Show('O Jarvis fechou com erro. Veja o arquivo jarvis.log na pasta do Jarvis.', 'J.A.R.V.I.S.')"
        exit
    )
    echo.
    echo O Jarvis fechou com erro. Veja a mensagem acima.
    pause
)
exit
