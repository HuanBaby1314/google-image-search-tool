#!/usr/bin/env python3
"""
青青小助手 - 卸载向导
"""

import os
import sys
import json
import shutil
import subprocess
import time
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

APP_NAME = "青青小助手"
APP_DIR_NAME = "QingQingHelper"
WIN_SIZE = "500x400"


class UninstallWizard:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title(f"{APP_NAME} - 卸载")
        self.root.geometry(WIN_SIZE)
        self.root.resizable(False, False)

        # 检测安装目录
        self.install_path = self._detect_install_path()
        
        if not self.install_path:
            messagebox.showerror("错误", "未找到安装目录，无法卸载")
            self.root.destroy()
            return

        self.current_page = 0
        self.pages = []
        self.delete_user_data = tk.BooleanVar(value=False)

        self.create_pages()
        self.show_page(0)
        self.center_window()
        self.root.deiconify()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def center_window(self):
        self.root.update_idletasks()
        w, h = 500, 400
        x = (self.root.winfo_screenwidth() // 2) - (w // 2)
        y = (self.root.winfo_screenheight() // 2) - (h // 2)
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _detect_install_path(self):
        """检测安装目录"""
        # 1. 环境变量
        env_path = os.environ.get('QINGQINGHELPER_HOME')
        if env_path and Path(env_path).exists():
            return Path(env_path)
        
        # 2. config.json
        if getattr(sys, 'frozen', False):
            exe_dir = Path(sys.executable).parent
        else:
            exe_dir = Path(__file__).parent
        
        for cfg_path in [exe_dir / "config.json", exe_dir.parent / "config.json"]:
            if cfg_path.exists():
                try:
                    with open(cfg_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    if 'app_dir' in config and Path(config['app_dir']).exists():
                        return Path(config['app_dir'])
                    if 'install_dir' in config:
                        p = Path(config['install_dir']) / APP_DIR_NAME
                        if p.exists():
                            return p
                except:
                    pass
        
        return None

    def create_pages(self):
        self.pages = [
            self._page_confirm(),
            self._page_options(),
            self._page_progress(),
            self._page_done(),
        ]

    def _pack_buttons(self, page, buttons):
        bar = tk.Frame(page)
        bar.pack(side="bottom", fill="x", padx=30, pady=15)
        inner = tk.Frame(bar)
        inner.pack(side="right")
        # 反转按钮顺序，从右往左排列
        for text, callback in reversed(buttons):
            tk.Button(inner, text=text, command=callback,
                      width=10, font=("Microsoft YaHei", 10)).pack(side="left", padx=5)

    # ==================== 页面 ====================

    def _page_confirm(self):
        page = tk.Frame(self.root)
        self._pack_buttons(page, [("卸载", self.next_page), ("取消", self.cancel)])

        tk.Label(page, text=f"卸载 {APP_NAME}",
                 font=("Microsoft YaHei", 18, "bold")).pack(pady=(50, 20))
        
        tk.Label(page, text="确定要卸载此程序吗？",
                 font=("Microsoft YaHei", 12)).pack(pady=10)
        
        tk.Label(page, text=f"安装目录: {self.install_path}",
                 font=("Microsoft YaHei", 9), fg="gray").pack(pady=5)

        return page

    def _page_options(self):
        page = tk.Frame(self.root)
        self._pack_buttons(page, [("下一步 >", self.next_page), ("< 上一步", self.prev_page)])

        tk.Label(page, text="卸载选项",
                 font=("Microsoft YaHei", 14, "bold")).pack(pady=(40, 20))

        tk.Label(page, text="选择要删除的内容：",
                 font=("Microsoft YaHei", 10)).pack(anchor="w", padx=50)

        # 程序文件（必删）
        frame1 = tk.Frame(page)
        frame1.pack(anchor="w", padx=60, pady=10, fill="x")
        tk.Label(frame1, text="✓ 程序文件（bin, extensions, config.json, start.bat）",
                 font=("Microsoft YaHei", 10), fg="gray").pack(anchor="w")
        tk.Label(frame1, text="  必须删除", font=("Microsoft YaHei", 9), fg="gray").pack(anchor="w")

        # 用户数据（可选）
        frame2 = tk.Frame(page)
        frame2.pack(anchor="w", padx=60, pady=10, fill="x")
        tk.Checkbutton(frame2, text="删除用户数据（images, logs, data）",
                       variable=self.delete_user_data,
                       font=("Microsoft YaHei", 10)).pack(anchor="w")
        tk.Label(frame2, text="  默认保留，取消勾选可保留搜索记录和下载的图片",
                 font=("Microsoft YaHei", 9), fg="gray").pack(anchor="w")

        return page

    def _page_progress(self):
        page = tk.Frame(self.root)

        tk.Label(page, text="正在卸载",
                 font=("Microsoft YaHei", 14, "bold")).pack(pady=(40, 20))
        
        self.progress = ttk.Progressbar(page, length=350, mode="determinate")
        self.progress.pack(pady=10)
        
        self.status_label = tk.Label(page, text="准备卸载...", font=("Microsoft YaHei", 10))
        self.status_label.pack(pady=5)

        self.log_text = tk.Text(page, font=("Consolas", 9), height=8, width=55)
        self.log_text.pack(padx=30, pady=10, fill="both", expand=True)

        return page

    def _page_done(self):
        page = tk.Frame(self.root)
        self._pack_buttons(page, [("完成", self.finish)])

        tk.Label(page, text="卸载完成",
                 font=("Microsoft YaHei", 18, "bold")).pack(pady=(60, 15))
        tk.Label(page, text="✓", font=("Arial", 48), fg="#4caf50").pack(pady=10)
        
        self.done_info = tk.Label(page, text="", font=("Microsoft YaHei", 11), justify="center")
        self.done_info.pack(pady=20)

        return page

    # ==================== 导航 ====================

    def show_page(self, idx):
        for p in self.pages:
            p.pack_forget()
        self.pages[idx].pack(fill="both", expand=True)
        self.current_page = idx

    def next_page(self):
        if self.current_page == 0:  # 确认页
            self.current_page = 1
            self.show_page(1)
        elif self.current_page == 1:  # 选项页
            self.current_page = 2
            self.show_page(2)
            self.root.after(100, self.do_uninstall)
        elif self.current_page == 2:  # 进度页
            pass
        elif self.current_page == 3:  # 完成页
            self.finish()

    def prev_page(self):
        if self.current_page > 0 and self.current_page < 2:
            self.current_page -= 1
            self.show_page(self.current_page)

    def cancel(self):
        self.root.destroy()

    def on_close(self):
        self.root.destroy()

    def finish(self):
        self.root.destroy()
        # 启动自删除批处理
        self._start_self_delete()

    # ==================== 工具 ====================

    def log(self, msg):
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.root.update()

    # ==================== 卸载逻辑 ====================

    def do_uninstall(self):
        try:
            # 1. 停止服务
            self.log("停止运行中的服务...")
            self.status_label.config(text="停止服务...")
            self.progress["value"] = 10
            self._stop_service()

            # 2. 删除程序文件
            self.log("\n删除程序文件...")
            self.status_label.config(text="删除程序文件...")
            self.progress["value"] = 30
            
            program_items = ["bin", "extensions", "config.json", "start.bat"]
            for item in program_items:
                target = self.install_path / item
                if target.exists():
                    if target.is_dir():
                        shutil.rmtree(str(target))
                    else:
                        target.unlink()
                    self.log(f"✓ 已删除: {item}")
                else:
                    self.log(f"  跳过: {item}（不存在）")

            # 3. 删除用户数据（可选）
            self.progress["value"] = 60
            if self.delete_user_data.get():
                self.log("\n删除用户数据...")
                self.status_label.config(text="删除用户数据...")
                
                user_items = ["images", "logs", "data"]
                for item in user_items:
                    target = self.install_path / item
                    if target.exists():
                        shutil.rmtree(str(target))
                        self.log(f"✓ 已删除: {item}")
            else:
                self.log("\n保留用户数据")

            # 4. 移除环境变量
            self.progress["value"] = 80
            self.log("\n移除环境变量...")
            self.status_label.config(text="移除环境变量...")
            self._remove_env_var()

            # 4.5 移除自定义协议
            self.log("\n移除自定义协议...")
            self.status_label.config(text="移除自定义协议...")
            self._unregister_protocol()

            # 5. 删除桌面快捷方式
            self.log("\n删除快捷方式...")
            self.status_label.config(text="删除快捷方式...")
            self._remove_shortcuts()

            # 6. 删除安装目录（如果为空）
            self.progress["value"] = 90
            self.log("\n检查安装目录...")
            try:
                if self.install_path.exists() and not any(self.install_path.iterdir()):
                    self.install_path.rmdir()
                    self.log("✓ 已删除空的安装目录")
                else:
                    remaining = list(self.install_path.iterdir()) if self.install_path.exists() else []
                    if remaining:
                        self.log(f"安装目录仍有 {len(remaining)} 个项目，保留目录")
            except Exception as e:
                self.log(f"! 删除安装目录失败: {e}")

            self.progress["value"] = 100
            self.status_label.config(text="卸载完成!")
            
            self.log("\n" + "=" * 40)
            self.log("卸载完成!")
            self.log("=" * 40)

            self.done_info.config(
                text=f"已成功卸载 {APP_NAME}\n\n"
                     f"{'用户数据已删除' if self.delete_user_data.get() else '用户数据已保留'}"
            )

            self.root.after(1000, lambda: self.show_page(3))

        except Exception as e:
            self.log(f"\n卸载出错: {e}")
            self.status_label.config(text="卸载出错!")
            messagebox.showerror("错误", f"卸载过程中出错:\n{e}")

    def _stop_service(self):
        """停止运行中的服务"""
        try:
            # 通过端口查找并停止服务
            result = subprocess.run(
                ['netstat', '-ano', '-p', 'tcp'],
                capture_output=True, text=True, timeout=10
            )
            for line in result.stdout.splitlines():
                if ':5277' in line and 'LISTENING' in line:
                    parts = line.split()
                    if parts:
                        pid = parts[-1]
                        if pid != str(os.getpid()):
                            self.log(f"  停止服务进程 (PID: {pid})")
                            subprocess.run(['taskkill', '/F', '/PID', pid],
                                         capture_output=True, timeout=10)
                            time.sleep(1)
                            self.log("✓ 服务已停止")
                            return
            self.log("  没有检测到运行中的服务")
        except Exception as e:
            self.log(f"! 停止服务失败: {e}")

    def _remove_env_var(self):
        """移除环境变量"""
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Environment",
                0,
                winreg.KEY_SET_VALUE
            )
            try:
                winreg.DeleteValue(key, "QINGQINGHELPER_HOME")
                self.log("✓ 已移除环境变量 QINGQINGHELPER_HOME")
            except FileNotFoundError:
                self.log("  环境变量不存在，跳过")
            winreg.CloseKey(key)
            
            # 广播环境变量变更
            try:
                import ctypes
                ctypes.windll.user32.SendMessageTimeoutW(
                    0xFFFF, 0x001A, 0, "Environment", 0x0002, 5000, None
                )
            except:
                pass
        except Exception as e:
            self.log(f"! 移除环境变量失败: {e}")

    def _unregister_protocol(self):
        """移除自定义协议 qqhelpr://"""
        try:
            import winreg
            # 删除整个 qqhelpr 键（含子键）
            try:
                # 先删子键
                winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, r"qqhelpr\shell\open\command")
                winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, r"qqhelpr\shell\open")
                winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, r"qqhelpr\shell")
                winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, "qqhelpr")
                self.log("✓ 已移除自定义协议 qqhelpr://")
            except FileNotFoundError:
                self.log("  自定义协议不存在，跳过")
        except Exception as e:
            self.log(f"! 移除自定义协议失败: {e}")

    def _remove_shortcuts(self):
        """删除快捷方式"""
        try:
            desktop = Path.home() / "Desktop"
            shortcut = desktop / f"{APP_NAME}.lnk"
            if shortcut.exists():
                shortcut.unlink()
                self.log("✓ 已删除桌面快捷方式")
            else:
                self.log("  桌面快捷方式不存在，跳过")
        except Exception as e:
            self.log(f"! 删除快捷方式失败: {e}")

    def _start_self_delete(self):
        """启动自删除批处理"""
        try:
            if getattr(sys, 'frozen', False):
                exe_path = Path(sys.executable)
            else:
                return  # 开发模式不自删除
            
            # 创建批处理文件
            bat_path = exe_path.parent / "_uninstall_cleanup.bat"
            with open(bat_path, 'w', encoding='utf-8') as f:
                f.write('@echo off\n')
                f.write('chcp 437 >nul 2>&1\n')
                f.write('timeout /t 2 /nobreak >nul\n')  # 等待2秒让exe退出
                f.write(f'del /f /q "{exe_path}"\n')  # 删除exe
                f.write(f'del /f /q "{bat_path}"\n')  # 删除自身
            
            # 启动批处理
            subprocess.Popen(
                ['cmd', '/c', str(bat_path)],
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        except Exception as e:
            print(f"自删除失败: {e}")

    def run(self):
        self.root.mainloop()


def main():
    wizard = UninstallWizard()
    wizard.run()


if __name__ == '__main__':
    main()
