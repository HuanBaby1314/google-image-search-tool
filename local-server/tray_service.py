#!/usr/bin/env python3
"""
Google Image Search Tool - 系统托盘服务
首次运行时选择安装目录，后续使用配置的目录
"""

import os
import sys
import json
import time
import logging
import shutil
from pathlib import Path
from datetime import datetime
import threading

# ==================== 配置管理 ====================

APP_NAME = "青青小助手"
APP_DIR_NAME = "QingQingHelper"
CONFIG_FILE = "config.json"

def get_exe_dir():
    """获取数据文件目录（打包后的临时目录或脚本目录）"""
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)
    return Path(__file__).parent

def get_exe_location():
    """获取exe实际所在目录（用于保存/读取配置文件）"""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent

def get_config_path():
    """获取配置文件路径：先查exe同目录，再查上级目录"""
    exe_dir = get_exe_location()
    cfg = exe_dir / CONFIG_FILE
    if cfg.exists():
        return cfg
    # bin/ 目录下的 exe 查找 ../config.json
    cfg = exe_dir.parent / CONFIG_FILE
    if cfg.exists():
        return cfg
    # 默认返回 exe 同目录
    return exe_dir / CONFIG_FILE

def load_config():
    """加载配置"""
    config_path = get_config_path()
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return None

def save_config(config):
    """保存配置"""
    config_path = get_config_path()
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

