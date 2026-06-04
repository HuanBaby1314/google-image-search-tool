#!/usr/bin/env python3
"""
Google Image Search Tool - 系统托盘服务
"""

import os
import sys
import json
import time
import logging
import threading
import glob
from pathlib import Path
from datetime import datetime, timedelta

# ==================== 日志配置 ====================

log_dir = Path.home() / "Downloads" / "qingqing_helper_dir"
log_dir.mkdir(parents=True, exist_ok=True)

# 常规日志 - 保留15天
app_log_file = log_dir / "service.log"

# 心跳日志 - 只保留当天
heartbeat_log_file = log_dir / "heartbeat.log"

# 配置常规日志
app_logger = logging.getLogger('app')
app_logger.setLevel(logging.INFO)

app_handler = logging.FileHandler(app_log_file, encoding='utf-8')
app_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
app_logger.addHandler(app_handler)

# 配置控制台输出
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
app_logger.addHandler(console_handler)

# 配置心跳日志
heartbeat_logger = logging.getLogger('heartbeat')
heartbeat_logger.setLevel(logging.INFO)

heartbeat_handler = logging.FileHandler(heartbeat_log_file, encoding='utf-8')
heartbeat_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
heartbeat_logger.addHandler(heartbeat_handler)

logger = app_logger


# ==================== 日志清理 ====================

def cleanup_logs():
    """清理历史日志"""
    today = datetime.now().strftime('%Y%m%d')
    
    # 1. 清理心跳日志 - 只保留当天
    # 心跳日志每天重新创建
    if heartbeat_log_file.exists():
        # 检查文件修改时间
        mtime = datetime.fromtimestamp(heartbeat_log_file.stat().st_mtime)
        if mtime.strftime('%Y%m%d') != today:
            # 清空文件
            with open(heartbeat_log_file, 'w', encoding='utf-8') as f:
                f.write('')
            logger.info("心跳日志已清理")
    
    # 2. 清理常规日志 - 保留15天
    try:
        cutoff_date = datetime.now() - timedelta(days=15)
        
        # 查找所有日志文件
        log_files = glob.glob(str(log_dir / "service*.log"))
        log_files += glob.glob(str(log_dir / "service*.log.*"))
        
        for log_file in log_files:
            file_path = Path(log_file)
            if file_path.exists():
                mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                if mtime < cutoff_date:
                    file_path.unlink()
                    logger.info(f"删除旧日志: {file_path.name}")
    except Exception as e:
        logger.error(f"清理日志失败: {e}")


def schedule_log_cleanup():
    """定时清理日志（每天执行一次）"""
    while True:
        try:
            cleanup_logs()
        except Exception as e:
            print(f"日志清理错误: {e}")
        
        # 每小时检查一次
        time.sleep(3600)


# ==================== 依赖检查 ====================

DEPENDENCIES_OK = True
MISSING_DEPS = []

try:
    import pystray
except ImportError:
    MISSING_DEPS.append('pystray')
    DEPENDENCIES_OK = False

try:
    from PIL import Image, ImageDraw
except ImportError:
    MISSING_DEPS.append('Pillow')
    DEPENDENCIES_OK = False

try:
    from flask import Flask, request, jsonify
    from flask_cors import CORS
except ImportError:
    MISSING_DEPS.append('flask/flask-cors')
    DEPENDENCIES_OK = False

try:
    import pyautogui
    import pyperclip
except ImportError:
    MISSING_DEPS.append('pyautogui/pyperclip')
    DEPENDENCIES_OK = False

try:
    import win32gui
    import win32con
    import winreg
except ImportError:
    MISSING_DEPS.append('pywin32')
    DEPENDENCIES_OK = False


# ==================== Flask应用 ====================

app = Flask(__name__)
CORS(app)

# 全局状态
server_running = False
server_port = 5000
tray_icon = None
autostart_enabled = False


# ==================== 开机自启 ====================

AUTOSTART_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "Google搜图服务"


def get_exe_path():
    """获取当前exe路径"""
    if getattr(sys, 'frozen', False):
        return sys.executable
    return os.path.abspath(__file__)


def is_autostart_enabled():
    """检查是否已设置开机自启"""
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
    """设置开机自启"""
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

def get_base_dir():
    return Path.home() / "Downloads"


