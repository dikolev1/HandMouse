@echo off
rem Starts Hand Mouse in the background (no window). Ctrl+Alt+Q quits, Ctrl+Alt+H pauses.
cd /d "%~dp0"
set "PYW=pyw"
if exist python_path.txt (
  set /p PYEXE=<python_path.txt
  call set "PYW=%%PYEXE:python.exe=pythonw.exe%%"
)
start "" "%PYW%" hand_mouse.py
