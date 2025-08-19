' VBScript to run the bot hidden (no console window)
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "C:\Users\Dusan\miniconda3\python.exe simple_bot.py", 0, False