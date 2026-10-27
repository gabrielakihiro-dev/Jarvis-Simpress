@echo off
chcp 65001 > nul
title J.A.R.V.I.S Simpress - Modo Terminal
echo ========================================================
echo       INICIANDO O J.A.R.V.I.S SIMPRESS (TERMINAL)       
echo ========================================================
echo.
cd /d "%~dp0"
if exist ".venv313\Scripts\activate.bat" (
    call ".venv313\Scripts\activate.bat"
) else (
    call ".venv\Scripts\activate.bat"
)
python jarvis.py
if errorlevel 1 (echo.
    echo O Jarvis fechou com erro. Veja a mensagem acima.
    pause
)
exit
