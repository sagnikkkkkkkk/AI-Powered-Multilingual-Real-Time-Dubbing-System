@echo off
REM One-command launcher: sets up a virtual environment, installs
REM dependencies (first run only), and starts the full app.
REM Usage: double-click run.bat, or run it from cmd/PowerShell.

cd /d "%~dp0backend"

if not exist venv (
  echo Creating virtual environment ^(first run only^)...
  python -m venv venv
)

call venv\Scripts\activate.bat

echo Installing dependencies ^(first run only, this can take a few minutes^)...
pip install -q --upgrade pip
pip install -q -r requirements.txt

where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo.
  echo WARNING: ffmpeg is not installed. Video/audio processing will fail.
  echo   Download it from https://ffmpeg.org/download.html and add it to PATH.
  echo.
)

echo.
echo Starting Nativox -- open http://127.0.0.1:8000 in your browser
echo.
uvicorn main:app --reload --host 127.0.0.1 --port 8000
