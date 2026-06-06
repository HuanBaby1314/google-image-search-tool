#!/usr/bin/env python3
"""
本地服务器 - 处理Chrome扩展的请求
"""

import os
import sys
import json
import time
import logging
import shutil
from pathlib import Path
from datetime import datetime
from threading import Thread

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_sock import Sock

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)
sock = Sock(app)

# WebSocket 客户端管理
ws_clients = set()
ws_pending_click = {}  # 待确认的点击请求

# 导入依赖
import platform
system = platform.system()

try:
    import pyautogui
    import pyperclip
    PYAUTOGUI_AVAILABLE = True
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.05
    
    if system == 'Darwin':  # macOS
        import subprocess
        import Quartz
        logger.info("macOS环境，使用Quartz进行窗口管理")
    elif system == 'Windows':
        import pygetwindow as gw
        import win32gui
        import win32con
        logger.info("Windows环境，使用win32gui进行窗口管理")
    else:
        logger.warning(f"未支持的操作系统: {system}")
        PYAUTOGUI_AVAILABLE = False
except ImportError as e:
    logger.warning(f"依赖缺失: {e}")
    PYAUTOGUI_AVAILABLE = False


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


def get_images_dir():
    """获取图片存储目录（用于静态服务）"""
    images_dir = Path(__file__).parent / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    return images_dir


def find_file(filename):
    """查找文件，支持扩展名映射"""
    base = get_base_dir()
    work_dir = get_work_dir()
    
    name_stem = Path(filename).stem
    name_ext = Path(filename).suffix
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
    
    if name_ext.lower() in image_extensions:
        search_extensions = [name_ext] + [ext for ext in image_extensions if ext != name_ext]
    else:
        search_extensions = image_extensions
    
    search_dirs = [work_dir, base / "qingqing_helper_dir", base]
    
    helper_dir = base / "qingqing_helper_dir"
    if helper_dir.exists():
        for date_dir in sorted(helper_dir.iterdir(), reverse=True):
            if date_dir.is_dir() and date_dir.name != "local" and date_dir != work_dir:
                search_dirs.append(date_dir)
    
    # 1. 原始文件名
    for search_dir in search_dirs:
        if search_dir.exists():
            target = search_dir / filename
            if target.exists():
                logger.info(f"找到原始文件: {target}")
                return str(target)
    
    # 2. 扩展名映射
    for search_dir in search_dirs:
        if search_dir.exists():
            for ext in search_extensions:
                target = search_dir / (name_stem + ext)
                if target.exists():
                    logger.info(f"找到映射文件: {target} (原始: {filename})")
                    return str(target)
    
    # 3. 模糊匹配
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
    if not PYAUTOGUI_AVAILABLE:
        return None
    
    if system == 'Darwin':  # macOS
        return get_browser_window_macos()
    elif system == 'Windows':
        return get_browser_window_windows()
    return None

def get_browser_window_macos():
    """macOS上获取浏览器窗口"""
    try:
        # 使用Quartz获取窗口列表
        window_list = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
            Quartz.kCGNullWindowID
        )
        
        browsers = ['Google Chrome', 'Chrome', 'Microsoft Edge', 'Edge', 'Safari', 'Firefox']
        
        for window_info in window_list:
            window_name = window_info.get(Quartz.kCGWindowName, '')
            owner_name = window_info.get(Quartz.kCGWindowOwnerName, '')
            
            # 检查是否是浏览器窗口
            is_browser = False
            for browser in browsers:
                if browser.lower() in owner_name.lower() or browser.lower() in window_name.lower():
                    is_browser = True
                    break
            
            if not is_browser:
                continue
            
            # 获取窗口位置和大小
            bounds = window_info.get(Quartz.kCGWindowBounds, {})
            if not bounds:
                continue
            
            # 创建一个类似pygetwindow的窗口对象
            class MacOSWindow:
                def __init__(self, title, left, top, width, height):
                    self.title = title
                    self.left = left
                    self.top = top
                    self.width = width
                    self.height = height
                    self.isMinimized = False
                    self.isActive = True
                
                def activate(self):
                    # 使用osascript激活窗口
                    script = f'''
                    tell application "System Events"
                        set frontmost of process "{owner_name}" to true
                    end tell
                    '''
                    subprocess.run(['osascript', '-e', script], capture_output=True)
                
                def restore(self):
                    if self.isMinimized:
                        self.activate()
                        self.isMinimized = False
            
            window = MacOSWindow(
                title=window_name or owner_name,
                left=bounds.get('X', 0),
                top=bounds.get('Y', 0),
                width=bounds.get('Width', 0),
                height=bounds.get('Height', 0)
            )
            
            logger.info(f"找到macOS浏览器窗口: {window.title}")
            return window
        
        logger.warning("未找到浏览器窗口")
        return None
        
    except Exception as e:
        logger.error(f"macOS获取窗口失败: {e}")
        return None

