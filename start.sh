#!/bin/bash

# 王青青的小助手 - 统一启动脚本
# 自动检测操作系统并调用对应的启动脚本

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 检测操作系统
case "$(uname -s)" in
    Darwin*)
        # macOS
        echo "检测到 macOS 系统"
        exec "$SCRIPT_DIR/scripts/macos/start.sh"
        ;;
    Linux*)
        # Linux
        echo "检测到 Linux 系统"
        exec "$SCRIPT_DIR/scripts/macos/start.sh"
        ;;
    CYGWIN*|MINGW*|MSYS*)
        # Windows (Git Bash / MSYS2)
        echo "检测到 Windows 系统"
        exec "$SCRIPT_DIR/scripts/windows/start.bat"
        ;;
    *)
        echo "不支持的操作系统: $(uname -s)"
        exit 1
        ;;
esac