def get_today_dir():
    return datetime.now().strftime('%Y%m%d')


def get_work_dir():
    base = get_base_dir()
    today = get_today_dir()
    work_dir = base / "qingqing_helper_dir" / today
    work_dir.mkdir(parents=True, exist_ok=True)
    return work_dir


def find_file(filename):
    """
    查找文件，支持扩展名映射
    例如: AA24MRKe.img -> 查找 AA24MRKe.jpg, AA24MRKe.png 等
    """
    base = get_base_dir()
    work_dir = get_work_dir()
    
    # 获取文件名和扩展名
    name_stem = Path(filename).stem  # 不含扩展名的文件名
    name_ext = Path(filename).suffix  # 扩展名
    
    # 可能的图片扩展名
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
    
    # 如果原始扩展名是图片格式，也加入查找列表
    if name_ext.lower() in image_extensions:
        search_extensions = [name_ext] + [ext for ext in image_extensions if ext != name_ext]
    else:
        # 如果是.img等非标准扩展名，查找所有图片格式
        search_extensions = image_extensions
    
    # 搜索路径列表
    search_dirs = [
        work_dir,
        base / "qingqing_helper_dir",
        base
    ]
    
    # 也搜索历史日期目录
    helper_dir = base / "qingqing_helper_dir"
    if helper_dir.exists():
        for date_dir in sorted(helper_dir.iterdir(), reverse=True):
            if date_dir.is_dir() and date_dir.name != "local" and date_dir != work_dir:
                search_dirs.append(date_dir)
    
    # 1. 先查找原始文件名
    for search_dir in search_dirs:
        if search_dir.exists():
            target = search_dir / filename
            if target.exists():
                logger.info(f"找到原始文件: {target}")
                return str(target)
    
    # 2. 查找同名不同扩展名的文件
    for search_dir in search_dirs:
        if search_dir.exists():
            for ext in search_extensions:
                target = search_dir / (name_stem + ext)
                if target.exists():
                    logger.info(f"找到映射文件: {target} (原始: {filename})")
                    return str(target)
    
    # 3. 模糊匹配（文件名包含搜索词）
    for search_dir in search_dirs:
        if search_dir.exists():
            for f in search_dir.iterdir():
                if f.is_file() and name_stem in f.stem:
                    if f.suffix.lower() in image_extensions:
                        logger.info(f"找到模糊匹配: {f} (原始: {filename})")
                        return str(f)
    
    return None


def get_browser_window():
    """获取浏览器窗口"""
    if not DEPENDENCIES_OK:
        return None
    
    try:
        import pygetwindow as gw
    except ImportError:
        logger.warning("pygetwindow不可用")
        return None
    
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
    
    # 使用动态计算的导航栏高度
    screen_x = browser_x + viewport_x
    screen_y = browser_y + viewport_y + nav_bar_height
    
    logger.info(f"浏览器位置: ({browser_x}, {browser_y})")
    logger.info(f"视口坐标: ({viewport_x}, {viewport_y})")
    logger.info(f"导航栏高度: {nav_bar_height} (动态计算)")
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
    if not DEPENDENCIES_OK:
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


@app.route('/api/get-download-dir', methods=['GET'])
def get_download_dir():
    return jsonify({'download_dir': str(get_work_dir())})


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

    # 查找文件（支持扩展名映射）
    full_path = find_file(filename)
    
    if not full_path:
        return jsonify({'success': False, 'error': f'文件不存在: {filename}'})

    logger.info(f"找到文件: {full_path}")

    try:
        # 1. 点击按钮打开文件对话框
        if button_x is not None and button_y is not None:
            if not click_at_position(button_x, button_y, nav_bar_height):
                return jsonify({'success': False, 'error': '点击按钮失败'})
            
            time.sleep(1.5)
        
        # 2. 在文件对话框中选择文件
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
            thread = threading.Thread(target=process_upload, args=(filename,))
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
    """创建托盘图标"""
    width = 64
    height = 64
    image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    # 绘制圆形背景
    draw.ellipse([4, 4, width-4, height-4], fill=color)
    
    # 绘制放大镜图标
    draw.ellipse([14, 14, 38, 38], outline='white', width=3)
    draw.line([35, 35, 50, 50], fill='white', width=3)
    
    return image


