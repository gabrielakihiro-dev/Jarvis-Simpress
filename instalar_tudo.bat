@echo off
chcp 65001 > nul
title J.A.R.V.I.S Simpress - Instalacao
cd /d "%~dp0"
echo ========================================================
echo        INSTALACAO DO J.A.R.V.I.S SIMPRESS
echo ========================================================
echo.

echo [1/5] Verificando Python 3.13...
py -3.13 --version > nul 2>&1
if errorlevel 1 (
    echo Instalando Python 3.13 via winget...
    winget install -e --id Python.Python.3.13 --accept-package-agreements --accept-source-agreements --silent
    py -3.13 --version > nul 2>&1
    if errorlevel 1 (
        echo.
        echo [ERRO] Python 3.13 instalado, mas ainda nao detectado.
        echo Feche esta janela e execute instalar_tudo.bat de novo.
        pause
        exit /b 1
    )
)

echo [2/5] Criando ambiente virtual .venv313...
if not exist ".venv313\Scripts\python.exe" py -3.13 -m venv .venv313
if errorlevel 1 goto erro

echo [3/5] Instalando dependencias...
".venv313\Scripts\python.exe" -m pip install -q -r requirements.txt
if errorlevel 1 goto erro

echo [4/5] Baixando modelo "Hey Jarvis" (openwakeword)...
".venv313\Scripts\python.exe" -c "import openwakeword.utils as u; u.download_models(['hey_jarvis'])"
if errorlevel 1 goto erro

echo [5/5] Baixando modelo de voz Vosk (pt, ~31 MB)...
if exist "modelos_voz\vosk-model-small-pt-0.3\" (
    echo Ja existe, pulando.
) else (
    if not exist "modelos_voz" mkdir "modelos_voz"
    rem --ssl-no-revoke: redes corporativas costumam bloquear a checagem de revogacao
    curl -fL --ssl-no-revoke -o "modelos_voz\vosk.zip" https://alphacephei.com/vosk/models/vosk-model-small-pt-0.3.zip
    if errorlevel 1 goto erro
    tar -xf "modelos_voz\vosk.zip" -C "modelos_voz"
    if errorlevel 1 goto erro
    del "modelos_voz\vosk.zip"
)

if not exist ".env" copy ".env.example" ".env" > nul

echo.
echo ========================================================
echo  Instalacao concluida.
echo  Falta so colocar OPENROUTER_API_KEY no arquivo .env
echo  Depois abra iniciar_jarvis.bat
echo ========================================================
pause
exit /b 0

:erro
echo.
echo [ERRO] Falha na instalacao. Veja a mensagem acima.
pause
exit /b 1