def select_install_directory():
    """显示完整的安装向导，返回选择的安装目录"""
    try:
        import tkinter as tk
        from tkinter import ttk, filedialog, messagebox
        
        result = {'install_dir': None}
        
        class InstallWizard:
            def __init__(self):
                self.root = tk.Tk()
                self.root.withdraw()
                self.root.title(f"{APP_NAME} 安装向导")
                self.root.geometry("600x500")
                self.root.resizable(False, False)

                self.install_dir = tk.StringVar(value=r"C:\Program Files (x86)")
                self.current_page = 0
                self.pages = []

                self.create_pages()
                self.show_page(0)
                self.root.update_idletasks()
                w, h = 600, 500
                x = (self.root.winfo_screenwidth() // 2) - (w // 2)
                y = (self.root.winfo_screenheight() // 2) - (h // 2)
                self.root.geometry(f"{w}x{h}+{x}+{y}")
                self.root.deiconify()
                self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

            def create_pages(self):
                self.pages = [
                    self._page_welcome(),
                    self._page_license(),
                    self._page_directory(),
                    self._page_installing(),
                    self._page_complete(),
                ]

            def _pack_buttons(self, page, buttons):
                bar = tk.Frame(page)
                bar.pack(side="bottom", fill="x", padx=30, pady=15)
                for text, callback in buttons:
                    tk.Button(bar, text=text, command=callback,
                              width=10, font=("Microsoft YaHei", 10)).pack(side="left", padx=5)

            def _page_welcome(self):
                page = tk.Frame(self.root)
                self._pack_buttons(page, [("取消", self.cancel), ("下一步 >", self.next_page)])
                tk.Label(page, text=f"欢迎安装 {APP_NAME}", font=("Microsoft YaHei", 18, "bold")).pack(pady=(40, 10))
                tk.Label(page, text="批量下载网页图片并上传到Google搜图的工具", font=("Microsoft YaHei", 11)).pack(pady=5)
                tk.Label(page, text="版本 1.0.0", font=("Microsoft YaHei", 10), fg="gray").pack(pady=5)
                box = tk.Frame(page)
                box.pack(pady=20, padx=60, anchor="w")
                for f in ["✓ Chrome/Edge 扩展支持", "✓ 批量图片扫描与下载", "✓ Google 搜图自动上传",
                           "✓ 系统托盘后台服务", "✓ 本地图片管理"]:
                    tk.Label(box, text=f, font=("Microsoft YaHei", 10), anchor="w").pack(fill="x", pady=2)
                return page

            def _page_license(self):
                page = tk.Frame(self.root)
                self._pack_buttons(page, [("取消", self.cancel), ("< 上一步", self.prev_page), ("下一步 >", self.next_page)])
                tk.Label(page, text="许可协议", font=("Microsoft YaHei", 14, "bold")).pack(pady=(20, 5))
                txt_frame = tk.Frame(page)
                txt_frame.pack(padx=30, pady=5, fill="both", expand=True)
                scroll = tk.Scrollbar(txt_frame)
                scroll.pack(side="right", fill="y")
                license_text = "MIT License\n\nCopyright (c) 2026 HuanBaby1314\n\nPermission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the \"Software\"), to deal in the Software without restriction."
                txt = tk.Text(txt_frame, wrap="word", font=("Consolas", 9), yscrollcommand=scroll.set)
                txt.insert("1.0", license_text)
                txt.config(state="disabled")
                txt.pack(side="left", fill="both", expand=True)
                scroll.config(command=txt.yview)
                self.agree_var = tk.BooleanVar(value=True)
                tk.Checkbutton(page, text="我已阅读并同意许可协议", variable=self.agree_var,
                               font=("Microsoft YaHei", 10)).pack(side="bottom", pady=8)
                return page

            def _page_directory(self):
                page = tk.Frame(self.root)
                self._pack_buttons(page, [("取消", self.cancel), ("< 上一步", self.prev_page), ("下一步 >", self.next_page)])
                tk.Label(page, text="选择安装位置", font=("Microsoft YaHei", 14, "bold")).pack(pady=(20, 2))
                tk.Label(page, text=f"选择软件的安装目录，将在此目录下创建 {APP_DIR_NAME} 文件夹",
                         font=("Microsoft YaHei", 10), fg="gray").pack(pady=(0, 8))
                row = tk.Frame(page)
                row.pack(padx=30, fill="x")
                tk.Label(row, text="安装目录:", font=("Microsoft YaHei", 10)).pack(anchor="w")
                inp = tk.Frame(row)
                inp.pack(fill="x", pady=3)
                tk.Entry(inp, textvariable=self.install_dir, font=("Microsoft YaHei", 10)).pack(side="left", fill="x", expand=True)
                tk.Button(inp, text="浏览...", command=self.browse_directory, font=("Microsoft YaHei", 10)).pack(side="right", padx=5)
                box = tk.LabelFrame(page, text="目录结构预览", font=("Microsoft YaHei", 10))
                box.pack(padx=30, pady=5, fill="both", expand=True)
                self.dir_preview = tk.Label(box, font=("Consolas", 10), justify="left", anchor="nw")
                self.dir_preview.pack(padx=10, pady=8, fill="both", expand=True)
                self.install_dir.trace_add("write", self.update_dir_preview)
                self.update_dir_preview()
                return page

            def _page_installing(self):
                page = tk.Frame(self.root)
                tk.Label(page, text="正在安装", font=("Microsoft YaHei", 14, "bold")).pack(pady=20)
                self.progress = ttk.Progressbar(page, length=400, mode="determinate")
                self.progress.pack(pady=10)
                self.install_status = tk.Label(page, text="准备安装...", font=("Microsoft YaHei", 10))
                self.install_status.pack(pady=5)
                log_frame = tk.Frame(page)
                log_frame.pack(padx=30, pady=10, fill="both", expand=True)
                scroll = tk.Scrollbar(log_frame)
                scroll.pack(side="right", fill="y")
                self.log_text = tk.Text(log_frame, wrap="word", font=("Consolas", 9), yscrollcommand=scroll.set)
                self.log_text.pack(fill="both", expand=True)
                scroll.config(command=self.log_text.yview)
                return page

            def _page_complete(self):
                page = tk.Frame(self.root)
                self._pack_buttons(page, [("完成", self.finish)])
                tk.Label(page, text="安装完成", font=("Microsoft YaHei", 18, "bold")).pack(pady=(60, 15))
                tk.Label(page, text="✓", font=("Arial", 48), fg="#4caf50").pack(pady=10)
                self.complete_info = tk.Label(page, text="", font=("Microsoft YaHei", 11), justify="center")
                self.complete_info.pack(pady=20)
                return page

            def show_page(self, idx):
                for p in self.pages:
                    p.pack_forget()
                self.pages[idx].pack(fill="both", expand=True)
                self.current_page = idx

            def next_page(self):
                if self.current_page == 1 and not self.agree_var.get():
                    messagebox.showwarning("提示", "请先阅读并同意许可协议")
                    return
                if self.current_page == 2 and not self.validate_directory():
                    return
                if self.current_page == 3:
                    return
                if self.current_page >= len(self.pages) - 1:
                    return
                self.current_page += 1
                if self.current_page == 3:
                    self.show_page(3)
                    self.root.after(100, self.do_install)
                elif self.current_page == 4:
                    self.show_complete_info()
                    self.show_page(4)
                else:
                    self.show_page(self.current_page)

            def prev_page(self):
                if self.current_page > 0:
                    self.current_page -= 1
                    self.show_page(self.current_page)

            def cancel(self):
                self.root.destroy()

            def on_closing(self):
                self.root.destroy()

            def finish(self):
                result['install_dir'] = Path(self.install_dir.get()) / APP_DIR_NAME
                self.root.destroy()

            def browse_directory(self):
                d = filedialog.askdirectory(title="选择安装目录", initialdir=self.install_dir.get())
                if d:
                    self.install_dir.set(d)

            def update_dir_preview(self, *_):
                p = Path(self.install_dir.get()) / APP_DIR_NAME
                self.dir_preview.config(text=(
                    f"{p}/\n"
                    "├── bin/\n"
                    "│   └── qingqingHelper.exe\n"
                    "├── images/\n"
                    "│   └── YYYYMMDD/\n"
                    "├── logs/\n"
                    "├── data/\n"
                    "├── chrome-extension/\n"
                    "├── config.json\n"
                    "└── start.bat"
                ))

            def validate_directory(self):
                p = Path(self.install_dir.get())
                if not p.exists():
                    try:
                        p.mkdir(parents=True, exist_ok=True)
                    except Exception as e:
                        messagebox.showerror("错误", f"无法创建目录: {e}")
                        return False
                try:
                    t = p / ".w"
                    t.touch()
                    t.unlink()
                except Exception as e:
                    messagebox.showerror("错误", f"没有写入权限: {e}")
                    return False
                return True

            def log(self, msg):
                self.log_text.insert("end", msg + "\n")
                self.log_text.see("end")
                self.root.update()

            def do_install(self):
                install_path = Path(self.install_dir.get()) / APP_DIR_NAME
                try:
                    self.log("创建安装目录...")
                    self.install_status.config(text="创建目录结构...")
                    self.progress['value'] = 10
                    install_path.mkdir(parents=True, exist_ok=True)
                    for d in ["bin", "images", "logs", "data"]:
                        (install_path / d).mkdir(exist_ok=True)
                    self.log(f"✓ 安装目录: {install_path}")
                    self.log(f"✓ 程序目录: {install_path / 'bin'}")
                    self.log(f"✓ 图片目录: {install_path / 'images'}")
                    self.log(f"✓ 日志目录: {install_path / 'logs'}")
                    self.log(f"✓ 数据目录: {install_path / 'data'}")
                    self.progress['value'] = 30
                    self.root.update()

                    exe_source = get_exe_dir() / "chrome-extension"
                    if not exe_source.exists():
                        exe_source = get_exe_location().parent / "chrome-extension"
                    ext_dest = install_path / "chrome-extension"
                    if exe_source.exists():
                        if ext_dest.exists():
                            shutil.rmtree(str(ext_dest))
                        shutil.copytree(str(exe_source), str(ext_dest))
                        self.log("✓ Chrome扩展已复制")
                    else:
                        self.log("! Chrome扩展不存在（开发模式跳过）")

                    self.progress['value'] = 60
                    self.root.update()

                    config = {
                        'install_dir': str(install_path.parent),
                        'app_dir': str(install_path),
                        'bin_dir': str(install_path / "bin"),
                        'images_dir': str(install_path / "images"),
                        'logs_dir': str(install_path / "logs"),
                        'data_dir': str(install_path / "data"),
                        'port': 5277,
                        'version': '1.0.0',
                        'first_run': False,
                        'install_time': datetime.now().isoformat(),
                    }
                    for p in [install_path / "config.json"]:
                        with open(p, 'w', encoding='utf-8') as f:
                            json.dump(config, f, indent=2, ensure_ascii=False)
                    self.log("✓ 配置文件已保存")

                    self.progress['value'] = 80
                    self.root.update()

                    bat = install_path / "start.bat"
                    with open(bat, 'w', encoding='utf-8') as f:
                        f.write('@echo off\n')
                        f.write('chcp 437 >nul 2>&1\n')
                        f.write(f'echo Starting {APP_NAME}...\n')
                        f.write('cd /d "%~dp0"\n')
                        f.write('start "" "bin\\qingqingHelper.exe"\n')
                    self.log(f"✓ 启动脚本: {bat}")

                    self.progress['value'] = 100
                    self.install_status.config(text="安装完成!")
                    self.root.update()
                    self.log("\n安装完成!")
                    self.root.after(1000, self._goto_complete)
                except Exception as e:
                    self.log(f"\n错误: {e}")
                    self.install_status.config(text="安装失败!")

            def _goto_complete(self):
                self.show_complete_info()
                self.current_page = 4
                self.show_page(4)

            def show_complete_info(self):
                p = Path(self.install_dir.get()) / APP_DIR_NAME
                self.complete_info.config(text=f"已成功安装到:\n{p}")

        # 运行安装向导
        wizard = InstallWizard()
        
        if result['install_dir']:
            return result['install_dir']
        
        return None
        
    except Exception as e:
        print(f"无法打开安装向导: {e}")
        # 回退到命令行输入
        print("\n请手动输入安装目录路径:")
        path = input().strip()
        if path:
            return Path(path)
        return None

def setup_install_directory():
    """设置安装目录"""
    # 检查 config.json（exe 同目录）
    config = load_config()
    if config and 'app_dir' in config:
        app_dir = Path(config['app_dir'])
        if app_dir.exists():
            return app_dir
    
    # 首次运行，显示安装向导
    print("=" * 50)
    print(f"欢迎使用 {APP_NAME}")
    print("=" * 50)
    print("\n请选择安装目录...")
    
    install_dir = select_install_directory()
    
    if not install_dir:
        # 用户取消安装，退出程序
        print("\n安装已取消")
        sys.exit(0)
    
    return install_dir

# ==================== 日志配置 ====================

def setup_logging(logs_dir):
    """配置日志"""
    logs_dir = Path(logs_dir)
    logs_dir.mkdir(parents=True, exist_ok=True)
    
    # 常规日志
    app_log = logs_dir / "service.log"
    
    # 心跳日志
    heartbeat_log = logs_dir / "heartbeat.log"
    
    # 配置常规日志
    app_logger = logging.getLogger('app')
    app_logger.setLevel(logging.INFO)
    
    app_handler = logging.FileHandler(str(app_log), encoding='utf-8')
    app_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    app_logger.addHandler(app_handler)
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    app_logger.addHandler(console_handler)
    
    # 配置心跳日志
    heartbeat_logger = logging.getLogger('heartbeat')
    heartbeat_logger.setLevel(logging.INFO)
    
    heartbeat_handler = logging.FileHandler(str(heartbeat_log), encoding='utf-8')
    heartbeat_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
    heartbeat_logger.addHandler(heartbeat_handler)
    
    return app_logger, heartbeat_logger

# ==================== 主程序 ====================

# 初始化配置
APP_DIR = setup_install_directory()
CONFIG = load_config()

# 如果 CONFIG 为 None，使用默认配置
if not CONFIG:
    CONFIG = {
        'app_dir': str(APP_DIR),
        'bin_dir': str(APP_DIR / 'bin'),
        'images_dir': str(APP_DIR / 'images'),
        'logs_dir': str(APP_DIR / 'logs'),
        'data_dir': str(APP_DIR / 'data'),
        'port': 5277
    }

# 日志目录
LOGS_DIR = Path(CONFIG['logs_dir'])
IMAGES_DIR = Path(CONFIG['images_dir'])
DATA_DIR = Path(CONFIG['data_dir'])

# 配置日志
logger, heartbeat_logger = setup_logging(LOGS_DIR)

# 导入依赖
try:
    import pyautogui
    import pyperclip
    import pygetwindow as gw
    import win32gui
    import win32con
    DEPENDENCIES_OK = True
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.05
except ImportError as e:
    logger.warning(f"依赖缺失: {e}")
    DEPENDENCIES_OK = False

try:
    import winreg
except ImportError:
    pass

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# Flask应用
app = Flask(__name__)
CORS(app)

# 全局状态
server_running = False
server_port = 5277
tray_icon = None
autostart_enabled = False

# ==================== 开机自启 ====================

AUTOSTART_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

def get_exe_path():
    if getattr(sys, 'frozen', False):
        return sys.executable
    return os.path.abspath(__file__)

def is_autostart_enabled():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTOSTART_KEY, 0, winreg.KEY_READ)
        try:
            value, _ = winreg.QueryValueEx(key, APP_NAME)
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            winreg.CloseKey(key)
            return False
    except Exception:
        return False

def set_autostart(enable):
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTOSTART_KEY, 0, winreg.KEY_SET_VALUE)
        
        if enable:
            exe_path = get_exe_path()
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, f'"{exe_path}"')
            logger.info(f"已启用开机自启: {exe_path}")
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
            logger.info("已禁用开机自启")
        
        winreg.CloseKey(key)
        return True
    except Exception as e:
        logger.error(f"设置开机自启失败: {e}")
        return False

