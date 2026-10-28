' Executa o comando recebido como argumento sem abrir nenhuma janela de cmd.
' Uso: wscript executar_oculto.vbs "caminho\do\script.bat"
Set objShell = CreateObject("WScript.Shell")
objShell.Run """" & WScript.Arguments(0) & """", 0, False
