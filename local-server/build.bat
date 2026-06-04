@echo off
chcp 437 >nul 2>&1

echo ========================================
echo Google Image Search - Build Tool
echo ========================================
echo.

cd /d "%~dp0"

echo [1/5] Find Python...
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
echo [2/5] Check venv...
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
echo [3/5] Install dependencies...
if "%NEED_INSTALL%"=="1" (
    echo Installing packages...
    %VENV_PIP% install flask flask-cors pyautogui pyperclip pygetwindow pywin32 pystray Pillow
    if errorlevel 1 (
        echo ERROR: Install failed
        pause
        exit /b 1
    )
    echo Installing PyInstaller...
    %VENV_PIP% install pyinstaller
    if errorlevel 1 (
        echo ERROR: Install PyInstaller failed
        pause
        exit /b 1
    )
    echo Dependencies installed
) else (
    echo Checking pyinstaller...
    %VENV_PYINSTALLER% --version >nul 2>&1
    if errorlevel 1 (
        echo Installing PyInstaller...
        %VENV_PIP% install pyinstaller
    )
    echo Dependencies already installed
)

echo.
echo [4/5] Test imports...
%VENV_PYTHON% -c "import pystray; import PIL; import flask; import pyautogui; print('OK')"
if errorlevel 1 (
    echo ERROR: Import test failed
    echo Try deleting venv folder and run again
    pause
    exit /b 1
)

echo.
echo [5/5] Build exe...
echo This may take a few minutes...
echo.
%VENV_PYINSTALLER% --clean --noconfirm build.spec
if errorlevel 1 (
    echo.
    echo ERROR: Build failed
    pause
    exit /b 1
)

echo.
echo ========================================
echo Build successful!
echo.
echo Output: dist\GoogleImageSearch.exe
echo ========================================
echo.
pause