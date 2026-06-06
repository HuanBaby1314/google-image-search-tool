@echo off
chcp 437 >nul 2>&1

set PORT=5277

echo ========================================
echo 王青青的小助手 - 本地服务器
echo ========================================
echo.
echo 功能:
echo   - 素材采集
echo   - 专利标号
echo   - 以图搜图 (Google/Amazon)
echo   - 图片分割
echo.
echo 工作目录: %USERPROFILE%\Downloads\qingqing_helper_dir
echo 服务器地址: http://localhost:%PORT%
echo.
echo 按 Ctrl+C 停止服务器
echo ========================================
echo.

REM 切换到项目根目录
cd /d "%~dp0\..\.."

REM 检查Python环境
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到Python，请先安装Python 3.9+
    pause
    exit /b 1
)

REM 检查依赖
echo 检查依赖...
pip show flask >nul 2>&1
if errorlevel 1 (
    echo 安装依赖...
    pip install -r "%~dp0\..\..\local-server\requirements.txt"
)

REM 检查端口是否被占用
echo 检查端口 %PORT%...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :%PORT% ^| findstr LISTENING') do (
    echo 检测到端口 %PORT% 已被占用 (PID: %%a)
    echo 正在停止旧服务...
    taskkill /F /PID %%a >nul 2>&1
    timeout /t 1 /nobreak >nul
    echo 旧服务已停止
)

REM 启动服务器
echo 启动服务器...
python "%~dp0\..\..\local-server\server.py"

pause
