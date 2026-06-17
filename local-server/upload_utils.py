#!/usr/bin/env python3
"""
上传工具模块 - 共享的 pyautogui 文件上传逻辑
server.py 和 tray_service.py 都从这里导入
"""

import os
import sys
import time
import logging
import platform

logger = logging.getLogger(__name__)

# ==================== 依赖检测 ====================

system = platform.system()
DEPENDENCIES_OK = False
PYAUTOGUI_AVAILABLE = False
DPI_SCALE = 1.0  # Windows DPI 缩放比例

try:
    import pyautogui
    import pyperclip
    PYAUTOGUI_AVAILABLE = True
    DEPENDENCIES_OK = True
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.05

    # 检测 Windows DPI 缩放
    if system == 'Windows':
        try:
            import ctypes
            # 获取系统 DPI 缩放比例
            ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-Monitor DPI Aware
            hdc = ctypes.windll.user32.GetDC(0)
            dpi_x = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX
            ctypes.windll.user32.ReleaseDC(0, hdc)
            DPI_SCALE = dpi_x / 96.0
            logger.info(f"Windows DPI 缩放: {DPI_SCALE:.2f}x (DPI: {dpi_x})")
        except Exception as e:
            logger.warning(f"DPI 检测失败: {e}，使用默认 1.0")
            DPI_SCALE = 1.0

    if system == 'Darwin':
        import subprocess
        try:
            import Quartz
            logger.info("macOS环境，使用Quartz进行窗口管理")
        except ImportError:
            logger.warning("Quartz不可用")
    elif system == 'Windows':
        import pygetwindow as gw
        import win32gui
        import win32con
        logger.info("Windows环境，使用win32gui进行窗口管理")
    else:
        logger.warning(f"未支持的操作系统: {system}")
        DEPENDENCIES_OK = False
except ImportError as e:
    logger.warning(f"依赖缺失: {e}")
    DEPENDENCIES_OK = False


# ==================== 浏览器窗口 ====================

def get_browser_window():
    """获取浏览器窗口"""
    if not DEPENDENCIES_OK:
        return None

    if system == 'Darwin':
        return _get_browser_window_macos()
    elif system == 'Windows':
        return _get_browser_window_windows()
    return None


def _get_browser_window_windows():
    """Windows上获取浏览器窗口"""
    try:
        windows = gw.getWindowsWithTitle('')
        browsers = ['Chrome', 'Edge', 'Firefox', 'Brave']
        for w in windows:
            if not w.title:
                continue
            for browser in browsers:
                if browser.lower() in w.title.lower():
                    return w
    except Exception as e:
        logger.error(f"获取浏览器窗口失败: {e}")
    return None


def _get_browser_window_macos():
    """macOS上获取浏览器窗口"""
    try:
        window_list = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
            Quartz.kCGNullWindowID
        )
        browsers = ['Google Chrome', 'Chrome', 'Microsoft Edge', 'Edge', 'Safari', 'Firefox']
        for window_info in window_list:
            window_name = window_info.get(Quartz.kCGWindowName, '') or ''
            owner_name = window_info.get(Quartz.kCGWindowOwnerName, '') or ''
            is_browser = any(b.lower() in owner_name.lower() or b.lower() in window_name.lower() for b in browsers)
            if not is_browser:
                continue
            bounds = window_info.get(Quartz.kCGWindowBounds, {})
            if not bounds:
                continue

            class MacOSWindow:
                def __init__(self, bounds, title):
                    self.left = int(bounds.get('X', 0))
                    self.top = int(bounds.get('Y', 0))
                    self.width = int(bounds.get('Width', 0))
                    self.height = int(bounds.get('Height', 0))
                    self.title = title
                    self.isMinimized = False
                def activate(self):
                    pass
                def restore(self):
                    pass

            return MacOSWindow(bounds, window_name)
    except Exception as e:
        logger.error(f"macOS获取浏览器窗口失败: {e}")
    return None


# ==================== 坐标计算 ====================

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
    browser_width = window.width
    browser_height = window.height

    # Windows 最大化时窗口边框会超出屏幕（如 -9, -9），需要修正
    visible_x = max(0, browser_x)
    visible_y = max(0, browser_y)

    # 浏览器视口坐标是 CSS 像素，需要乘以 DPI 缩放比例转为物理像素
    screen_x = visible_x + int(viewport_x * DPI_SCALE)
    screen_y = visible_y + int((viewport_y + nav_bar_height) * DPI_SCALE)

    logger.info(f"浏览器位置: ({browser_x}, {browser_y})")
    logger.info(f"可见区域: ({visible_x}, {visible_y})")
    logger.info(f"视口坐标: ({viewport_x}, {viewport_y})")
    logger.info(f"导航栏高度: {nav_bar_height}")
    logger.info(f"DPI缩放: {DPI_SCALE:.2f}x")
    logger.info(f"屏幕坐标: ({screen_x}, {screen_y})")

    return screen_x, screen_y