# ==================== 工具函数 ====================

def get_today_dir():
    return datetime.now().strftime('%Y%m%d')

def get_work_dir():
    """获取今日工作目录"""
    today = get_today_dir()
    work_dir = IMAGES_DIR / today
    work_dir.mkdir(parents=True, exist_ok=True)
    return work_dir

def find_file(filename):
    """查找文件，支持扩展名映射"""
    name_stem = Path(filename).stem
    name_ext = Path(filename).suffix
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
    
    if name_ext.lower() in image_extensions:
        search_extensions = [name_ext] + [ext for ext in image_extensions if ext != name_ext]
    else:
        search_extensions = image_extensions
    
    # 搜索目录列表
    search_dirs = [
        get_work_dir(),  # 今日目录
        IMAGES_DIR,      # 图片根目录
    ]
    
    # 搜索历史日期目录
    for d in IMAGES_DIR.iterdir():
        if d.is_dir() and d.name.isdigit() and len(d.name) == 8:
            search_dirs.append(d)
    
    # 1. 原始文件名
    for search_dir in search_dirs:
        if search_dir.exists():
            target = search_dir / filename
            if target.exists():
                logger.info(f"找到文件: {target}")
                return str(target)
    
    # 2. 扩展名映射
    for search_dir in search_dirs:
        if search_dir.exists():
            for ext in search_extensions:
                target = search_dir / (name_stem + ext)
                if target.exists():
                    logger.info(f"找到映射文件: {target}")
                    return str(target)
    
    # 3. 模糊匹配
    for search_dir in search_dirs:
        if search_dir.exists():
            for f in search_dir.iterdir():
                if f.is_file() and name_stem in f.stem:
                    if f.suffix.lower() in image_extensions:
                        logger.info(f"找到模糊匹配: {f}")
                        return str(f)
    
    return None

