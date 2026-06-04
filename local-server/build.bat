@echo off
chcp 437 >nul 2>&1

echo ========================================
echo   Build Tool
echo ========================================
echo.

cd /d "%~dp0"
echo Working dir: %cd%
echo.

echo [1/6] Find Python...
set PYTHON=

for /f "tokens=*" %%i in ('where python 2^>nul') do (
    echo Found: %%i
    echo %%i | findstr /i "AppData\Local\Python" >nul && set PYTHON=%%i
    echo %%i | findstr /i "AppData\Local\Programs\Python" >nul && set PYTHON=%%i
)

if "%PYTHON%"=="" (
    for /f "tokens=*" %%i in ('where python 2^>nul') do (
        echo %%i | findstr /i "WindowsApps" >nul && if "%PYTHON%"=="" set PYTHON=%%i
    )
)

if "%PYTHON%"=="" (
    where py >nul 2>&1 && set PYTHON=py
)

if "%PYTHON%"=="" (
    echo ERROR: Python not found
    pause
    exit /b 1
)

echo Using: %PYTHON%
%PYTHON% --version

echo.
echo [2/6] Check venv...
if not exist "venv\Scripts\python.exe" (
    echo Creating venv...
    %PYTHON% -m venv venv
    if errorlevel 1 (
        echo ERROR: Failed to create venv
        pause
        exit /b 1
    )
    echo venv created
    set NEED_INSTALL=1
) else (
    echo venv exists
    set NEED_INSTALL=0
)

set VENV_PIP="%~dp0venv\Scripts\pip.exe"
set VENV_PYTHON="%~dp0venv\Scripts\python.exe"
set VENV_PYINSTALLER="%~dp0venv\Scripts\pyinstaller.exe"

echo.
echo [3/6] Install dependencies...
if "%NEED_INSTALL%"=="1" (
    echo Installing packages...
    %VENV_PIP% install flask flask-cors pyautogui pyperclip pygetwindow pywin32 pystray Pillow
    if errorlevel 1 (
        echo ERROR: Install packages failed
        pause
        exit /b 1
    )
    echo Installing pyinstaller...
    %VENV_PIP% install pyinstaller
    if errorlevel 1 (
        echo ERROR: Install pyinstaller failed
        pause
        exit /b 1
    )
    echo Dependencies installed
) else (
    echo Dependencies already installed
)

echo.
echo [4/6] Test imports...
%VENV_PYTHON% -c "import pystray; import PIL; import flask; import pyautogui; print('OK')"
if errorlevel 1 (
    echo ERROR: Import test failed
    pause
    exit /b 1
)
echo Import test passed

echo.
echo [5/6] Build server.exe (temp, will be embedded)...
echo.
%VENV_PYINSTALLER% --clean --noconfirm build.spec
if errorlevel 1 (
    echo.
    echo ERROR: Build server.exe failed
    pause
    exit /b 1
)
echo server.exe built

echo.
echo [6/6] Build qingqingHelper.exe (installer)...
echo.
%VENV_PYINSTALLER% --clean --noconfirm installer.spec
if errorlevel 1 (
    echo.
    echo ERROR: Build qingqingHelper.exe failed
    pause
    exit /b 1
)

echo.
echo Cleaning up...
del /f /q "dist\server.exe" 2>nul

echo.
echo ========================================
echo Build successful!
echo.
echo Output: dist\qingqingHelper.exe
echo.
echo Run qingqingHelper.exe to install.
echo ========================================
echo.
pause