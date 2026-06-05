# Google Image Search Tool - 项目记忆文件

## 项目概述

Chrome扩展 + 本地服务器的图片搜图工具，支持批量下载网页图片并上传到Google搜图。

**核心架构：**
- Chrome扩展：扫描图片、管理下载、发送请求
- 本地服务器：Flask + pyautogui，处理文件对话框操作

---

## 关键技术要点

### 1. Chrome扩展 (Manifest V3)

**CSP限制：**
- ❌ 不允许内联事件处理器 (`onclick="..."`)
- ✅ 必须在JS中使用 `addEventListener` 绑定事件

**scripting API：**
```javascript
// 注入页面执行函数
await chrome.scripting.executeScript({
  target: { tabId: tab.id },
  func: functionName,
  world: 'MAIN'  // 在页面主世界执行
});
```

**持久化存储：**
```javascript
// 保存
await chrome.storage.local.set({ key: value });
// 读取
const result = await chrome.storage.local.get(['key']);
```

### 2. Shadow DOM图片扫描

MSN等网站使用Web Component，图片在Shadow DOM中：
```javascript
function scanShadowRoots(root) {
  root.querySelectorAll('*').forEach(el => {
    if (el.shadowRoot) {
      // 扫描shadowRoot中的img
      el.shadowRoot.querySelectorAll('img').forEach(img => {
        // 处理图片
      });
      // 递归扫描嵌套的shadow DOM
      scanShadowRoots(el.shadowRoot);
    }
  });
}
```

### 3. 文件选择对话框

**重要：** 文件选择对话框不能通过JS触发！
```
Error: File chooser dialog can only be shown with a user activation.
```

**解决方案：** 使用pyautogui点击坐标
1. 获取元素的视口坐标 (`getBoundingClientRect()`)
2. 发送给本地服务器
3. pyautogui计算屏幕坐标并点击

### 4. 坐标计算

**视口坐标 → 屏幕坐标：**
```javascript
// 扩展端：获取视口坐标
const rect = element.getBoundingClientRect();
const viewportX = rect.left + rect.width / 2;
const viewportY = rect.top + rect.height / 2;

// 计算导航栏高度
const navBarHeight = window.outerHeight - window.innerHeight;
```

```python
# 服务器端：计算屏幕坐标
screen_x = browser_window.left + viewport_x
screen_y = browser_window.top + viewport_y + nav_bar_height
```

**使用 pygetwindow 获取浏览器窗口位置：**
```python
import pygetwindow as gw
window = gw.getWindowsWithTitle('Chrome')[0]
browser_x = window.left
browser_y = window.top
```

---

## 重要选择器

### Google搜图页面

| 元素 | 选择器 |
|------|--------|
| 按图搜索按钮 | `div[aria-label="按图搜索"]` |
| 上传文件标签 | `span[jsname][jsaction][role="button"]` 且文本="上传文件" |
| 搜索按钮 | `div[aria-label="搜尋"][role="button"]` |
| 文件输入框 | `input[type="file"]` |

**注意：** 上传文件按钮必须用精确选择器 `span[jsname][jsaction][role="button"]`，不要用通用选择器！

---

## 文件扩展名映射

MSN等网站的图片URL可能是 `.img` 格式，但实际下载后是 `.jpg`/`.png`。

**查找逻辑：**
1. 先查找原始文件名
2. 再查找同名不同扩展名（.jpg, .jpeg, .png, .gif, .webp, .bmp）
3. 最后模糊匹配

---

## 搜索记录持久化

**存储结构：**
```javascript
{
  "searchedImages": {
    "filename.jpg": {
      "tabId": 123,
      "url": "https://www.google.com/search?...",
      "timestamp": 1234567890
    }
  }
}
```

**跳过逻辑：**
1. tab必须存在
2. URL必须包含搜图特征（`/search`, `lens.google`, `tbm=isch`）
3. 记录的URL是搜图结果 → 当前URL也必须是搜图结果

---

## 打包注意事项

### Windows批处理文件

**编码问题：**
- ❌ 中文内容会导致乱码
- ✅ 使用纯英文内容
- ✅ 开头添加 `chcp 437 >nul 2>&1`

**依赖安装：**
- 只在venv不存在时安装依赖
- 使用完整路径调用Python：`%~dp0venv\Scripts\python.exe`

**Python路径检测：**
- 跳过WSL路径（`/usr/bin`）
- 优先使用 `AppData\Local\Python` 或 `AppData\Local\Programs\Python`

---

## 常见问题

### 1. 扩展重新加载后不生效
**解决：** 必须删除扩展后重新加载，而不是点击刷新按钮

### 2. Service Worker控制台查看日志
**路径：** `edge://extensions/` → 点击"Service Worker"链接

### 3. 图片扫描不到
**可能原因：**
- 图片在Shadow DOM中
- 图片是懒加载的
- 图片使用了非标准属性

### 4. 文件上传对话框未出现
**检查：**
- 坐标是否正确
- 导航栏高度是否准确
- 浏览器窗口是否被遮挡

---

## 目录结构

```
google-image-search-tool/
├── README.md
├── extensions/
│   └── qingqingHelper/
│       ├── manifest.json          # 扩展配置
│       ├── background.js          # 后台服务（心跳、搜图流程）
│       ├── popup.html             # 弹出界面
│       ├── popup.js               # 界面逻辑
│       └── icons/                 # 扩展图标
└── local-server/
    ├── server.py              # Flask服务器（开发用）
    ├── tray_service.py        # 系统托盘程序（打包用）
    ├── upload_handler.py      # pyautogui文件操作
    ├── build.bat              # 打包脚本
    ├── build.spec             # PyInstaller配置
    ├── debug.bat              # 调试模式
    └── requirements.txt       # Python依赖
```

---

## 待办事项

- [ ] Amazon搜图功能（开发中）
- [ ] 批量搜图进度条优化
- [ ] 搜图结果自动收集

---

*最后更新: 2026-06-04*