def get_browser_window_windows():
    """Windows上获取浏览器窗口"""
    browsers = ['Chrome', 'Edge', 'Google Chrome', 'Microsoft Edge']
    
    for browser_name in browsers:
        try:
            windows = gw.getWindowsWithTitle(browser_name)
            if windows:
                # 返回第一个非最小化的窗口，或第一个窗口
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
    browser_width = window.width
    browser_height = window.height
    
    # 使用动态计算的导航栏高度
    screen_x = browser_x + viewport_x
    screen_y = browser_y + viewport_y + nav_bar_height
    
    # 详细日志输出
    logger.info("=" * 50)
    logger.info("[坐标计算详情]")
    logger.info(f"  浏览器窗口位置: ({browser_x}, {browser_y})")
    logger.info(f"  浏览器窗口大小: {browser_width} x {browser_height}")
    logger.info(f"  视口坐标 (来自扩展): ({viewport_x}, {viewport_y})")
    logger.info(f"  导航栏高度: {nav_bar_height}")
    logger.info(f"  计算公式: screen_x = {browser_x} + {viewport_x} = {screen_x}")
    logger.info(f"  计算公式: screen_y = {browser_y} + {viewport_y} + {nav_bar_height} = {screen_y}")
    logger.info(f"  最终屏幕坐标: ({screen_x}, {screen_y})")
    
    # 检查坐标是否在窗口范围内
    if screen_x < browser_x or screen_x > browser_x + browser_width:
        logger.warning(f"  ⚠ X坐标超出浏览器窗口范围!")
    if screen_y < browser_y or screen_y > browser_y + browser_height:
        logger.warning(f"  ⚠ Y坐标超出浏览器窗口范围!")
    
    # 获取当前鼠标位置作为参考
    current_pos = pyautogui.position()
    logger.info(f"  当前鼠标位置: ({current_pos.x}, {current_pos.y})")
    logger.info("=" * 50)
    
    return screen_x, screen_y


def click_at_position(viewport_x, viewport_y, nav_bar_height=85, element_width=0, element_height=0):
    """点击浏览器页面中的元素，基于元素尺寸做随机偏移"""
    if not PYAUTOGUI_AVAILABLE:
        logger.error("pyautogui不可用")
        return False
    
    try:
        import random
        
        # 基于元素尺寸计算随机偏移（排除边界2像素，偏向右上方）
        offset_x = 0
        offset_y = 0
        if element_width > 0 and element_height > 0:
            margin = 2  # 排除边界像素
            range_x = max(0, element_width / 2 - margin)
            range_y = max(0, element_height / 2 - margin)
            # 偏向右方：[0, range_x] 范围
            offset_x = random.uniform(0, range_x)
            # 偏向上方：[-range_y, 0] 范围（Y轴向上为负）
            offset_y = random.uniform(-range_y, 0)
        
        adjusted_x = viewport_x + offset_x
        adjusted_y = viewport_y + offset_y
        
        screen_x, screen_y = calculate_screen_position(adjusted_x, adjusted_y, nav_bar_height)
        
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


def move_to_position(viewport_x, viewport_y, nav_bar_height=85, element_width=0, element_height=0):
    """移动鼠标到浏览器页面中的元素位置（不点击），用于预览确认"""
    if not PYAUTOGUI_AVAILABLE:
        logger.error("pyautogui不可用")
        return False, None, None
    
    try:
        # 计算元素中心位置（不做随机偏移，方便用户确认）
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
        pyautogui.moveTo(screen_x, screen_y, duration=0.3)  # 平滑移动
        return True, screen_x, screen_y
        
    except Exception as e:
        logger.error(f"移动鼠标失败: {e}")
        return False, None, None


def find_file_dialog(target_title='打开'):
    """查找文件对话框"""
    if not PYAUTOGUI_AVAILABLE:
        logger.error("find_file_dialog: PYAUTOGUI_AVAILABLE=False")
        return None
    
    if system == 'Darwin':  # macOS
        return find_file_dialog_macos(target_title)
    elif system == 'Windows':
        return find_file_dialog_windows(target_title)
    return None

