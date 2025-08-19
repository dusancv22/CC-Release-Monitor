' VBScript to run the tray bot completely hidden
Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Get the directory where this VBS script is located
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

' Change to the script directory
WshShell.CurrentDirectory = scriptDir

' Run the tray bot with full paths and error logging
pythonPath = "C:\Users\Dusan\miniconda3\python.exe"
scriptPath = scriptDir & "\tray_bot.py"
logPath = scriptDir & "\logs\tray_startup.log"

' Create command with error redirection
command = """" & pythonPath & """ """ & scriptPath & """ 2>>""" & logPath & """"

WshShell.Run command, 0, False