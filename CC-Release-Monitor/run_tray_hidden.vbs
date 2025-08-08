' VBScript to run the tray bot completely hidden
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "C:\Users\Dusan\miniconda3\python.exe tray_bot.py", 0, False