def find_file_dialog_macos(target_title='打开'):
    """
    macOS上查找文件对话框
    macOS的文件对话框是系统原生的，通常没有明确的窗口标题
    我们通过检测是否有文件对话框类型的窗口来判断
    """
    try:
        # 使用Quartz获取窗口列表
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
        
        # 输出日志
        logger.info(f"[macOS窗口检测] 扫描到 {len(all_windows)} 个可见窗口")
        
        # 检测策略：
        # 1. 查找Chrome/Safari/Firefox的文件对话框
        # 2. macOS文件对话框通常是模态窗口，layer > 0
        
        browsers = ['Google Chrome', 'Chrome', 'Safari', 'Firefox', 'Microsoft Edge']
        
        for window_info in all_windows:
            owner = window_info['owner']
            title = window_info['title']
            layer = window_info['layer']
            
            # 检查是否是浏览器进程的窗口
            is_browser = any(b.lower() in owner.lower() for b in browsers)
            if not is_browser:
                continue
            
            # macOS文件对话框特征：
            # 1. 属于浏览器进程
            # 2. 通常有较高的layer值（模态窗口）
            # 3. 标题可能包含特定关键词或者是空的（系统对话框）
            
            # 检测文件对话框的特征
            dialog_keywords = ['打开', 'Open', '选择', 'Choose', '选取', 'Select', 
                              '上传', 'Upload', '浏览', 'Browse']
            
            has_dialog_keyword = any(kw.lower() in title.lower() for kw in dialog_keywords)
            is_modal = layer > 0  # 模态窗口通常layer > 0
            
            # 如果标题包含对话框关键词，或者是一个模态窗口（可能是无标题的文件对话框）
            if has_dialog_keyword or (is_modal and not title):
                logger.info(f"[macOS窗口检测] 找到可能的文件对话框: owner='{owner}', title='{title}', layer={layer}")
                return {
                    'id': window_info['id'],
                    'title': title or '文件对话框',
                    'owner': owner,
                    'is_macos_dialog': True
                }
        
        logger.info("[macOS窗口检测] 未找到文件对话框")
        return None
        
    except Exception as e:
        logger.error(f"macOS查找对话框失败: {e}")
        return None

def find_file_dialog_windows(target_title='打开'):
    """Windows上查找文件对话框"""
    result = []
    all_windows = []
    
    def callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            class_name = win32gui.GetClassName(hwnd)
            
            # 记录所有可见窗口
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
    
    # 输出日志
    logger.info(f"[窗口检测] 目标标题: '{target_title}'")
    logger.info(f"[窗口检测] 扫描到 {len(all_windows)} 个可见窗口")
    
    if all_windows:
        logger.info("[窗口检测] 所有可见窗口:")
        for w in all_windows[:20]:  # 最多显示20个
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
    if system == 'Darwin':  # macOS
        # macOS上无法直接检查窗口焦点，简单等待
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
    if system == 'Darwin':  # macOS
        return focus_window_macos(hwnd)
    elif system == 'Windows':
        return focus_window_windows(hwnd)
    return False

def focus_window_macos(window_info):
    """macOS上聚焦窗口"""
    try:
        # 使用osascript聚焦窗口
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

def focus_window_windows(hwnd):
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
        # 轮询等待窗口获得焦点
        if wait_for_window_focus(hwnd, timeout=1.0):
            return True
        logger.warning("聚焦窗口超时")
        return True  # 仍然返回 True，继续尝试操作
    except Exception as e:
        logger.warning(f"聚焦窗口失败: {e}")
        return False


def select_file_in_dialog(file_path):
    """
    在文件对话框中选择文件（假设对话框已打开）
    macOS: 使用 Cmd+Shift+G 打开"前往文件夹"对话框，输入路径
    Windows: 直接在地址栏输入路径
    """
    if not PYAUTOGUI_AVAILABLE:
        logger.error("pyautogui不可用")
        return False

    file_path = os.path.abspath(file_path)
    
    if not os.path.exists(file_path):
        logger.error(f"文件不存在: {file_path}")
        return False

    try:
        if system == 'Darwin':
            return select_file_in_dialog_macos(file_path)
        else:
            return select_file_in_dialog_windows(file_path)
    except Exception as e:
        logger.error(f"操作失败: {e}")
        return False


def select_file_in_dialog_macos(file_path):
    """
    macOS上在文件对话框中选择文件
    方法：使用 Cmd+Shift+G 打开"前往文件夹"对话框，输入文件完整路径，回车打开
    """
    try:
        logger.info(f"[macOS文件选择] 开始选择文件: {file_path}")
        
        # 保存原始剪贴板内容
        try:
            original_clipboard = pyperclip.paste()
        except:
            original_clipboard = ''
        
        # 使用 Cmd+Shift+G 打开"前往文件夹"对话框
        logger.info("[macOS文件选择] Step 1: 打开前往文件夹对话框")
        time.sleep(0.3)
        pyautogui.hotkey('command', 'shift', 'g')
        time.sleep(0.8)  # 等待对话框出现
        
        # 输入完整文件路径
        logger.info("[macOS文件选择] Step 2: 输入文件路径")
        pyperclip.copy(file_path)
        time.sleep(0.1)
        pyautogui.hotkey('command', 'a')
        time.sleep(0.05)
        pyautogui.hotkey('command', 'v')
        time.sleep(0.3)
        
        # 第一次回车 - 关闭"前往文件夹"对话框并选中文件
        logger.info("[macOS文件选择] Step 3: 第一次回车（关闭对话框，选中文件）")
        pyautogui.press('enter')
        time.sleep(0.8)  # 等待文件被选中
        
        # 第二次回车 - 打开文件（点击"打开"按钮）
        logger.info("[macOS文件选择] Step 4: 第二次回车（打开文件）")
        pyautogui.press('enter')
        time.sleep(0.5)
        
        # 恢复剪贴板
        try:
            pyperclip.copy(original_clipboard)
        except:
            pass
        
        logger.info("[macOS文件选择] 文件选择完成")
        return True
        
    except Exception as e:
        logger.error(f"[macOS文件选择] 操作失败: {e}")
        return False


