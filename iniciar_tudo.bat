@echo off
rem Abre o servidor do Simpress, espera ele responder e abre o Jarvis.
rem Os cmds do servidor e do Jarvis ficam ocultos (sem janela, sem icone na barra).
rem   iniciar_tudo.bat           abre tudo agora
rem   iniciar_tudo.bat instalar  abre tudo ao entrar no Windows (atalho na pasta Inicializar)
rem   iniciar_tudo.bat remover   desfaz o "instalar"
rem   fechar_tudo.bat            fecha o servidor do Simpress e o Jarvis
set "ATALHO=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Iniciar Simpress e Jarvis.lnk"
set "SIMPRESS=%~dp0..\Simpress\iniciar_servidor.bat"

if /i "%~1"=="instalar" goto instalar
if /i "%~1"=="remover" goto remover

if not exist "%SIMPRESS%" (
    echo ERRO: Simpress nao encontrado em "%SIMPRESS%".
    pause
    exit /b 1
)
rem Simpress ja aberto: nao sobe outro servidor.
call :achar_simpress
if defined SIMPRESS_URL goto pronto
echo Abrindo o servidor do Simpress...
wscript "%~dp0executar_oculto.vbs" "%SIMPRESS%"
rem Espera o Simpress responder (ate ~2 min) antes de abrir o Jarvis.
echo Aguardando o Simpress responder (pode levar ate 2 minutos)...
for /l %%i in (1,1,60) do (
    call :achar_simpress
    if defined SIMPRESS_URL goto pronto
    timeout /t 2 /nobreak >nul
)
:pronto
echo Abrindo o Jarvis...
set "JARVIS_OCULTO=1"
wscript "%~dp0executar_oculto.vbs" "%~dp0iniciar_jarvis.bat"
exit /b 0

:achar_simpress
rem O servidor usa a primeira porta livre de 8000 a 8099. Testa so as portas que estao escutando:
rem varrer as 100 com curl leva ~1 s por porta fechada (~2 min por volta).
set "SIMPRESS_URL="
for /f "tokens=2" %%a in ('netstat -ano -p tcp ^| findstr LISTENING') do (
    for /f "tokens=2 delims=:" %%p in ("%%a") do (
        if %%p geq 8000 if %%p leq 8099 if not defined SIMPRESS_URL (
            curl -sf -m 2 -o nul http://127.0.0.1:%%p/api/stats && set "SIMPRESS_URL=http://127.0.0.1:%%p"
        )
    )
)
exit /b 0

:instalar
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:ATALHO); $s.TargetPath='%~f0'; $s.WorkingDirectory='%~dp0'; $s.WindowStyle=7; $s.Save()"
if exist "%ATALHO%" (echo Pronto: Simpress e Jarvis abrem ao entrar no Windows.) else (echo ERRO: atalho nao foi criado.)
pause
exit /b 0

:remover
if exist "%ATALHO%" del "%ATALHO%"
echo Pronto: Simpress e Jarvis nao abrem mais ao entrar no Windows.
pause
exit /b 0
