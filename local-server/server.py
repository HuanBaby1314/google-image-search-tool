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
try:
    import pyautogui
    import pyperclip
    import pygetwindow as gw
    import win32gui
    import win32con
    PYAUTOGUI_AVAILABLE = True
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.05
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
    
    # 尝试获取Chrome或Edge窗口
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
    
    # 使用动态计算的导航栏高度
    screen_x = browser_x + viewport_x
    screen_y = browser_y + viewport_y + nav_bar_height
    
    logger.info(f"浏览器位置: ({browser_x}, {browser_y})")
    logger.info(f"视口坐标: ({viewport_x}, {viewport_y})")
    logger.info(f"导航栏高度: {nav_bar_height} (动态计算)")
    logger.info(f"屏幕坐标: ({screen_x}, {screen_y})")
    
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


def find_file_dialog(target_title='打开'):
    """查找文件对话框"""
    if not PYAUTOGUI_AVAILABLE:
        logger.error("find_file_dialog: PYAUTOGUI_AVAILABLE=False")
        return None
    
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
    deadline = time.time() + timeout
    while time.time() < deadline:
        if win32gui.GetForegroundWindow() == hwnd:
            return True
        time.sleep(interval)
    return False

def focus_window(hwnd):
    """聚焦窗口"""
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
    """在文件对话框中选择文件（假设对话框已打开）"""
    if not PYAUTOGUI_AVAILABLE:
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
        
        logger.info("文件选择完成")
        return True
        
    except Exception as e:
        logger.error(f"操作失败: {e}")
        return False

def upload_file_with_retry(file_path, button_x, button_y, nav_bar_height, 
                           button_width, button_height, max_retries=3):
    """
    文件上传流程（重试逻辑由扩展端处理）：
    1. 点击上传按钮
    2. 等待对话框出现
    3. 对话框出现后选择文件
    """
    if not PYAUTOGUI_AVAILABLE:
        logger.error("pyautogui不可用")
        return False

    file_path = os.path.abspath(file_path)
    if not os.path.exists(file_path):
        logger.error(f"文件不存在: {file_path}")
        return False

    # 点击上传按钮
    if button_x is not None and button_y is not None:
        logger.info(f"[上传] 点击按钮 ({button_x}, {button_y})")
        if not click_at_position(button_x, button_y, nav_bar_height, button_width, button_height):
            logger.warning(f"[上传] 点击按钮失败")
            return False
    
    # 等待对话框出现
    dialog = wait_for_file_dialog(target_title='打开', timeout=3.0, interval=0.2)
    
    if dialog:
        hwnd = dialog['hwnd']
        logger.info(f"[上传] 找到对话框: '{dialog['title']}'")
        focus_window(hwnd)
        time.sleep(0.3)
        
        # 选择文件
        success = select_file_in_dialog(file_path)
        if success:
            logger.info(f"[上传] 文件上传成功")
            return True
        else:
            logger.warning(f"[上传] 文件选择失败")
            return False
    else:
        logger.warning(f"[上传] 对话框未出现")



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
                    corrected_x = message.get('corrected_x')
                    corrected_y = message.get('corrected_y')
                    
                    if request_id in ws_pending_click:
                        ws_pending_click[request_id] = {
                            'confirmed': confirmed,
                            'corrected_x': corrected_x,
                            'corrected_y': corrected_y,
                            'timestamp': time.time()
                        }
                        logger.info(f"[WS] 收到点击确认: request_id={request_id}, confirmed={confirmed}")
                    
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
    
    if not filename:
        return jsonify({'success': False, 'error': '文件名为空'})

    logger.info(f"查找文件: {filename} (isLocal={is_local})")
    logger.info(f"视口坐标: ({button_x}, {button_y}), 导航栏高度: {nav_bar_height}")

    full_path = find_file(filename)
    
    if not full_path:
        return jsonify({'success': False, 'error': f'文件不存在: {filename}'})

    logger.info(f"找到文件: {full_path}")

    try:
        # 使用带重试的上传流程
        success = upload_file_with_retry(
            full_path, button_x, button_y, nav_bar_height,
            button_width, button_height, max_retries=3
        )
        
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


if __name__ == '__main__':
    work_dir = get_work_dir()
    
    logger.info("=" * 50)
    logger.info("Google Image Search Tool - 本地服务器")
    logger.info("=" * 50)
    logger.info(f"工作目录: {work_dir}")
    logger.info(f"pyautogui: {'可用' if PYAUTOGUI_AVAILABLE else '不可用'}")
    logger.info(f"pygetwindow: {'可用' if 'gw' in dir() else '不可用'}")
    logger.info("服务器地址: http://localhost:5000")
    logger.info("=" * 50)

    app.run(host='0.0.0.0', port=5277, debug=False)