def select_file_in_dialog_windows(file_path):
    """Windows上在文件对话框中选择文件"""
    try:
        # 保存原始剪贴板内容
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
        
        # 恢复剪贴板
        try:
            pyperclip.copy(original_clipboard)
        except:
            pass
        
        logger.info("[Windows文件选择] 文件选择完成")
        return True
        
    except Exception as e:
        logger.error(f"[Windows文件选择] 操作失败: {e}")
        return False

def upload_file_with_retry(file_path, button_x, button_y, nav_bar_height, 
                           button_width, button_height, max_retries=3, preview_only=False):
    """
    文件上传流程：
    1. 移动鼠标到上传按钮位置（让用户确认）
    2. 通过WebSocket让扩展确认hover元素是否是文件上传按钮
    3. 确认后点击上传按钮
    4. 等待对话框出现后选择文件
    
    参数:
        preview_only: 如果为True，只移动鼠标预览位置，不点击
    
    macOS: 点击按钮后直接选择文件（系统对话框是模态的）
    Windows: 等待对话框出现后选择文件
    """
    if not PYAUTOGUI_AVAILABLE:
        logger.error("pyautogui不可用")
        return False

    file_path = os.path.abspath(file_path)
    if not os.path.exists(file_path):
        logger.error(f"文件不存在: {file_path}")
        return False

    # 移动鼠标到上传按钮位置
    if button_x is not None and button_y is not None:
        logger.info(f"[上传] 移动鼠标到按钮位置 ({button_x}, {button_y})")
        
        # 先移动鼠标到目标位置（不点击）
        moved, screen_x, screen_y = move_to_position(button_x, button_y, nav_bar_height)
        
        if not moved:
            logger.warning("[上传] 移动鼠标失败")
            return False
        
        logger.info(f"[上传] 鼠标已移动到屏幕坐标 ({screen_x}, {screen_y})")
        
        # 如果只是预览模式，暂停让用户确认
        if preview_only:
            logger.info("[上传] 预览模式：鼠标已移动到目标位置，请确认...")
            logger.info("[上传] 等待3秒后自动继续...")
            time.sleep(3)  # 暂停3秒让用户确认
            logger.info("[上传] 预览结束")
            return True
        
        # 通过WebSocket让扩展确认hover的元素
        element_info = {
            'expected_type': 'file_upload_button',
            'button_width': button_width,
            'button_height': button_height
        }
        
        confirm_result = ws_prepare_click(button_x, button_y, nav_bar_height, element_info)
        
        if confirm_result and confirm_result.get('confirmed'):
            logger.info("[上传] 扩展确认hover元素是文件上传按钮")
            if confirm_result.get('reasons'):
                logger.info(f"[上传] 确认原因: {confirm_result['reasons']}")
        else:
            # 如果扩展没有确认，记录警告但继续尝试点击
            reason = confirm_result.get('reasons', ['未知原因']) if confirm_result else ['无响应']
            logger.warning(f"[上传] 扩展未确认hover元素: {reason}")
            logger.info("[上传] 继续尝试点击...")
        
        # 点击上传按钮
        if not click_at_position(button_x, button_y, nav_bar_height, button_width, button_height):
            logger.warning(f"[上传] 点击按钮失败")
            return False
    
    if system == 'Darwin':
        # macOS: 点击按钮后文件对话框会立即打开（模态）
        # 等待一小段时间让对话框完全显示
        time.sleep(0.8)
        
        # 直接选择文件
        logger.info("[上传] macOS: 直接选择文件")
        success = select_file_in_dialog_macos(file_path)
        if success:
            logger.info("[上传] 文件上传成功")
            return True
        else:
            logger.warning("[上传] 文件选择失败")
            return False
    else:
        # Windows: 等待对话框出现
        dialog = wait_for_file_dialog(target_title='打开', timeout=3.0, interval=0.2)
        
        if dialog:
            logger.info(f"[上传] 找到对话框: '{dialog.get('title', '')}'")
            hwnd = dialog.get('hwnd')
            focus_window(hwnd)
            time.sleep(0.3)
            
            # 选择文件
            success = select_file_in_dialog_windows(file_path)
            if success:
                logger.info("[上传] 文件上传成功")
                return True
            else:
                logger.warning("[上传] 文件选择失败")
                return False
        else:
            logger.warning("[上传] 对话框未出现")
            return False



# ==================== WebSocket ====================

import json as json_module

