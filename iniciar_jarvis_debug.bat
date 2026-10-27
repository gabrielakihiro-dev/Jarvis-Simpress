@echo off
chcp 65001 > nul
title J.A.R.V.I.S Simpress - Interface Grafica
echo ========================================================
echo         INICIANDO O J.A.R.V.I.S SIMPRESS (GUI + DIAGNOSTICO DAS PALMAS)        
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
echo [2/3] Ativando ambiente virtual...
call "%VENV%\Scripts\activate.bat"
python -m pip install -q -r requirements.txt
echo [3/3] Abrindo Interface Futurista PyQt6...
echo.
set SIMPRESS_URL=http://127.0.0.1:8000
set JARVIS_PALMAS_DEBUG=1
python jarvis_ui.py
echo.
pause
