#!/usr/bin/env python3
"""
青青小助手 - 安装向导
"""

import os
import sys
import json
import shutil
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

APP_NAME = "青青小助手"
APP_DIR_NAME = "QingQingHelper"  # 英文文件夹名
DEFAULT_INSTALL_DIR = str(Path.home() / "AppData" / "Local" / "QingQingHelper")
WIN_SIZE = "600x500"

LICENSE_TEXT = """MIT License

Copyright (c) 2026 HuanBaby1314

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE."""


class InstallerWizard:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title(f"{APP_NAME} 安装向导")
        self.root.geometry(WIN_SIZE)
        self.root.resizable(False, False)

        # 读取上次安装目录
        last_install_dir = self._load_last_install_dir()
        self.install_dir = tk.StringVar(value=last_install_dir or DEFAULT_INSTALL_DIR)
        
        self.current_page = 0
        self.pages = []

        self.create_pages()
        self.show_page(0)
        self.center_window()
        self.root.deiconify()

    def _load_last_install_dir(self):
        """读取上次安装目录"""
        # 1. 优先检查环境变量
        env_path = os.environ.get('QINGQINGHELPER_HOME')
        if env_path and Path(env_path).exists():
            print(f"[安装器] 从环境变量读取安装目录: {env_path}")
            return env_path
        
        # 2. 检查 exe 同目录和上级目录的 config.json
        if getattr(sys, 'frozen', False):
            exe_dir = Path(sys.executable).parent
        else:
            exe_dir = Path(__file__).parent
        
        for cfg_path in [exe_dir / "config.json", exe_dir.parent / "config.json"]:
            if cfg_path.exists():
                try:
                    with open(cfg_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    if 'app_dir' in config:
                        print(f"[安装器] 从 config.json 读取安装目录: {config['app_dir']}")
                        return config['app_dir']
                    if 'install_dir' in config:
                        # install_dir 是父目录，拼接项目名
                        install_path = str(Path(config['install_dir']) / APP_DIR_NAME)
                        print(f"[安装器] 从 config.json 读取安装目录: {install_path}")
                        return install_path
                except:
                    pass
        
        print("[安装器] 未找到已安装目录，使用默认目录")
        return None

    def center_window(self):
        self.root.update_idletasks()
        w, h = WIN_SIZE.split("x")
        w, h = int(w), int(h)
        x = (self.root.winfo_screenwidth() // 2) - (w // 2)
        y = (self.root.winfo_screenheight() // 2) - (h // 2)
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def create_pages(self):
        self.pages = [
            self._page_welcome(),
            self._page_license(),
            self._page_directory(),
            self._page_installing(),
            self._page_complete(),
        ]

    # ============================================================
    # 底部按钮栏
    # 规则：pack(side="bottom") 必须最先调用，之后再 pack 内容
    # ============================================================

    def _pack_buttons(self, page, buttons):
        """
        buttons: [(text, callback), ...] 从左到右排列，右对齐
        """
        bar = tk.Frame(page)
        bar.pack(side="bottom", fill="x", padx=30, pady=15)
        # 右对齐：创建内部框架并右对齐
        inner = tk.Frame(bar)
        inner.pack(side="right")
        for text, callback in buttons:
            tk.Button(inner, text=text, command=callback,
                      width=10, font=("Microsoft YaHei", 10)).pack(side="left", padx=5)

    # ============================================================
    # 第1页：欢迎
    # ============================================================

    def _page_welcome(self):
        page = tk.Frame(self.root)
        self._pack_buttons(page, [("取消", self.cancel), ("下一步 >", self.next_page)])

        tk.Label(page, text=f"欢迎安装 {APP_NAME}",
                 font=("Microsoft YaHei", 18, "bold")).pack(pady=(40, 10))
        tk.Label(page, text="批量下载网页图片并上传到Google搜图的工具",
                 font=("Microsoft YaHei", 11)).pack(pady=5)
        tk.Label(page, text="版本 1.0.0",
                 font=("Microsoft YaHei", 10), fg="gray").pack(pady=5)

        box = tk.Frame(page)
        box.pack(pady=20, padx=60, anchor="w")
        for f in ["✓ Chrome/Edge 扩展支持", "✓ 批量图片扫描与下载",
                   "✓ Google 搜图自动上传", "✓ 系统托盘后台服务", "✓ 本地图片管理"]:
            tk.Label(box, text=f, font=("Microsoft YaHei", 10), anchor="w").pack(fill="x", pady=2)

        return page

    # ============================================================
    # 第2页：许可协议
    # ============================================================

    def _page_license(self):
        page = tk.Frame(self.root)
        self._pack_buttons(page, [
            ("取消", self.cancel),
            ("< 上一步", self.prev_page),
            ("下一步 >", self.next_page),
        ])

        tk.Label(page, text="许可协议", font=("Microsoft YaHei", 14, "bold")).pack(pady=(20, 5))

        # 协议文本（expand=True 填充中间区域）
        txt_frame = tk.Frame(page)
        txt_frame.pack(padx=30, pady=5, fill="both", expand=True)
        scroll = tk.Scrollbar(txt_frame)
        scroll.pack(side="right", fill="y")
        txt = tk.Text(txt_frame, wrap="word", font=("Consolas", 9), yscrollcommand=scroll.set)
        txt.insert("1.0", LICENSE_TEXT)
        txt.config(state="disabled")
        txt.pack(side="left", fill="both", expand=True)
        scroll.config(command=txt.yview)

        # 勾选框（固定在底部按钮栏上方）
        self.agree_var = tk.BooleanVar(value=True)
        tk.Checkbutton(page, text="我已阅读并同意许可协议",
                       variable=self.agree_var,
                       font=("Microsoft YaHei", 10)).pack(side="bottom", pady=8)

        return page

    # ============================================================
    # 第3页：选择安装位置
    # ============================================================

    def _page_directory(self):
        page = tk.Frame(self.root)
        self._pack_buttons(page, [
            ("取消", self.cancel),
            ("< 上一步", self.prev_page),
            ("下一步 >", self.next_page),
        ])

        tk.Label(page, text="选择安装位置",
                 font=("Microsoft YaHei", 14, "bold")).pack(pady=(20, 2))
        tk.Label(page, text="选择软件的安装目录：",
                 font=("Microsoft YaHei", 10), fg="gray").pack(pady=(0, 8))

        # 路径输入
        row = tk.Frame(page)
        row.pack(padx=30, fill="x")
        tk.Label(row, text="安装目录:", font=("Microsoft YaHei", 10)).pack(anchor="w")
        inp = tk.Frame(row)
        inp.pack(fill="x", pady=3)
        tk.Entry(inp, textvariable=self.install_dir,
                 font=("Microsoft YaHei", 10)).pack(side="left", fill="x", expand=True)
        tk.Button(inp, text="浏览...", command=self.browse_dir,
                  font=("Microsoft YaHei", 10)).pack(side="right", padx=5)

        # 目录预览
        box = tk.LabelFrame(page, text="目录结构预览", font=("Microsoft YaHei", 10))
        box.pack(padx=30, pady=5, fill="both", expand=True)
        self.dir_preview = tk.Label(box, font=("Consolas", 10), justify="left", anchor="nw")
        self.dir_preview.pack(padx=10, pady=8, fill="both", expand=True)
        self.install_dir.trace_add("write", self._refresh_preview)
        self._refresh_preview()

        self.space_label = tk.Label(page, text="", font=("Microsoft YaHei", 9), fg="gray")
        self.space_label.pack(pady=2)
        self._refresh_space()

        return page

    # ============================================================
    # 第4页：安装进度
    # ============================================================

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
        self.log_text = tk.Text(log_frame, wrap="word", font=("Consolas", 9),
                                yscrollcommand=scroll.set)
        self.log_text.pack(fill="both", expand=True)
        scroll.config(command=self.log_text.yview)

        return page

    # ============================================================
    # 第5页：完成
    # ============================================================

    def _page_complete(self):
        page = tk.Frame(self.root)
        self._pack_buttons(page, [("完成", self.finish)])

        tk.Label(page, text="安装完成",
                 font=("Microsoft YaHei", 18, "bold")).pack(pady=(60, 15))
        tk.Label(page, text="✓", font=("Arial", 48), fg="#4caf50").pack(pady=10)
        self.complete_info = tk.Label(page, text="", font=("Microsoft YaHei", 11), justify="center")
        self.complete_info.pack(pady=20)

        return page

    # ============================================================
    # 导航
    # ============================================================

    def show_page(self, idx):
        for p in self.pages:
            p.pack_forget()
        self.pages[idx].pack(fill="both", expand=True)
        self.current_page = idx

    def next_page(self):
        if self.current_page == 1 and not self.agree_var.get():
            messagebox.showwarning("提示", "请先阅读并同意许可协议")
            return
        if self.current_page == 2 and not self._validate_dir():
            return
        if self.current_page == 3:
            return
        if self.current_page >= len(self.pages) - 1:
            return
        self.current_page += 1
        if self.current_page == 3:
            self.show_page(3)
            self.root.after(100, self._do_install)
        elif self.current_page == 4:
            self._show_complete_info()
            self.show_page(4)
        else:
            self.show_page(self.current_page)

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.show_page(self.current_page)

    def cancel(self):
        self.root.destroy()



    def finish(self):
        # 启动服务
        install_path = Path(self.install_dir.get())
        exe_path = install_path / "bin" / "qingqingHelper.exe"
        if exe_path.exists():
            try:
                os.startfile(str(exe_path))
                print(f"服务已启动: {exe_path}")
            except Exception as e:
                print(f"启动服务失败: {e}")
        self.root.destroy()

    # ============================================================
    # 工具
    # ============================================================

    def browse_dir(self):
        d = filedialog.askdirectory(title="选择安装目录", initialdir=self.install_dir.get())
        if d:
            self.install_dir.set(d)

    def _refresh_preview(self, *_):
        p = Path(self.install_dir.get())
        # 统一使用系统路径分隔符
        sep = os.sep
        self.dir_preview.config(text=(
            f"{p}{sep}\n"
            f"├── bin{sep}\n"
            "│   └── qingqingHelper.exe\n"
            f"├── images{sep}\n"
            "│   └── YYYYMMDD\n"
            f"├── logs{sep}\n"
            f"├── data{sep}\n"
            f"├── extensions{sep}\n"
            f"│   └── qingqingHelper{sep}\n"
            "├── config.json\n"
            "├── start.bat\n"
            "└── uninstall.exe"
        ))

    def _refresh_space(self):
        try:
            p = Path(self.install_dir.get())
            if p.exists():
                gb = shutil.disk_usage(str(p)).free / (1024 ** 3)
                self.space_label.config(text=f"可用磁盘空间: {gb:.1f} GB")
        except Exception:
            pass

    def _validate_dir(self):
        p = Path(self.install_dir.get())
        # 确保路径以 APP_DIR_NAME 结尾
        if p.name != APP_DIR_NAME:
            p = p / APP_DIR_NAME
            self.install_dir.set(str(p))
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

    def _register_protocol(self, install_path):
        """注册自定义协议 qqhelpr://，用于浏览器扩展启动服务
        指向 start.bat，用绝对路径写入注册表（不依赖环境变量）
        """
        try:
            import winreg
            bat_path = str(Path(install_path) / "start.bat")

            if not Path(bat_path).exists():
                self._log(f"! 启动脚本不存在: {bat_path}，跳过协议注册")
                return False

            # 注册协议根键
            key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, "qqhelpr")
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "URL:QQHelpr Protocol")
            winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
            winreg.CloseKey(key)

            # 注册命令处理（指向 start.bat）
            cmd_key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, r"qqhelpr\shell\open\command")
            winreg.SetValueEx(cmd_key, "", 0, winreg.REG_SZ,
                              f'"{bat_path}" "%1"')
            winreg.CloseKey(cmd_key)

            self._log(f"✓ 自定义协议已注册: qqhelpr:// -> {bat_path}")
            return True
        except Exception as e:
            self._log(f"! 注册自定义协议失败: {e}（不影响使用）")
            return False

    def _log(self, msg):
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.root.update()

    # ============================================================
    # 安装逻辑
    # ============================================================

    def _check_write_permission(self, path):
        """检查是否有写入权限"""
        try:
            # 确保目录存在
            path.mkdir(parents=True, exist_ok=True)
            # 测试写入
            test_file = path / ".permission_test"
            test_file.write_text("test", encoding='utf-8')
            test_file.unlink()
            return True
        except Exception:
            return False

    def _request_admin(self):
        """请求管理员权限重新运行"""
        try:
            import ctypes
            if getattr(sys, 'frozen', False):
                exe = sys.executable
            else:
                exe = sys.executable
            # ShellExecuteW 返回大于 32 表示成功
            ret = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", exe, "", None, 1
            )
            return ret > 32
        except Exception:
            return False

    def _do_install(self):
        install_path = Path(self.install_dir.get())
        try:
            # 检测写入权限
            self._log("检查安装目录权限...")
            self.install_status.config(text="检查权限...")
            
            if not self._check_write_permission(install_path):
                self._log(f"! 没有写入权限: {install_path}")
                self._log("尝试请求管理员权限...")
                
                if self._request_admin():
                    self._log("已请求管理员权限，当前安装器将关闭")
                    self._log("请在新打开的管理员窗口中继续安装")
                    self.root.after(1500, self.root.destroy)
                    return
                else:
                    self._log("! 无法获取管理员权限")
                    from tkinter import messagebox
                    messagebox.showerror("权限不足", 
                        f"没有写入权限:\n{install_path}\n\n"
                        "请以管理员身份运行安装器，或选择其他安装目录。\n\n"
                        "建议安装到:\n"
                        "- D:\\QingQingHelper\n"
                        "- C:\\Users\\{用户名}\\AppData\\Local\\QingQingHelper")
                    self.install_status.config(text="权限不足，请选择其他目录")
                    return

            self._log("✓ 权限检查通过")

            # 检测并关闭已运行的服务（通过端口检测，避免杀掉安装器自己）
            self._log("检查已运行的服务...")
            self.install_status.config(text="检查已运行的服务...")
            try:
                import subprocess
                # 用 netstat 查找占用 5277 端口的进程
                result = subprocess.run(
                    ['netstat', '-ano', '-p', 'tcp'],
                    capture_output=True, text=True, timeout=10
                )
                # 查找包含 :5277 的行
                pid_to_kill = None
                for line in result.stdout.splitlines():
                    if ':5277' in line and 'LISTENING' in line:
                        parts = line.split()
                        if parts:
                            pid_to_kill = parts[-1]
                            break
                
                if pid_to_kill and pid_to_kill != str(os.getpid()):
                    self._log(f"检测到服务进程 (PID: {pid_to_kill})，正在关闭...")
                    subprocess.run(['taskkill', '/F', '/PID', pid_to_kill], 
                                 capture_output=True, timeout=10)
                    import time
                    time.sleep(1)
                    self._log("✓ 已关闭旧服务")
                else:
                    self._log("✓ 没有检测到运行中的服务")
            except Exception as e:
                self._log(f"! 检查服务状态失败: {e}，继续安装...")

            self._log("创建安装目录...")
            self.install_status.config(text="创建目录结构...")
            self.progress["value"] = 10

            install_path.mkdir(parents=True, exist_ok=True)
            for d in ["bin", "images", "logs", "data"]:
                (install_path / d).mkdir(exist_ok=True)

            self._log(f"✓ 安装目录: {install_path}")
            self._log(f"✓ 程序目录: {install_path / 'bin'}")
            self._log(f"✓ 图片目录: {install_path / 'images'}")
            self._log(f"✓ 日志目录: {install_path / 'logs'}")
            self._log(f"✓ 数据目录: {install_path / 'data'}")

            self.progress["value"] = 30
            self.root.update()

            if getattr(sys, "frozen", False):
                src_dir = Path(sys.executable).parent
            else:
                src_dir = Path(__file__).parent

            # 复制服务程序
            self._log("\n复制程序文件...")
            self.install_status.config(text="复制程序文件...")
            if getattr(sys, "frozen", False):
                exe_src = Path(sys._MEIPASS) / "server.exe"
            else:
                exe_src = src_dir / "dist" / "server.exe"
            exe_dst = install_path / "bin" / "qingqingHelper.exe"
            if exe_src.exists():
                shutil.copy2(str(exe_src), str(exe_dst))
                self._log(f"✓ 服务程序: {exe_dst}")
            else:
                self._log("! 服务程序不存在（开发模式跳过）")

            # 复制卸载程序
            if getattr(sys, "frozen", False):
                uninstall_src = Path(sys._MEIPASS) / "uninstall.exe"
            else:
                uninstall_src = src_dir / "dist" / "uninstall.exe"
            uninstall_dst = install_path / "uninstall.exe"
            if uninstall_src.exists():
                shutil.copy2(str(uninstall_src), str(uninstall_dst))
                self._log(f"✓ 卸载程序: {uninstall_dst}")
            else:
                self._log("! 卸载程序不存在（开发模式跳过）")

            # 复制Chrome扩展
            if getattr(sys, "frozen", False):
                ext_src = Path(sys._MEIPASS) / "extensions" / "qingqingHelper"
            else:
                ext_src = src_dir.parent / "extensions" / "qingqingHelper"
            ext_dst = install_path / "extensions" / "qingqingHelper"
            if ext_src.exists():
                if ext_dst.exists():
                    shutil.rmtree(str(ext_dst))
                ext_dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(str(ext_src), str(ext_dst))
                self._log("✓ Chrome扩展已复制")
            else:
                self._log("! Chrome扩展不存在（开发模式跳过）")

            self.progress["value"] = 60
            self.root.update()

            # 配置文件
            self._log("\n创建配置文件...")
            self.install_status.config(text="创建配置文件...")
            config = {
                "install_dir": str(install_path.parent),
                "app_dir": str(install_path),
                "bin_dir": str(install_path / "bin"),
                "images_dir": str(install_path / "images"),
                "logs_dir": str(install_path / "logs"),
                "data_dir": str(install_path / "data"),
                "port": 5277,
                "version": "1.0.0",
                "first_run": False,
                "install_time": datetime.now().isoformat(),
            }
            for p in [install_path / "config.json"]:
                with open(p, "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
            self._log("✓ 配置文件已保存")

            # 设置环境变量 QINGQINGHELPER_HOME（用户级别 + 当前进程）
            try:
                import winreg
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Environment",
                    0,
                    winreg.KEY_SET_VALUE
                )
                winreg.SetValueEx(key, "QINGQINGHELPER_HOME", 0, winreg.REG_SZ, str(install_path))
                winreg.CloseKey(key)
                # 立即更新当前进程的环境变量
                os.environ['QINGQINGHELPER_HOME'] = str(install_path)
                self._log(f"✓ 环境变量已设置: QINGQINGHELPER_HOME={install_path}")
                
                # 广播环境变量变更消息，让所有进程刷新
                try:
                    import ctypes
                    HWND_BROADCAST = 0xFFFF
                    WM_SETTINGCHANGE = 0x001A
                    SMTO_ABORTIFHUNG = 0x0002
                    result = ctypes.c_long()
                    ctypes.windll.user32.SendMessageTimeoutW(
                        HWND_BROADCAST, WM_SETTINGCHANGE, 0, 
                        "Environment", SMTO_ABORTIFHUNG, 5000, 
                        ctypes.byref(result)
                    )
                    self._log("✓ 环境变量已刷新")
                except Exception as e:
                    self._log(f"! 刷新环境变量失败: {e}（不影响使用）")
            except Exception as e:
                self._log(f"! 设置环境变量失败: {e}（不影响使用）")

            self.progress["value"] = 80
            self.root.update()

            # 注册自定义协议 qqhelpr://（指向 start.bat）
            self._log("\\n注册自定义协议...")
            self.install_status.config(text="注册自定义协议...")
            self._register_protocol(str(install_path))

            # 启动脚本
            self._log("\n创建启动脚本...")
            bat = install_path / "start.bat"
            with open(bat, "w", encoding="utf-8") as f:
                f.write("@echo off\n")
                f.write("chcp 437 >nul 2>&1\n")
                f.write(f"echo Starting {APP_NAME}...\n")
                f.write('cd /d "%~dp0"\n')
                f.write('start "" "bin\\qingqingHelper.exe"\n')
            self._log(f"✓ 启动脚本: {bat}")

            self.progress["value"] = 100
            self.install_status.config(text="安装完成!")
            self.root.update()

            self._log("\n" + "=" * 40)
            self._log("安装完成!")
            self._log("=" * 40)

            self.root.after(1000, self._goto_complete)

        except Exception as e:
            self._log(f"\n错误: {e}")
            self.install_status.config(text="安装失败!")

    def _goto_complete(self):
        self._show_complete_info()
        self.current_page = 4
        self.show_page(4)

    def _show_complete_info(self):
        p = Path(self.install_dir.get())
        self.complete_info.config(text=f"已成功安装到:\n{p}")

    def run(self):
        self.root.mainloop()


def main():
    InstallerWizard().run()


if __name__ == "__main__":
    main()