@sock.route('/ws')
def websocket_handler(ws):
    """WebSocket 连接处理"""
    ws_clients.add(ws)
    logger.info(f"[WS] 客户端连接，当前连接数: {len(ws_clients)}")
    
    last_pong = time.time()
    HEARTBEAT_INTERVAL = 30
    
    try:
        while True:
            try:
                data = ws.receive(timeout=HEARTBEAT_INTERVAL)
                if data is None:
                    current_time = time.time()
                    if current_time - last_pong > HEARTBEAT_INTERVAL * 2:
                        logger.warning("[WS] 心跳超时，断开连接")
                        break
                    try:
                        ws.send(json_module.dumps({'type': 'ping', 'timestamp': int(current_time)}))
                    except:
                        break
                    continue
                
                message = json_module.loads(data)
                msg_type = message.get('type', '')
                
                if msg_type == 'pong':
                    last_pong = time.time()
                    continue
                
                if msg_type == 'ping':
                    ws.send(json_module.dumps({'type': 'pong', 'timestamp': int(time.time())}))
                    continue
                
                if msg_type == 'confirm-hover':
                    request_id = message.get('request_id', '')
                    confirmed = message.get('confirmed', False)
                    is_file_upload_button = message.get('isFileUploadButton', False)
                    corrected_x = message.get('corrected_x')
                    corrected_y = message.get('corrected_y')
                    element = message.get('element', {})
                    reasons = message.get('reasons', [])
                    
                    if request_id in ws_pending_click:
                        ws_pending_click[request_id] = {
                            'confirmed': confirmed,
                            'isFileUploadButton': is_file_upload_button,
                            'corrected_x': corrected_x,
                            'corrected_y': corrected_y,
                            'element': element,
                            'reasons': reasons,
                            'timestamp': time.time()
                        }
                        logger.info(f"[WS] 收到点击确认: request_id={request_id}, confirmed={confirmed}, isFileUploadButton={is_file_upload_button}")
                        if reasons:
                            logger.info(f"[WS] 确认原因: {reasons}")
                    
                    continue
                
                logger.info(f"[WS] 收到消息: {msg_type}")
                
            except Exception as e:
                if 'timeout' in str(e).lower() or 'timed out' in str(e).lower():
                    current_time = time.time()
                    if current_time - last_pong > HEARTBEAT_INTERVAL * 2:
                        logger.warning("[WS] 心跳超时，断开连接")
                        break
                    try:
                        ws.send(json_module.dumps({'type': 'ping', 'timestamp': int(current_time)}))
                    except:
                        break
                    continue
                raise
                
    except Exception as e:
        logger.error(f"[WS] 连接异常: {e}")
    finally:
        ws_clients.discard(ws)
        logger.info(f"[WS] 客户端断开，当前连接数: {len(ws_clients)}")

def ws_send_and_wait(message, wait_for_type=None, timeout=10.0):
    """向所有 WebSocket 客户端发送消息，可选等待特定类型的响应"""
    if not ws_clients:
        logger.warning("[WS] 没有连接的客户端")
        return None
    
    data = json_module.dumps(message)
    dead_clients = set()
    
    for ws in ws_clients:
        try:
            ws.send(data)
        except Exception as e:
            logger.error(f"[WS] 发送失败: {e}")
            dead_clients.add(ws)
    
    ws_clients.difference_update(dead_clients)
    
    if not wait_for_type or not ws_clients:
        return None
    
    deadline = time.time() + timeout
    request_id = message.get('request_id', '')
    
    while time.time() < deadline:
        if request_id and request_id in ws_pending_click:
            result = ws_pending_click.pop(request_id)
            return result
        time.sleep(0.1)
    
    logger.warning(f"[WS] 等待响应超时: {wait_for_type}")
    return None

def ws_prepare_click(viewport_x, viewport_y, nav_bar_height, element_info=None):
    """通知扩展准备点击，等待 hover 确认"""
    import uuid
    request_id = str(uuid.uuid4())[:8]
    
    message = {
        'type': 'prepare-click',
        'request_id': request_id,
        'viewport_x': viewport_x,
        'viewport_y': viewport_y,
        'nav_bar_height': nav_bar_height,
        'element_info': element_info or {}
    }
    
    ws_pending_click[request_id] = None
    result = ws_send_and_wait(message, wait_for_type='confirm-hover', timeout=10.0)
    ws_pending_click.pop(request_id, None)
    
    return result

# ==================== Flask路由 ====================

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok', 'message': '服务正常'})


@app.route('/images/<path:filename>')
def serve_image(filename):
    """提供图片静态访问"""
    images_dir = get_images_dir()
    return send_from_directory(str(images_dir), filename)


