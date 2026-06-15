# Google Image Search Tool - 项目记忆

## 项目概述
Chrome扩展 + Flask服务器 + pyautogui 桌面自动化，实现浏览器搜图和图片上传功能。

## 架构
```
google-image-search-tool/
├── extensions/qingqingHelper/   # Chrome 扩展
├── local-server/
│   ├── server.py                # 调试入口（debug.bat）
│   ├── tray_service.py          # 打包入口（系统托盘版）
│   ├── upload_utils.py          # 上传工具函数
│   ├── split_utils.py           # 图片分割函数
│   ├── installer.py             # 安装器
│   ├── uninstaller.py           # 卸载器
│   └── venv/                    # Python 虚拟环境（唯一）
└── scripts/windows/
    ├── build.bat                # 构建脚本
    ├── build.spec               # PyInstaller 配置（server.exe）
    ├── installer.spec           # PyInstaller 配置（qingqingHelper.exe）
    └── uninstaller.spec         # PyInstaller 配置（uninstall.exe）
```

## 关键约定

### 双入口同步
- `server.py`（625行）：调试用，从 upload_utils.py 导入函数
- `tray_service.py`（2238行）：打包用，内联所有代码
- **修改共享逻辑时必须同步两个文件！**

### 共享逻辑清单
- WebSocket: `ws_clients`, `ws_pending_click`, `ws_send_and_wait`, `ws_prepare_click`, `websocket_handler`
- Flask 路由: `/api/select-file-and-upload`, `/api/upload-and-search`, `/api/split-image` 等
- 鼠标操作: `move_to_position`, `click_at_position`, `calculate_screen_position`

### ws_send_and_wait 修复要点
```python
# 错误写法：会立即返回 None（因为 key 已初始化为 None）
if request_id in ws_pending_click:
    result = ws_pending_click.pop(request_id)
    return result

# 正确写法：必须检查值是否不是 None
if request_id in ws_pending_click:
    result = ws_pending_click[request_id]
    if result is not None:
        ws_pending_click.pop(request_id)
        return result
```

## 构建相关
- Python: 3.14.2
- 安装目录: `D:\Program Files (x86)\QingQingHelper`
- 注册表: `HKEY_CURRENT_USER\Software\Classes`（不需要管理员权限）
- 版本号: `scripts/version.py` 定义，同时硬编码在多个文件中
- console=False 时不能用 `input()`，用 `sys.exit(1)` 替代

## 已知问题
- PyInstaller 打包时需要内联依赖模块（tray_service.py 内联了 upload_utils/split_utils）
- 批处理文件必须纯英文避免编码问题
- Chrome 扩展不能用内联 onclick（CSP 限制），用 addEventListener