def get_browser_window():
    """获取浏览器窗口"""
    if not DEPENDENCIES_OK:
        return None
    
    try:
        browsers = ['Chrome', 'Edge', 'Google Chrome', 'Microsoft Edge']
        
        for browser_name in browsers:
            try:
                windows = gw.getWindowsWithTitle(browser_name)
                if windows:
                    for win in windows:
                        if not win.isMinimized and win.width > 100 and win.height > 100:
                            return win
                    return windows[0]
            except Exception:
                continue
    except Exception:
        pass
    
    return None

def calculate_screen_position(viewport_x, viewport_y, nav_bar_height=85):
    """将浏览器视口坐标转换为屏幕绝对坐标"""
    window = get_browser_window()
    
    if not window:
        logger.error("未找到浏览器窗口")
        return None, None
    
    try:
        if window.isMinimized:
            window.restore()
        window.activate()
        time.sleep(0.3)
    except Exception as e:
        logger.warning(f"激活窗口失败: {e}")
    
    browser_x = window.left
    browser_y = window.top
    
    screen_x = browser_x + viewport_x
    screen_y = browser_y + viewport_y + nav_bar_height
    
    logger.info(f"浏览器位置: ({browser_x}, {browser_y})")
    logger.info(f"视口坐标: ({viewport_x}, {viewport_y})")
    logger.info(f"导航栏高度: {nav_bar_height}")
    logger.info(f"屏幕坐标: ({screen_x}, {screen_y})")
    
    return screen_x, screen_y

