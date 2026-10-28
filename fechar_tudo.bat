@echo off
rem Fecha o servidor do Simpress e o Jarvis, mesmo rodando ocultos (sem janela de cmd).
rem O Jarvis (janela PyQt6) recebe um fechamento normal primeiro; so' se nao fechar em 5s e' forcado.
powershell -NoProfile -Command ^
  "$n=0; Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -match 'jarvis_ui\.py' -or $_.CommandLine -match 'jarvis\.py' } | ForEach-Object { $proc = Get-Process -Id $_.ProcessId -ErrorAction SilentlyContinue; if ($proc) { if ($proc.CloseMainWindow()) { $proc.WaitForExit(5000) | Out-Null }; if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue }; $n++ } }; Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -match 'main\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; $n++ }; Write-Host \"Processos encerrados: $n\""
pause
exit /b 0