def update_tray_icon(status='running'):
    """更新托盘图标状态"""
    global tray_icon
    
    if tray_icon is None:
        return
    
    if status == 'running':
        icon_image = create_icon_image('#4caf50')
        title = 'Google搜图服务 - 运行中'
    elif status == 'error':
        icon_image = create_icon_image('#f44336')
        title = 'Google搜图服务 - 错误'
    else:
        icon_image = create_icon_image('#9e9e9e')
        title = 'Google搜图服务 - 已停止'
    
    try:
        tray_icon.icon = icon_image
        tray_icon.title = title
    except:
        pass


def on_toggle_autostart(icon, item):
    """切换开机自启"""
    global autostart_enabled
    
    autostart_enabled = not autostart_enabled
    set_autostart(autostart_enabled)
    
    # 更新菜单显示
    item.checked = autostart_enabled


def on_open_log(icon, item):
    """打开日志文件"""
    if app_log_file.exists():
        os.startfile(str(app_log_file))


def on_open_heartbeat_log(icon, item):
    """打开心跳日志"""
    if heartbeat_log_file.exists():
        os.startfile(str(heartbeat_log_file))


def on_open_folder(icon, item):
    """打开工作目录"""
    work_dir = get_work_dir()
    os.startfile(str(work_dir))


def on_restart(icon, item):
    """重启服务"""
    global server_running
    
    logger.info("重启服务...")
    server_running = False
    
    time.sleep(1)
    start_flask_server()
    server_running = True
    update_tray_icon('running')


def on_exit(icon, item):
    """退出程序"""
    global server_running
    
    logger.info("退出服务...")
    server_running = False
    
    try:
        icon.stop()
    except:
        pass
    
    sys.exit(0)


def start_flask_server():
    """启动Flask服务器"""
    global server_running
    
    def run_server():
        try:
            logger.info(f"启动服务器 http://localhost:{server_port}")
            app.run(host='0.0.0.0', port=server_port, debug=False, use_reloader=False)
        except Exception as e:
            logger.error(f"服务器错误: {e}")
            update_tray_icon('error')
    
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    server_running = True


def create_tray_icon():
    """创建系统托盘图标"""
    global tray_icon, autostart_enabled
    
    # 检查开机自启状态
    autostart_enabled = is_autostart_enabled()
    
    # 创建菜单
    menu = pystray.Menu(
        pystray.MenuItem('开机自启', on_toggle_autostart, checked=lambda item: autostart_enabled),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('打开应用日志', on_open_log),
        pystray.MenuItem('打开心跳日志', on_open_heartbeat_log),
        pystray.MenuItem('打开目录', on_open_folder),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('重启服务', on_restart),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('退出', on_exit)
    )
    
    # 创建图标
    icon_image = create_icon_image('#4caf50')
    
    tray_icon = pystray.Icon(
        name='Google搜图服务',
        icon=icon_image,
        title='Google搜图服务 - 启动中...',
        menu=menu
    )
    
    return tray_icon


def main():
    """主函数"""
    global server_port
    
    # 检查依赖
    if not DEPENDENCIES_OK:
        msg = f"错误: 缺少依赖: {', '.join(MISSING_DEPS)}"
        print(msg)
        print("请运行: pip install pystray Pillow flask flask-cors pyautogui pyperclip pywin32")
        
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, msg + "\n\n请安装缺少的依赖后重试", "Google搜图服务 - 错误", 0x10)
        except:
            input("按回车键退出...")
        
        sys.exit(1)
    
    logger.info("=" * 50)
    logger.info("Google搜图服务 - 系统托盘版")
    logger.info("=" * 50)
    logger.info(f"工作目录: {get_work_dir()}")
    logger.info(f"服务端口: {server_port}")
    logger.info(f"开机自启: {'已启用' if autostart_enabled else '已禁用'}")
    logger.info("=" * 50)
    
    # 清理历史日志
    cleanup_logs()
    
    # 启动日志清理线程
    cleanup_thread = threading.Thread(target=schedule_log_cleanup, daemon=True)
    cleanup_thread.start()
    
    # 启动Flask服务
    start_flask_server()
    
    # 更新图标状态
    update_tray_icon('running')
    
    # 创建并运行托盘图标
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