def click_at_position(viewport_x, viewport_y, nav_bar_height=85):
    """点击浏览器页面中的元素"""
    if not DEPENDENCIES_OK:
        logger.error("pyautogui不可用")
        return False
    
    try:
        screen_x, screen_y = calculate_screen_position(viewport_x, viewport_y, nav_bar_height)
        
        if screen_x is None or screen_y is None:
            return False
        
        screen_width, screen_height = pyautogui.size()
        if screen_x < 0 or screen_x > screen_width or screen_y < 0 or screen_y > screen_height:
            logger.error(f"坐标超出屏幕范围: ({screen_x}, {screen_y})")
            return False
        
        logger.info(f"点击屏幕坐标: ({screen_x}, {screen_y})")
        pyautogui.click(screen_x, screen_y)
        time.sleep(0.5)
        return True
        
    except Exception as e:
        logger.error(f"点击失败: {e}")
        return False

def find_file_dialog(target_title='打开'):
    """查找文件对话框"""
    if not DEPENDENCIES_OK:
        return None
    
    result = []
    
    def callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            class_name = win32gui.GetClassName(hwnd)
            
            if class_name == '#32770' or any(kw in title for kw in ['打开', 'Open', '选择', 'Choose']):
                result.append({
                    'hwnd': hwnd,
                    'title': title,
                    'exact_match': title == target_title
                })
    
    try:
        win32gui.EnumWindows(callback, None)
    except Exception:
        pass
    
    exact = [d for d in result if d['exact_match']]
    if exact:
        return exact[0]
    
    partial = [d for d in result if target_title in d['title']]
    if partial:
        return partial[0]
    
    return result[0] if result else None