# ==================== 鼠标操作 ====================

def move_to_position(viewport_x, viewport_y, nav_bar_height=85, element_width=0, element_height=0):
    """移动鼠标到浏览器页面中的元素位置（不点击），用于预览确认"""
    if not DEPENDENCIES_OK:
        logger.error("pyautogui不可用")
        return False, None, None

    try:
        adjusted_x = viewport_x
        adjusted_y = viewport_y

        screen_x, screen_y = calculate_screen_position(adjusted_x, adjusted_y, nav_bar_height)

        if screen_x is None or screen_y is None:
            return False, None, None

        screen_width, screen_height = pyautogui.size()
        if screen_x < 0 or screen_x > screen_width or screen_y < 0 or screen_y > screen_height:
            logger.error(f"坐标超出屏幕范围: ({screen_x}, {screen_y})")
            return False, None, None

        logger.info(f"移动鼠标到屏幕坐标: ({screen_x}, {screen_y})")
        pyautogui.moveTo(screen_x, screen_y, duration=0.3)
        time.sleep(0.1)
        
        # 验证鼠标是否真的移动了
        actual_pos = pyautogui.position()
        logger.info(f"鼠标实际位置: ({actual_pos.x}, {actual_pos.y})")
        
        # 如果 pyautogui 没生效，用 ctypes 备用方案
        if abs(actual_pos.x - screen_x) > 5 or abs(actual_pos.y - screen_y) > 5:
            logger.warning("pyautogui.moveTo 未生效，尝试 ctypes 方案")
            try:
                import ctypes
                ctypes.windll.user32.SetCursorPos(int(screen_x), int(screen_y))
                time.sleep(0.1)
                actual_pos = pyautogui.position()
                logger.info(f"ctypes 鼠标位置: ({actual_pos.x}, {actual_pos.y})")
            except Exception as e:
                logger.error(f"ctypes 移动失败: {e}")
        
        return True, screen_x, screen_y

    except Exception as e:
        logger.error(f"移动鼠标失败: {e}")
        return False, None, None


def click_at_position(viewport_x, viewport_y, nav_bar_height=85, element_width=0, element_height=0):
    """点击浏览器页面中的元素，基于元素尺寸做随机偏移"""
    if not DEPENDENCIES_OK:
        logger.error("pyautogui不可用")
        return False, None, None

    try:
        import random

        offset_x = 0
        offset_y = 0
        if element_width > 0 and element_height > 0:
            margin = 2
            range_x = max(0, element_width / 2 - margin)
            range_y = max(0, element_height / 2 - margin)
            offset_x = random.uniform(0, range_x)
            offset_y = random.uniform(-range_y, 0)

        adjusted_x = viewport_x + offset_x
        adjusted_y = viewport_y + offset_y

        screen_x, screen_y = calculate_screen_position(adjusted_x, adjusted_y, nav_bar_height)

        if screen_x is None or screen_y is None:
            return False, None, None

        screen_width, screen_height = pyautogui.size()
        if screen_x < 0 or screen_x > screen_width or screen_y < 0 or screen_y > screen_height:
            logger.error(f"坐标超出屏幕范围: ({screen_x}, {screen_y})")
            return False, screen_x, screen_y

        logger.info(f"点击屏幕坐标: ({screen_x}, {screen_y})")
        pyautogui.moveTo(screen_x, screen_y, duration=0.05)
        time.sleep(0.02)
        
        # 验证鼠标位置，如果没生效用 ctypes
        actual_pos = pyautogui.position()
        if abs(actual_pos.x - screen_x) > 5 or abs(actual_pos.y - screen_y) > 5:
            logger.warning("pyautogui 未生效，使用 ctypes 点击")
            try:
                import ctypes
                ctypes.windll.user32.SetCursorPos(int(screen_x), int(screen_y))
                time.sleep(0.02)
                # ctypes 鼠标点击
                ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)  # LEFTDOWN
                ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)  # LEFTUP
            except Exception as e:
                logger.error(f"ctypes 点击失败: {e}")
                pyautogui.click(screen_x, screen_y)
        else:
            pyautogui.click(screen_x, screen_y)
        
        time.sleep(0.1)
        return True, screen_x, screen_y

    except Exception as e:
        logger.error(f"点击失败: {e}")
        return False, None, None


# ==================== 对话框检测 ====================

