@echo off
rem Starts Hand Mouse with a camera window so you can test and tune it.
cd /d "%~dp0"
set "PYEXE=py"
if exist python_path.txt set /p PYEXE=<python_path.txt
"%PYEXE%" hand_mouse.py --preview
if errorlevel 1 pause