def focus_window(hwnd):
    """聚焦窗口"""
    try:
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            time.sleep(0.2)
        
        try:
            shell = __import__('win32com.client').Dispatch("WScript.Shell")
            shell.SendKeys('%')
        except:
            pass
        
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.3)
        return True
    except Exception as e:
        logger.warning(f"聚焦窗口失败: {e}")
        return False

def select_file_in_dialog(file_path):
    """在文件对话框中选择文件"""
    if not DEPENDENCIES_OK:
        logger.error("pyautogui不可用")
        return False

    file_path = os.path.abspath(file_path)
    
    if not os.path.exists(file_path):
        logger.error(f"文件不存在: {file_path}")
        return False

    logger.info(f"准备上传文件: {file_path}")

    time.sleep(1.5)
    
    dialog = find_file_dialog(target_title='打开')
    
    if dialog:
        hwnd = dialog['hwnd']
        logger.info(f"找到对话框: '{dialog['title']}'")
        focus_window(hwnd)
        time.sleep(0.5)
    else:
        logger.warning("未找到文件对话框")

    try:
        try:
            original_clipboard = pyperclip.paste()
        except:
            original_clipboard = ''
        
        pyperclip.copy(file_path)
        time.sleep(0.2)
        
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.1)
        
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.3)
        
        pyautogui.press('enter')
        time.sleep(0.5)
        
        try:
            pyperclip.copy(original_clipboard)
        except:
            pass
        
        logger.info("文件上传完成")
        return True
        
    except Exception as e:
        logger.error(f"操作失败: {e}")
        return False

