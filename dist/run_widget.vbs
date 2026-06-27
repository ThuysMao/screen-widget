Set objFSO = CreateObject("Scripting.FileSystemObject")
Set WshShell = CreateObject("WScript.Shell")
strPath = objFSO.GetParentFolderName(WScript.ScriptFullName)
WshShell.Run "pythonw.exe """ & strPath & "\widget.py""", 0, False
