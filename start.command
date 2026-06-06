#!/bin/bash

# 王青青的小助手 - macOS启动脚本（双击运行）

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "========================================"
echo "王青青的小助手"
echo "========================================"
echo ""

# 调用macOS启动脚本
exec "$SCRIPT_DIR/scripts/macos/start.sh"
