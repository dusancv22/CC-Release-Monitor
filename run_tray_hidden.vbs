' VBScript to run the tray bot completely hidden
Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Get the directory where this VBS script is located
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

' Change to the script directory
WshShell.CurrentDirectory = scriptDir

' Resolve Python interpreter path
pythonPath = ""
venvPythonw = scriptDir & "\venv\Scripts\pythonw.exe"
venvPython = scriptDir & "\venv\Scripts\python.exe"
If fso.FileExists(venvPythonw) Then
    pythonPath = venvPythonw
ElseIf fso.FileExists(venvPython) Then
    pythonPath = venvPython
Else
    pythonPath = "pythonw.exe"
End If

scriptPath = scriptDir & "\tray_bot.py"
logDir = scriptDir & "\logs"
logPath = logDir & "\tray_startup.log"

If Not fso.FolderExists(logDir) Then
    On Error Resume Next
    fso.CreateFolder(logDir)
    If Err.Number <> 0 Then
        WScript.Echo "Unable to create log directory: " & logDir & " (" & Err.Description & ")"
        WScript.Quit 1
    End If
    On Error GoTo 0
End If

If Not fso.FileExists(scriptPath) Then
    WScript.Echo "Bot script not found: " & scriptPath
    WScript.Quit 1
End If

command = """" & pythonPath & """ """ & scriptPath & """ 2>>""" & logPath & """"

On Error Resume Next
WshShell.Run command, 0, False
If Err.Number <> 0 Then
    WScript.Echo "Failed to launch tray bot using " & pythonPath & ": " & Err.Description
    WScript.Quit Err.Number
End If
On Error GoTo 0
