@echo off
chcp 437 >nul 2>&1

echo ========================================
echo 王青青的小助手
echo ========================================
echo.

cd /d "%~dp0"

REM 调用Windows启动脚本
call scripts\windows\start.bat
