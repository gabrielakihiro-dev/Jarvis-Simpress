@echo off
cd /d "%~dp0.."
set "PY=.venv313\Scripts\python.exe"
if not exist "%PY%" set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" (
    echo Ambiente virtual nao encontrado. Rode instalar_tudo.bat primeiro.
    exit /b 1
)
"%PY%" scripts\verify.py
exit /b %errorlevel%
