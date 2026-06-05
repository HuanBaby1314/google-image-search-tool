# Google Image Search Tool

<div align="center">

![Chrome Extension](https://img.shields.io/badge/Chrome-Extension-blue?style=flat-square&logo=google-chrome)
![Python](https://img.shields.io/badge/Python-3.8+-yellow?style=flat-square&logo=python)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey?style=flat-square)

**批量下载网页图片并上传到Google搜图的工具**

[功能特性](#功能特性) • [快速开始](#快速开始) • [使用说明](#使用说明) • [开发指南](#开发指南) • [更新日志](#更新日志)

</div>

---

## 功能特性

- 🔍 **智能扫描** - 扫描页面图片，支持懒加载、Shadow DOM
- 📥 **批量下载** - 一键下载选中图片，自动创建日期目录
- 🔍 **Google搜图** - 自动上传图片到Google搜图
- 🔄 **跳过重复** - 已搜图的图片自动跳过
- 🖥️ **系统托盘** - 本地服务以托盘形式运行
- 🛠️ **调试模式** - 支持单步调试，方便排查问题

## 快速开始

### 1. 安装Chrome扩展

1. 下载 [最新版本](https://github.com/YOUR_USERNAME/google-image-search-tool/releases)
2. 解压后打开 Chrome/Edge 浏览器
3. 访问 `chrome://extensions/` 或 `edge://extensions/`
4. 开启"开发者模式"
5. 点击"加载已解压的扩展程序"
6. 选择 `extensions/qingqingHelper` 文件夹

### 2. 启动本地服务

**方式一：直接运行exe（推荐）**
```
双击 dist/GoogleImageSearch.exe
```

**方式二：Python运行**
```bash
cd local-server
pip install -r requirements.txt
python server.py
```

### 3. 使用

1. 打开包含图片的网页
2. 点击扩展图标
3. 点击"扫描页面图片"
4. 选择需要的图片
5. 点击"Google搜图"

## 使用说明

### 扫描图片

- 点击"扫描页面图片"按钮
- 支持扫描：普通图片、懒加载图片、Shadow DOM中的图片
- 自动过滤SVG和小图标

### 下载图片

- 选择需要下载的图片
- 点击"下载选中图片"
- 图片保存到 `Downloads/qingqing_helper_dir/日期/` 目录
- 已下载的图片会标记为"已下载"

### Google搜图

- 选择图片后点击"Google搜图"
- 自动执行：打开搜图页面 → 点击上传 → 选择文件 → 搜索
- 已搜图的图片会自动跳过

### 本地图片

- 点击"本地图片"按钮选择本地文件
- 本地图片直接使用原始路径，不会重复下载

### 调试模式

- 点击右上角 🐛 图标进入调试模式
- 可以单步执行每个操作
- 查看详细的执行日志

## 开发指南

### 项目结构

```
google-image-search-tool/
├── extensions/
│   └── qingqingHelper/        # Chrome扩展
│       ├── manifest.json          # 扩展配置
│       ├── background.js          # 后台服务（心跳、搜图流程）
│       ├── popup.html             # 弹出界面
│       ├── popup.js               # 界面逻辑
│       └── icons/                 # 扩展图标
├── local-server/              # 本地服务器
│   ├── server.py              # Flask服务器（开发用）
│   ├── tray_service.py        # 系统托盘程序（打包用）
│   ├── upload_handler.py      # pyautogui文件操作
│   ├── build.bat              # 打包脚本
│   ├── build.spec             # PyInstaller配置
│   ├── build_console.spec     # Debug版本配置
│   ├── debug.bat              # 调试模式启动
│   └── requirements.txt       # Python依赖
├── PROJECT_MEMORY.md          # 项目记忆文件
├── LICENSE                    # MIT开源协议
└── README.md                  # 本文件
```

### 开发环境

**Chrome扩展：**
- Chrome/Edge 浏览器
- 开启开发者模式

**本地服务器：**
- Python 3.8+
- 依赖：Flask, pyautogui, pyperclip, pygetwindow, pywin32

### 打包发布

```bash
cd local-server
build.bat
```

输出文件：`dist/GoogleImageSearch.exe`

### 关键技术

1. **Chrome Extension Manifest V3** - 使用最新规范
2. **chrome.scripting API** - 注入页面执行脚本
3. **Shadow DOM扫描** - 支持Web Component中的图片
4. **pyautogui** - 操作系统文件对话框
5. **坐标计算** - 视口坐标到屏幕坐标的转换

详细技术说明请参考 [PROJECT_MEMORY.md](PROJECT_MEMORY.md)

## 更新日志

### v1.0.0 (2026-06-04)

- ✨ 初始版本发布
- 🔍 页面图片扫描（支持Shadow DOM）
- 📥 批量下载图片
- 🔍 Google搜图功能
- 🖥️ 系统托盘服务
- 🛠️ 调试模式
- 📝 搜索记录持久化

## 常见问题

**Q: 扫描不到图片？**
A: 尝试滚动页面后再扫描，部分图片需要触发懒加载。

**Q: 文件上传对话框没有出现？**
A: 确保本地服务器已启动，检查服务器状态指示灯。

**Q: 点击位置不准确？**
A: 确保浏览器窗口没有被遮挡，且不是全屏模式。

## 赞赏支持

如果这个项目对你有帮助，欢迎请我喝杯咖啡 ☕

<div align="center">
<table>
<tr>
<td align="center"><img src="https://private-user-images.githubusercontent.com/28698252/590677712-95175d2a-7887-478b-aa5b-1ff3e9b33b7d.png?jwt=***" width="45%"/><br><b>支付宝</b></td>
<td align="center"><img src="https://private-user-images.githubusercontent.com/28698252/590673265-10e6c704-7b78-4c2a-acd1-59f76ed99daa.jpg?jwt=***" width="45%"/><br><b>微信</b></td>
</tr>
</table>
</div>

## 开源协议

本项目基于 [MIT License](LICENSE) 开源。

---

<div align="center">

**[English](README_EN.md)** | **中文**

Made with ❤️ by [Your Name]

</div>