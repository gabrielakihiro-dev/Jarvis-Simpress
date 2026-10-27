@echo off
chcp 65001 > nul
title J.A.R.V.I.S Simpress - Interface Grafica
echo ========================================================
echo         INICIANDO O J.A.R.V.I.S SIMPRESS (GUI)          
echo ========================================================
echo.
cd /d "%~dp0"
if not exist ".venv" (
    echo [1/3] Criando ambiente virtual Python...
    python -m venv .venv
)
echo [2/3] Ativando ambiente virtual...
call ".venv\Scripts\activate.bat"
python -m pip install -q -r requirements.txt
echo [3/3] Abrindo Interface Futurista PyQt6...
echo.
set SIMPRESS_URL=http://127.0.0.1:8000
python jarvis_ui.py
echo.
pause