def find_file_dialog(target_title='打开'):
    """查找文件对话框"""
    if not DEPENDENCIES_OK:
        logger.error("find_file_dialog: DEPENDENCIES_OK=False")
        return None

    if system == 'Darwin':
        return _find_file_dialog_macos(target_title)
    elif system == 'Windows':
        return _find_file_dialog_windows(target_title)
    return None


def _find_file_dialog_windows(target_title='打开'):
    """Windows上查找文件对话框"""
    result = []
    all_windows = []

    def callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            class_name = win32gui.GetClassName(hwnd)

            all_windows.append({
                'hwnd': hwnd,
                'title': title,
                'class': class_name
            })

            if class_name == '#32770' or any(kw in title for kw in ['打开', 'Open', '选择', 'Choose']):
                result.append({
                    'hwnd': hwnd,
                    'title': title,
                    'exact_match': title == target_title
                })

    try:
        win32gui.EnumWindows(callback, None)
    except Exception as e:
        logger.error(f"EnumWindows 异常: {e}")

    logger.info(f"[窗口检测] 目标标题: '{target_title}'")
    logger.info(f"[窗口检测] 扫描到 {len(all_windows)} 个可见窗口")

    if all_windows:
        logger.info("[窗口检测] 所有可见窗口:")
        for w in all_windows[:20]:
            logger.info(f"  - hwnd={w['hwnd']}, title='{w['title']}', class='{w['class']}'")

    logger.info(f"[窗口检测] 匹配到 {len(result)} 个候选对话框")

    if result:
        for r in result:
            logger.info(f"  - hwnd={r['hwnd']}, title='{r['title']}', exact={r['exact_match']}")

    exact = [d for d in result if d['exact_match']]
    if exact:
        logger.info(f"[窗口检测] 精确匹配: '{exact[0]['title']}'")
        return exact[0]

    partial = [d for d in result if target_title in d['title']]
    if partial:
        logger.info(f"[窗口检测] 部分匹配: '{partial[0]['title']}'")
        return partial[0]

    if result:
        logger.info(f"[窗口检测] 使用第一个候选: '{result[0]['title']}'")
        return result[0]

    logger.warning("[窗口检测] 未找到任何匹配的对话框窗口")
    return None


def _find_file_dialog_macos(target_title='打开'):
    """macOS上查找文件对话框"""
    try:
        window_list = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
            Quartz.kCGNullWindowID
        )

        all_windows = []
        for window_info in window_list:
            window_name = window_info.get(Quartz.kCGWindowName, '') or ''
            owner_name = window_info.get(Quartz.kCGWindowOwnerName, '') or ''
            window_id = window_info.get(Quartz.kCGWindowNumber, 0)
            layer = window_info.get(Quartz.kCGWindowLayer, 0)
            all_windows.append({
                'id': window_id,
                'title': window_name,
                'owner': owner_name,
                'layer': layer
            })

        logger.info(f"[macOS窗口检测] 扫描到 {len(all_windows)} 个可见窗口")

        browsers = ['Google Chrome', 'Chrome', 'Safari', 'Firefox', 'Microsoft Edge']
        for window_info in all_windows:
            owner = window_info['owner']
            title = window_info['title']
            layer = window_info['layer']

            is_browser = any(b.lower() in owner.lower() for b in browsers)
            if not is_browser:
                continue

            if layer > 0 and (not title or 'dialog' in title.lower() or 'open' in title.lower()):
                logger.info(f"[macOS窗口检测] 找到可能的文件对话框: owner='{owner}', title='{title}', layer={layer}")
                return window_info

        logger.info("[macOS窗口检测] 未找到文件对话框")
        return None

    except Exception as e:
        logger.error(f"macOS窗口检测失败: {e}")
        return None


def wait_for_file_dialog(target_title='打开', timeout=5.0, interval=0.2):
    """轮询等待文件对话框出现"""
    logger.info(f"[轮询] 等待对话框: '{target_title}', 超时: {timeout}s")
    deadline = time.time() + timeout
    while time.time() < deadline:
        dialog = find_file_dialog(target_title)
        if dialog:
            elapsed = timeout - (deadline - time.time())
            logger.info(f"[轮询] 对话框已出现，耗时: {elapsed:.1f}s")
            return dialog
        time.sleep(interval)
    logger.warning(f"[轮询] 等待超时 {timeout}s，对话框未出现")
    return None


def wait_for_window_focus(hwnd, timeout=2.0, interval=0.1):
    """轮询等待窗口获得焦点"""
    if system == 'Darwin':
        time.sleep(timeout)
        return True
    elif system == 'Windows':
        deadline = time.time() + timeout
        while time.time() < deadline:
            if win32gui.GetForegroundWindow() == hwnd:
                return True
            time.sleep(interval)
        return False
    return False


