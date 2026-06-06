#!/bin/bash

# 公共清理脚本

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "清理构建文件..."

cd "$PROJECT_ROOT"

# 清理构建目录
rm -rf build dist *.egg-info
rm -f *.spec.bak

# 清理Python缓存
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true

# 清理临时文件
rm -f local-server/installer.py local-server/uninstaller.py
rm -f local-server/tray_service.py local-server/upload_handler.py

echo "清理完成！"
