#!/bin/bash

# 王青青的小助手 - macOS启动脚本

PORT=5277

echo "========================================"
echo "王青青的小助手 - 本地服务器"
echo "========================================"
echo ""
echo "功能:"
echo "  - 素材采集"
echo "  - 专利标号"
echo "  - 以图搜图 (Google/Amazon)"
echo "  - 图片分割"
echo ""
echo "工作目录: ~/Downloads/qingqing_helper_dir"
echo "服务器地址: http://localhost:$PORT"
echo ""
echo "========================================"
echo ""

# 切换到项目根目录
cd "$(dirname "$0")/../.."

# 检查端口是否被占用
check_port() {
    lsof -i:$PORT -t 2>/dev/null
}

# 停止现有服务
stop_server() {
    local pid=$(check_port)
    if [ -n "$pid" ]; then
        echo "检测到端口 $PORT 已被占用 (PID: $pid)"
        echo "正在停止旧服务..."
        kill -9 $pid 2>/dev/null
        sleep 1
        echo "旧服务已停止"
    fi
}

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到Python3，请先安装Python 3.9+"
    echo "安装方式: brew install python3"
    exit 1
fi

# 显示Python版本
python3 --version

# 检查并安装依赖
echo "检查依赖..."
if ! python3 -c "import flask" &> /dev/null; then
    echo "安装依赖..."
    pip3 install -r local-server/requirements.txt
fi

# 检查辅助功能权限（macOS特有）
echo ""
echo "提示: 如果鼠标无法移动，请检查辅助功能权限:"
echo "  系统偏好设置 -> 隐私与安全性 -> 辅助功能"
echo "  添加 Terminal.app 或你使用的终端应用"
echo ""

# 停止旧服务
stop_server

# 启动服务器
echo "启动服务器..."
python3 local-server/server.py