def focus_window(hwnd):
    """聚焦窗口"""
    if system == 'Darwin':
        return _focus_window_macos(hwnd)
    elif system == 'Windows':
        return _focus_window_windows(hwnd)
    return False


def _focus_window_macos(window_info):
    """macOS上聚焦窗口"""
    try:
        owner_name = window_info.get('owner', '')
        if not owner_name:
            logger.warning("无法获取窗口所有者名称")
            return False
        script = f'''
        tell application "System Events"
            set frontmost of process "{owner_name}" to true
        end tell
        '''
        result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
        if result.returncode == 0:
            logger.info(f"macOS聚焦窗口成功: {owner_name}")
            return True
        else:
            logger.warning(f"macOS聚焦窗口失败: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"macOS聚焦窗口异常: {e}")
        return False


def _focus_window_windows(hwnd):
    """Windows上聚焦窗口"""
    try:
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

        try:
            shell = __import__('win32com.client').Dispatch("WScript.Shell")
            shell.SendKeys('%')
        except:
            pass

        win32gui.SetForegroundWindow(hwnd)
        if wait_for_window_focus(hwnd, timeout=1.0):
            return True
        logger.warning("聚焦窗口超时")
        return True
    except Exception as e:
        logger.warning(f"聚焦窗口失败: {e}")
        return False


# ==================== 文件选择 ====================

def select_file_in_dialog(file_path):
    """在文件对话框中选择文件"""
    if not DEPENDENCIES_OK:
        logger.error("pyautogui不可用")
        return False

    file_path = os.path.abspath(file_path)

    if not os.path.exists(file_path):
        logger.error(f"文件不存在: {file_path}")
        return False

    try:
        try:
            original_clipboard = pyperclip.paste()
        except:
            original_clipboard = ''

        pyperclip.copy(file_path)
        time.sleep(0.05)

        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.02)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.05)

        pyautogui.press('enter')
        time.sleep(0.1)

        try:
            pyperclip.copy(original_clipboard)
        except:
            pass

        logger.info("[文件选择] 文件选择完成")
        return True

    except Exception as e:
        logger.error(f"[文件选择] 操作失败: {e}")
        return False


# ==================== 文件上传主流程 ====================

def upload_file_with_retry(file_path, button_x, button_y, nav_bar_height,
                           button_width, button_height, max_retries=3, preview_only=False,
                           hover_check_fn=None):
    """
    文件上传流程：
    1. 直接点击上传按钮（跳过移动鼠标预览）
    2. 等待对话框出现后选择文件

    参数:
        hover_check_fn: WebSocket hover 检测函数（暂不使用）
    """
    if not DEPENDENCIES_OK:
        logger.error("pyautogui不可用")
        return False

    file_path = os.path.abspath(file_path)
    if not os.path.exists(file_path):
        logger.error(f"文件不存在: {file_path}")
        return False

    # 按钮坐标检查
    if button_x is None or button_y is None:
        logger.warning("[上传] 按钮坐标为空，跳过点击")
        return False

    timing = {}
    t_start = time.time()

    # 直接点击上传按钮（跳过移动鼠标步骤）
    logger.info(f"[上传] 直接点击按钮 ({button_x}, {button_y})")
    t_click_start = time.time()
    success, _, _ = click_at_position(button_x, button_y, nav_bar_height, button_width, button_height)
    timing['click_button'] = round(time.time() - t_click_start, 3)

    if not success:
        logger.warning("[上传] 点击按钮失败")
        return False

    # 等待对话框出现
    t_dialog_start = time.time()
    dialog = wait_for_file_dialog(target_title='打开', timeout=3.0, interval=0.2)
    timing['wait_dialog'] = round(time.time() - t_dialog_start, 3)

    if not dialog:
        logger.warning("[上传] 对话框未出现，终止上传")
        return False

    hwnd = dialog.get('hwnd') if isinstance(dialog, dict) else None
    title = dialog.get('title', '') if isinstance(dialog, dict) else ''
    logger.info(f"[上传] 找到对话框: '{title}'")
    if hwnd:
        focus_window(hwnd)
        time.sleep(0.05)

    # 选择文件
    t_select_start = time.time()
    success = select_file_in_dialog(file_path)
    timing['select_file'] = round(time.time() - t_select_start, 3)

    timing['total'] = round(time.time() - t_start, 3)

    if success:
        logger.info(f"[上传] 文件上传成功 | 耗时: {timing}")
        return True

    logger.warning(f"[上传] 文件选择失败 | 耗时: {timing}")
    return False
