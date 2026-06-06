# 王青青的小助手

<div align="center">

![Chrome Extension](https://img.shields.io/badge/Chrome-Extension-blue?style=flat-square&logo=google-chrome)
![Python](https://img.shields.io/badge/Python-3.9+-yellow?style=flat-square&logo=python)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![Platform](https://img.shields.io/badge/Platform-macOS%20%7C%20Windows-lightgrey?style=flat-square)

**素材采集 + 专利标号 + 以图搜图 + 图片分割**

[功能特性](#功能特性) • [快速开始](#快速开始) • [项目结构](#项目结构) • [构建打包](#构建打包) • [使用说明](#使用说明) • [更新日志](#更新日志)

</div>

---

## 功能特性

### 📸 素材采集
- 批量采集 Shutterstock、123rf 等素材网站的作者信息
- 智能混合输入，支持多源 ID/链接混合粘贴
- 自动去重，格式化结果复制

### 📄 专利标号
- Google Patents 标号自动高亮
- Claims 中的标号点击跳转
- 最近访问记录

### 🔍 以图搜图
- 页面图片智能扫描（支持懒加载、Shadow DOM）
- 批量下载图片
- Google/Amazon 以图搜图
- WebSocket 实时状态同步
- 本地图片直接打开文件所在目录（Finder/资源管理器）

### ✂️ 图片分割
- 网格排列图片自动分割
- 拖拽上传支持
- 自动裁剪黑色边缘和红色线条
- 分割结果直接加入图片列表

---

## 快速开始

### 1. 安装 Chrome 扩展

1. 打开 Chrome/Edge 浏览器
2. 访问 `chrome://extensions/` 或 `edge://extensions/`
3. 开启「开发者模式」
4. 点击「加载已解压的扩展程序」
5. 选择 `extensions/qingqingHelper` 文件夹

### 2. 启动本地服务

**macOS：**
```bash
# 双击运行
open start.command

# 或终端运行
./start.sh
```

**Windows：**
```cmd
# 双击运行
start.bat

# 或命令行运行
scripts\windows\start.bat
```

**手动运行：**
```bash
cd local-server
pip install -r requirements.txt
python server.py
```

### 3. 使用

1. 打开包含图片的网页
2. 点击扩展图标
3. 选择功能 tab（素材采集/专利标号/以图搜图）
4. 根据提示操作

---

## 项目结构

```
google-image-search-tool/
├── start.sh                         # 统一启动脚本（自动检测系统）
├── start.bat                        # Windows 启动脚本
├── start.command                    # macOS 启动脚本（双击运行）
│
├── scripts/                         # 脚本目录
│   ├── clean.sh                     # 公共清理脚本
│   ├── installer.py                 # 安装器（公共）
│   ├── uninstaller.py               # 卸载器（公共）
│   ├── tray_service.py              # 系统托盘服务（公共）
│   ├── upload_handler.py            # 上传处理器（公共）
│   │
│   ├── macos/                       # macOS 专用
│   │   ├── start.sh                 # 启动脚本
│   │   └── build/                   # 构建配置
│   │       ├── build.sh             # 打包脚本
│   │       ├── build.spec           # PyInstaller 主程序配置
│   │       ├── build_console.spec   # PyInstaller 控制台版本配置
│   │       ├── installer.spec       # 安装器打包配置
│   │       └── uninstaller.spec     # 卸载器打包配置
│   │
│   └── windows/                     # Windows 专用
│       ├── start.bat                # 启动脚本
│       └── build/                   # 构建配置
│           ├── build.bat            # 打包脚本
│           ├── build.spec           # PyInstaller 主程序配置
│           ├── build_console.spec   # PyInstaller 控制台版本配置
│           ├── installer.spec       # 安装器打包配置
│           └── uninstaller.spec     # 卸载器打包配置
│
├── extensions/                      # Chrome 扩展目录
│   └── qingqingHelper/              # 扩展主目录
│       ├── manifest.json            # 扩展配置
│       ├── popup.html               # 弹出界面
│       ├── popup.js                 # 素材采集逻辑
│       ├── patent.js                # 专利标号逻辑
│       ├── patent-content.js        # 专利页面内容脚本
│       ├── inject.js                # 专利标号注入脚本
│       ├── imagesearch.js           # 以图搜图逻辑
│       ├── background.js            # 后台服务
│       └── icons/                   # 扩展图标
│
├── local-server/                    # 本地服务器目录
│   ├── server.py                    # Flask 服务器主程序
│   ├── requirements.txt             # Python 依赖
│   └── images/                      # 图片存储目录
│       └── split/                   # 分割后的图片
│
├── dist/                            # 打包输出目录
│
├── LICENSE                          # MIT 开源协议
├── README.md                        # 本文件
└── README_EN.md                     # 英文说明
```

---

## 构建打包

### macOS 打包

```bash
# 运行打包脚本
./scripts/macos/build/build.sh
```

### Windows 打包

```cmd
# 运行打包脚本
scripts\windows\build\build.bat
```

### 输出文件

打包完成后，`dist/` 目录下会生成：

- `王青青的小助手.app` - 主程序
- `王青青的小助手_调试版.app` - 控制台版本（调试用）
- `安装器.app` - 安装程序
- `卸载器.app` - 卸载程序

### 清理构建文件

```bash
./scripts/clean.sh
```

---

## 使用说明

### 素材采集

1. 切换到「📸 素材采集」tab
2. 在输入框粘贴素材 ID 或链接
3. 点击「开始批量同步采集」
4. 采集完成后点击「复制合并结果文本」

### 专利标号

1. 切换到「📄 专利标号」tab
2. 输入专利号（如 US8066257B2）
3. 点击「打开专利」
4. 页面会自动高亮 Claims 中的标号

### 以图搜图

1. 切换到「🔍 以图搜图」tab
2. 点击「扫描页面图片」或「选择本地图片」
3. 选择图片后点击「Google搜图」或「Amazon搜图」
4. 本地图片点击下载按钮会打开文件所在目录

### 图片分割

1. 在「🔍 以图搜图」tab 中展开「✂️ 图片分割」
2. 拖拽图片或点击选择文件
3. 点击「开始分割」
4. 分割结果自动加入图片列表

---

## 环境要求

- **浏览器**：Chrome/Edge（支持 Manifest V3）
- **Python**：3.9+
- **依赖**：Flask, OpenCV, NumPy, PyAutoGUI, pyperclip
- **macOS**：需要辅助功能权限（鼠标控制）
- **Windows**：需要 pywin32

---

## 更新日志

### v2.0.0 (2026-06-06)

- ✨ 合并素材采集、专利标号、以图搜图为统一扩展
- ✨ 新增图片分割功能（网格自动分割）
- ✨ 本地图片打开文件所在目录（Finder/资源管理器）
- ✨ 统一脚本管理（scripts/macos, scripts/windows）
- ✨ 完善构建打包流程
- 🎨 UI 优化，减小间距
- 🔧 macOS 兼容性适配（Quartz 窗口管理）
- 🔧 WebSocket 实时状态同步

### v1.0.0 (2026-06-04)

- ✨ 初始版本发布
- 🔍 页面图片扫描（支持 Shadow DOM）
- 📥 批量下载图片
- 🔍 Google/Amazon 搜图功能
- 🛠️ 调试模式

---

## 开源协议

本项目基于 [MIT License](LICENSE) 开源。
