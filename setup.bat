@echo off
rem One-time setup for Hand Mouse: finds (or installs) Python, installs the libraries,
rem downloads the hand model, then opens the preview. Details go to setup_log.txt.
cd /d "%~dp0"
echo Setting up Hand Mouse. This can take a few minutes...
call :main > setup_log.txt 2>&1
if errorlevel 1 (
  echo.
  echo Setup failed. See setup_log.txt in this folder.
  pause
  exit /b 1
)
echo Setup finished. Opening the preview...
start "" "%~dp0run_preview.bat"
exit /b 0

:main
set "PY="
where py >nul 2>nul && set "PY=py"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Launcher\py.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Launcher\py.exe"
if not defined PY (
  echo Python not found, installing Python 3.12 with winget...
  winget install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
)
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Launcher\py.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Launcher\py.exe"
if not defined PY (
  echo ERROR: Python could not be found or installed.
  exit /b 1
)
"%PY%" -c "import sys; print(sys.executable)" > python_path.txt || exit /b 1
set /p PYEXE=<python_path.txt
echo Using %PYEXE%
"%PYEXE%" -m pip install --upgrade pip
"%PYEXE%" -m pip install -r requirements.txt || exit /b 1
"%PYEXE%" -c "import hand_mouse; hand_mouse.ensure_model(); print('model ok')" || exit /b 1
exit /b 0
