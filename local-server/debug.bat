@echo off
chcp 437 >nul 2>&1

echo ========================================
echo Google Image Search - Debug Mode
echo ========================================
echo.
echo Work dir: %USERPROFILE%\Downloads\qingqing_helper_dir
echo Server: http://localhost:5000
echo.
echo Press Ctrl+C to stop
echo ========================================
echo.

cd /d "%~dp0"

REM Use venv Python if exists, otherwise system Python
if exist "%~dp0venv\Scripts\python.exe" (
    "%~dp0venv\Scripts\python.exe" server.py
) else (
    python server.py
)