# ==================== Flask路由 ====================

@app.route('/api/health', methods=['GET'])
def health_check():
    heartbeat_logger.info("health check")
    return jsonify({'status': 'ok', 'message': '服务正常'})

@app.route('/images/<path:filename>')
def serve_image(filename):
    """提供图片静态访问"""
    return send_from_directory(str(IMAGES_DIR), filename)

@app.route('/api/save-local-image', methods=['POST'])
def save_local_image():
    """保存本地图片到服务器"""
    data = request.json
    filename = data.get('filename', '')
    file_data = data.get('fileData', '')
    
    if not filename or not file_data:
        return jsonify({'success': False, 'error': '参数不完整'})
    
    try:
        import base64
        
        # 保存到今日目录
        images_dir = get_work_dir()
        
        if file_data.startswith('data:'):
            file_data = file_data.split(',')[1]
        
        file_bytes = base64.b64decode(file_data)
        
        file_path = images_dir / filename
        with open(file_path, 'wb') as f:
            f.write(file_bytes)
        
        logger.info(f"保存本地图片: {file_path}")
        
        return jsonify({
            'success': True,
            'path': str(file_path),
            'url': f'/images/{get_today_dir()}/{filename}'
        })
        
    except Exception as e:
        logger.error(f"保存图片失败: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/get-download-dir', methods=['GET'])
def get_download_dir():
    return jsonify({'download_dir': str(get_work_dir())})

@app.route('/api/get-config', methods=['GET'])
def get_config():
    """获取配置信息"""
    return jsonify({
        'install_dir': str(APP_DIR),
        'images_dir': str(IMAGES_DIR),
        'logs_dir': str(LOGS_DIR),
        'port': server_port
    })

@app.route('/api/select-file-and-upload', methods=['POST'])
def select_file_and_upload():
    """点击坐标并选择文件上传"""
    data = request.json
    filename = data.get('filename', '')
    is_local = data.get('isLocal', False)
    button_x = data.get('buttonX')
    button_y = data.get('buttonY')
    nav_bar_height = data.get('navBarHeight', 85)
    
    if not filename:
        return jsonify({'success': False, 'error': '文件名为空'})

    logger.info(f"查找文件: {filename} (isLocal={is_local})")
    logger.info(f"视口坐标: ({button_x}, {button_y}), 导航栏高度: {nav_bar_height}")

    full_path = find_file(filename)
    
    if not full_path:
        return jsonify({'success': False, 'error': f'文件不存在: {filename}'})

    logger.info(f"找到文件: {full_path}")

    try:
        if button_x is not None and button_y is not None:
            if not click_at_position(button_x, button_y, nav_bar_height):
                return jsonify({'success': False, 'error': '点击按钮失败'})
            
            time.sleep(1.5)
        
        success = select_file_in_dialog(full_path)
        
        if success:
            return jsonify({'success': True, 'message': '文件选择成功'})
        else:
            return jsonify({'success': False, 'error': '文件选择失败'})
    except Exception as e:
        logger.error(f"上传失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/upload-and-search', methods=['POST'])
def upload_and_search():
    data = request.json
    files = data.get('files', [])

    if not files:
        return jsonify({'success': False, 'error': '没有文件'})

    for file_info in files:
        filename = file_info.get('filename', '')
        if filename:
            thread = Thread(target=process_upload, args=(filename,))
            thread.daemon = True
            thread.start()

    return jsonify({'success': True, 'count': len(files)})

def process_upload(filename):
    try:
        full_path = find_file(filename)
        if not full_path:
            logger.error(f"文件不存在: {filename}")
            return

        success = select_file_in_dialog(full_path)
        if success:
            logger.info(f"上传成功: {filename}")
        else:
            logger.error(f"上传失败: {filename}")
    except Exception as e:
        logger.error(f"上传异常: {str(e)}")

# ==================== 系统托盘 ====================

def create_icon_image(color='#4caf50'):
    from PIL import Image, ImageDraw
    
    width = 64
    height = 64
    image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    draw.ellipse([4, 4, width-4, height-4], fill=color)
    draw.ellipse([14, 14, 38, 38], outline='white', width=3)
    draw.line([35, 35, 50, 50], fill='white', width=3)
    
    return image

def update_tray_icon(status='running'):
    global tray_icon
    
    if tray_icon is None:
        return
    
    if status == 'running':
        icon_image = create_icon_image('#4caf50')
        title = f'{APP_NAME} - 运行中 (端口:{server_port})'
    elif status == 'error':
        icon_image = create_icon_image('#f44336')
        title = f'{APP_NAME} - 错误'
    else:
        icon_image = create_icon_image('#9e9e9e')
        title = f'{APP_NAME} - 已停止'
    
    try:
        tray_icon.icon = icon_image
        tray_icon.title = title
    except:
        pass

def on_toggle_autostart(icon, item):
    global autostart_enabled
    autostart_enabled = not autostart_enabled
    set_autostart(autostart_enabled)
    item.checked = autostart_enabled

def on_open_folder(icon, item):
    os.startfile(str(IMAGES_DIR))

def on_open_logs(icon, item):
    os.startfile(str(LOGS_DIR))

def on_restart(icon, item):
    global server_running
    logger.info("重启服务...")
    server_running = False
    time.sleep(1)
    start_flask_server()
    server_running = True
    update_tray_icon('running')

def on_exit(icon, item):
    global server_running
    logger.info("退出服务...")
    server_running = False
    try:
        icon.stop()
    except:
        pass
    sys.exit(0)

def start_flask_server():
    global server_running
    
    def run_server():
        try:
            logger.info(f"启动服务器 http://localhost:{server_port}")
            logger.info(f"图片目录: {IMAGES_DIR}")
            app.run(host='0.0.0.0', port=server_port, debug=False, use_reloader=False)
        except Exception as e:
            logger.error(f"服务器错误: {e}")
            update_tray_icon('error')
    
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    server_running = True

def create_tray_icon():
    global tray_icon, autostart_enabled
    
    import pystray
    
    autostart_enabled = is_autostart_enabled()
    
    menu = pystray.Menu(
        pystray.MenuItem('开机自启', on_toggle_autostart, checked=lambda item: autostart_enabled),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('打开图片目录', on_open_folder),
        pystray.MenuItem('打开日志目录', on_open_logs),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('重启服务', on_restart),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('退出', on_exit)
    )
    
    icon_image = create_icon_image('#4caf50')
    
    tray_icon = pystray.Icon(
        name=APP_NAME,
        icon=icon_image,
        title=f'{APP_NAME} - 启动中...',
        menu=menu
    )
    
    return tray_icon

# ==================== 主入口 ====================

def main():
    import threading
    import socket
    
    # 单实例检查：端口是否已被占用
    def is_port_in_use(port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('127.0.0.1', port))
                return False
            except OSError:
                return True
    
    if is_port_in_use(server_port):
        msg = f"{APP_NAME} 已在运行中（端口 {server_port} 被占用）"
        print(msg)
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, msg, APP_NAME, 0x40)
        except:
            pass
        sys.exit(0)
    
    if not DEPENDENCIES_OK:
        msg = "错误: 缺少必要的依赖库"
        print(msg)
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, msg, APP_NAME, 0x10)
        except:
            pass
        sys.exit(1)
    
    logger.info("=" * 50)
    logger.info(f"{APP_NAME} - 系统托盘版")
    logger.info("=" * 50)
    logger.info(f"安装目录: {APP_DIR}")
    logger.info(f"图片目录: {IMAGES_DIR}")
    logger.info(f"日志目录: {LOGS_DIR}")
    logger.info(f"服务端口: {server_port}")
    logger.info("=" * 50)
    
    start_flask_server()
    update_tray_icon('running')
    
    icon = create_tray_icon()
    
    try:
        icon.run()
    except KeyboardInterrupt:
        logger.info("收到中断信号")
    except Exception as e:
        logger.error(f"托盘错误: {e}")
    finally:
        logger.info("服务已停止")

if __name__ == '__main__':
    main()