@echo off
rem Abre o servidor do Simpress, espera ele responder e abre o Jarvis.
rem   iniciar_tudo.bat           abre tudo agora
rem   iniciar_tudo.bat instalar  abre tudo ao entrar no Windows (atalho na pasta Inicializar)
rem   iniciar_tudo.bat remover   desfaz o "instalar"
set "ATALHO=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Iniciar Simpress e Jarvis.lnk"
set "SIMPRESS=%~dp0..\Simpress\iniciar_servidor.bat"

if /i "%~1"=="instalar" goto instalar
if /i "%~1"=="remover" goto remover

if not exist "%SIMPRESS%" (
    echo ERRO: Simpress nao encontrado em "%SIMPRESS%".
    pause
    exit /b 1
)
start "Simpress" /min "%SIMPRESS%"
rem Espera o Simpress responder (ate ~2 min) antes de abrir o Jarvis
for /l %%i in (1,1,60) do (
    curl -s -o nul http://127.0.0.1:8000/ && goto pronto
    timeout /t 2 /nobreak >nul
)
:pronto
start "Jarvis" "%~dp0iniciar_jarvis.bat"
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