@app.route('/api/open-file-location', methods=['POST'])
def open_file_location():
    """打开文件所在目录"""
    import subprocess
    
    data = request.json
    image_url = data.get('imageUrl', '')
    
    if not image_url:
        return jsonify({'success': False, 'error': '图片URL为空'})
    
    try:
        # 从URL提取文件路径
        if image_url.startswith('/images/'):
            # 本地图片路径
            file_path = Path(__file__).parent / image_url.lstrip('/')
        elif image_url.startswith('http://localhost') or image_url.startswith('https://localhost'):
            # 从本地服务器URL提取路径
            from urllib.parse import urlparse
            parsed = urlparse(image_url)
            file_path = Path(__file__).parent / parsed.path.lstrip('/')
        else:
            return jsonify({'success': False, 'error': '不支持的URL格式'})
        
        if not file_path.exists():
            return jsonify({'success': False, 'error': f'文件不存在: {file_path}'})
        
        # 获取文件所在目录
        dir_path = file_path.parent
        
        logger.info(f"[打开目录] 文件: {file_path}")
        logger.info(f"[打开目录] 目录: {dir_path}")
        
        # 根据操作系统打开目录
        if system == 'Darwin':
            # macOS: 使用 Finder 打开并选中文件
            subprocess.Popen(['open', '-R', str(file_path)])
        elif system == 'Windows':
            # Windows: 使用资源管理器打开并选中文件
            subprocess.Popen(['explorer', '/select,', str(file_path)])
        else:
            # Linux: 使用 xdg-open 打开目录
            subprocess.Popen(['xdg-open', str(dir_path)])
        
        return jsonify({
            'success': True,
            'path': str(file_path),
            'directory': str(dir_path)
        })
        
    except Exception as e:
        logger.error(f"[打开目录] 失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


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
        
        images_dir = get_images_dir()
        
        # 解析base64数据
        if file_data.startswith('data:'):
            # 移除data:image/xxx;base64,前缀
            file_data = file_data.split(',')[1]
        
        file_bytes = base64.b64decode(file_data)
        
        # 保存文件
        file_path = images_dir / filename
        with open(file_path, 'wb') as f:
            f.write(file_bytes)
        
        logger.info(f"保存本地图片: {file_path}")
        
        return jsonify({
            'success': True,
            'path': str(file_path),
            'url': f'/images/{filename}'
        })
        
    except Exception as e:
        logger.error(f"保存图片失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


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
    button_width = data.get('buttonWidth', 0)
    button_height = data.get('buttonHeight', 0)
    preview_only = data.get('preview', False)  # 预览模式
    
    if not filename:
        return jsonify({'success': False, 'error': '文件名为空'})

    logger.info(f"查找文件: {filename} (isLocal={is_local})")
    logger.info(f"视口坐标: ({button_x}, {button_y}), 导航栏高度: {nav_bar_height}")
    
    if preview_only:
        logger.info("预览模式：只移动鼠标到目标位置")

    full_path = find_file(filename)
    
    if not full_path:
        return jsonify({'success': False, 'error': f'文件不存在: {filename}'})

    logger.info(f"找到文件: {full_path}")

    try:
        # 使用带重试的上传流程
        success = upload_file_with_retry(
            full_path, button_x, button_y, nav_bar_height,
            button_width, button_height, max_retries=3, 
            preview_only=preview_only
        )
        
        if success:
            if preview_only:
                return jsonify({'success': True, 'message': '预览完成，鼠标已移动到目标位置'})
            else:
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
    """处理单个文件上传"""
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


@app.route('/api/debug/browser-info', methods=['GET'])
def debug_browser_info():
    """调试：获取浏览器窗口信息"""
    window = get_browser_window()
    
    if not window:
        return jsonify({'success': False, 'error': '未找到浏览器窗口'})
    
    return jsonify({
        'success': True,
        'browser': {
            'title': window.title,
            'left': window.left,
            'top': window.top,
            'width': window.width,
            'height': window.height,
            'isMinimized': window.isMinimized,
            'isActive': window.isActive
        }
    })


@app.route('/api/debug/test-click', methods=['POST'])
def debug_test_click():
    """调试：测试点击坐标"""
    data = request.json
    viewport_x = data.get('x', 0)
    viewport_y = data.get('y', 0)
    
    logger.info(f"测试点击: viewport({viewport_x}, {viewport_y})")
    
    success = click_at_position(viewport_x, viewport_y)
    
    return jsonify({
        'success': success,
        'viewport': {'x': viewport_x, 'y': viewport_y}
    })


def get_split_dir():
    """获取图片分割目录"""
    split_dir = Path(__file__).parent / "images" / "split"
    split_dir.mkdir(parents=True, exist_ok=True)
    return split_dir


@app.route('/api/split-image', methods=['POST'])
def split_image():
    """分割图片"""
    import cv2
    import numpy as np
    from urllib.parse import urlparse
    
    data = request.json
    image_url = data.get('imageUrl', '')
    filename = data.get('filename', 'unknown.jpg')
    
    logger.info(f"[分割] 收到请求: imageUrl={image_url}, filename={filename}")
    
    if not image_url:
        return jsonify({'success': False, 'error': '图片URL为空'})
    
    try:
        # 获取图片
        if image_url.startswith('http'):
            # 远程图片，下载
            import requests
            logger.info(f"[分割] 下载远程图片: {image_url}")
            response = requests.get(image_url, timeout=10)
            if response.status_code != 200:
                logger.error(f"[分割] 下载失败: status={response.status_code}")
                return jsonify({'success': False, 'error': f'下载图片失败: status={response.status_code}'})
            
            # 保存临时文件
            temp_path = Path(__file__).parent / "images" / "temp_split.jpg"
            temp_path.parent.mkdir(parents=True, exist_ok=True)
            with open(temp_path, 'wb') as f:
                f.write(response.content)
            img = cv2.imread(str(temp_path))
        elif image_url.startswith('/images/'):
            # 本地图片
            img_path = Path(__file__).parent / image_url.lstrip('/')
            logger.info(f"[分割] 读取本地图片: {img_path}")
            if not img_path.exists():
                logger.error(f"[分割] 文件不存在: {img_path}")
                return jsonify({'success': False, 'error': f'文件不存在: {img_path}'})
            img = cv2.imread(str(img_path))
        else:
            logger.error(f"[分割] 不支持的URL格式: {image_url}")
            return jsonify({'success': False, 'error': f'不支持的图片URL格式: {image_url}'})
        
        if img is None:
            logger.error("[分割] 无法读取图片")
            return jsonify({'success': False, 'error': '无法读取图片'})
        
        height, width = img.shape[:2]
        logger.info(f"[分割] 图片尺寸: {width} x {height}")
        
        # 分割图片
        regions = split_grid_image(img)
        
        if not regions:
            return jsonify({'success': False, 'error': '未检测到可分割的区域'})
        
        # 创建输出目录
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        name_without_ext = Path(filename).stem
        output_dir_name = f"{timestamp}_{name_without_ext}"
        output_dir = get_split_dir() / output_dir_name
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存分割后的图片
        output_images = []
        for i, region_img in enumerate(regions):
            # 裁剪黑色边缘和红色线条
            cropped = crop_black_edges(region_img)
            
            if cropped.shape[0] < 30 or cropped.shape[1] < 30:
                continue
            
            output_filename = f"split_{i+1:03d}.jpg"
            output_path = output_dir / output_filename
            cv2.imwrite(str(output_path), cropped, [cv2.IMWRITE_JPEG_QUALITY, 95])
            
            # 返回可访问的URL
            output_url = f"/images/split/{output_dir_name}/{output_filename}"
            output_images.append({
                'url': output_url,
                'filename': output_filename,
                'width': cropped.shape[1],
                'height': cropped.shape[0]
            })
            
            logger.info(f"[分割] 保存: {output_filename} ({cropped.shape[1]}x{cropped.shape[0]})")
        
        return jsonify({
            'success': True,
            'count': len(output_images),
            'images': output_images,
            'outputDir': str(output_dir)
        })
        
    except Exception as e:
        logger.error(f"[分割] 失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


def split_grid_image(img):
    """分割网格排列的图片"""
    import cv2
    import numpy as np
    
    height, width = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # 二值化
    _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
    
    # 查找分割线
    h_lines = find_dividing_lines(binary, axis='horizontal', min_length=width*0.3)
    v_lines = find_dividing_lines(binary, axis='vertical', min_length=height*0.3)
    
    logger.info(f"[分割] 检测到 {len(h_lines)} 条水平分割线, {len(v_lines)} 条垂直分割线")
    
    # 计算网格区域
    regions = calculate_grid_regions(h_lines, v_lines, width, height, img=img)
    
    if not regions:
        # 尝试自动检测
        regions = auto_detect_grid(binary, width, height, img=img)
    
    # 裁剪每个区域
    result = []
    for x, y, w, h in regions:
        region = img[y:y+h, x:x+w]
        result.append(region)
    
    return result


def find_dividing_lines(binary, axis='horizontal', min_length=100, threshold=0.8):
    """查找分割线"""
    import numpy as np
    
    lines = []
    h, w = binary.shape
    
    if axis == 'horizontal':
        for y in range(h):
            row = binary[y, :]
            white_ratio = np.sum(row > 0) / w
            if white_ratio > threshold:
                if is_continuous_line(row, min_length):
                    lines.append(y)
    else:
        for x in range(w):
            col = binary[:, x]
            white_ratio = np.sum(col > 0) / h
            if white_ratio > threshold:
                if is_continuous_line(col, min_length):
                    lines.append(x)
    
    return merge_nearby_lines(lines, gap=5)


def is_continuous_line(pixels, min_length):
    """检查是否是连续的白色像素"""
    max_continuous = 0
    current = 0
    
    for p in pixels:
        if p > 0:
            current += 1
            max_continuous = max(max_continuous, current)
        else:
            current = 0
    
    return max_continuous >= min_length


def merge_nearby_lines(lines, gap=5):
    """合并相近的线"""
    if not lines:
        return []
    
    merged = [lines[0]]
    for line in lines[1:]:
        if line - merged[-1] <= gap:
            merged[-1] = (merged[-1] + line) // 2
        else:
            merged.append(line)
    
    return merged


def calculate_grid_regions(h_lines, v_lines, width, height, img=None, min_white_ratio=0.1):
    """根据分割线计算网格区域"""
    import cv2
    import numpy as np
    
    regions = []
    
    h_boundaries = [0] + h_lines + [height]
    v_boundaries = [0] + v_lines + [width]
    
    for i in range(len(h_boundaries) - 1):
        for j in range(len(v_boundaries) - 1):
            y1 = h_boundaries[i]
            y2 = h_boundaries[i + 1]
            x1 = v_boundaries[j]
            x2 = v_boundaries[j + 1]
            
            w = x2 - x1
            h = y2 - y1
            
            if w < 50 or h < 50:
                continue
            
            if img is not None:
                region = img[y1:y2, x1:x2]
                if is_black_region(region, threshold=30, white_ratio_threshold=min_white_ratio):
                    continue
            
            regions.append((x1, y1, w, h))
    
    return regions


def is_black_region(region, threshold=30, white_ratio_threshold=0.1):
    """检查区域是否是黑色/无效区域"""
    import cv2
    import numpy as np
    
    gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
    
    white_pixels = np.sum(gray > 200)
    total_pixels = gray.size
    white_ratio = white_pixels / total_pixels
    
    mean_brightness = np.mean(gray)
    
    if white_ratio < white_ratio_threshold or mean_brightness < threshold:
        return True
    
    return False


def auto_detect_grid(binary, width, height, img=None):
    """自动检测网格"""
    import numpy as np
    
    h_proj = np.sum(binary, axis=1)
    v_proj = np.sum(binary, axis=0)
    
    h_splits = find_splits_from_projection(h_proj, threshold=np.max(h_proj)*0.1, min_gap=50)
    v_splits = find_splits_from_projection(v_proj, threshold=np.max(v_proj)*0.1, min_gap=50)
    
    h_boundaries = [0] + h_splits + [height]
    v_boundaries = [0] + v_splits + [width]
    
    regions = []
    for i in range(len(h_boundaries) - 1):
        for j in range(len(v_boundaries) - 1):
            y1 = h_boundaries[i]
            y2 = h_boundaries[i + 1]
            x1 = v_boundaries[j]
            x2 = v_boundaries[j + 1]
            
            w = x2 - x1
            h = y2 - y1
            
            if w < 50 or h < 50:
                continue
            
            if img is not None:
                region = img[y1:y2, x1:x2]
                if is_black_region(region, threshold=30, white_ratio_threshold=0.1):
                    continue
            
            regions.append((x1, y1, w, h))
    
    return regions


def find_splits_from_projection(projection, threshold, min_gap=50):
    """从投影中找到分割位置"""
    splits = []
    below_threshold = False
    start = 0
    
    for i, val in enumerate(projection):
        if val < threshold and not below_threshold:
            below_threshold = True
            start = i
        elif val >= threshold and below_threshold:
            below_threshold = False
            mid = (start + i) // 2
            if i - start >= 10:
                splits.append(mid)
    
    return merge_nearby_lines(splits, gap=min_gap)


def crop_black_edges(image, threshold=30, margin=2):
    """裁剪图片的黑色边缘和红色线条"""
    import cv2
    import numpy as np
    
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    
    lower_red1 = np.array([0, 50, 50])
    upper_red1 = np.array([10, 255, 255])
    mask_red1 = cv2.inRange(hsv, lower_red1, upper_red1)
    
    lower_red2 = np.array([160, 50, 50])
    upper_red2 = np.array([180, 255, 255])
    mask_red2 = cv2.inRange(hsv, lower_red2, upper_red2)
    
    mask_red = mask_red1 | mask_red2
    
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    mask_black = gray > threshold
    
    mask_valid = mask_black & (mask_red == 0)
    
    rows = np.any(mask_valid, axis=1)
    cols = np.any(mask_valid, axis=0)
    
    if not np.any(rows) or not np.any(cols):
        return image
    
    rmin, rmax = np.where(rows)[0][[0, -1]]
    cmin, cmax = np.where(cols)[0][[0, -1]]
    
    rmin = max(0, rmin - margin)
    rmax = min(image.shape[0] - 1, rmax + margin)
    cmin = max(0, cmin - margin)
    cmax = min(image.shape[1] - 1, cmax + margin)
    
    return image[rmin:rmax+1, cmin:cmax+1]


@app.route('/images/split/<path:filename>')
def serve_split_image(filename):
    """提供分割后的图片访问"""
    split_dir = get_split_dir()
    return send_from_directory(str(split_dir), filename)


if __name__ == '__main__':
    work_dir = get_work_dir()
    
    logger.info("=" * 50)
    logger.info("Google Image Search Tool - 本地服务器")
    logger.info("=" * 50)
    logger.info(f"工作目录: {work_dir}")
    logger.info(f"pyautogui: {'可用' if PYAUTOGUI_AVAILABLE else '不可用'}")
    
    if system == 'Darwin':
        logger.info(f"Quartz: {'可用' if 'Quartz' in dir() else '不可用'}")
    elif system == 'Windows':
        logger.info(f"pygetwindow: {'可用' if 'gw' in dir() else '不可用'}")
    
    logger.info(f"操作系统: {system}")
    logger.info("服务器地址: http://localhost:5277")
    logger.info("=" * 50)

    app.run(host='0.0.0.0', port=5277, debug=False)