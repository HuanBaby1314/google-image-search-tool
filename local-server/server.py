#!/usr/bin/env python3
"""
本地服务器 - 处理Chrome扩展的请求
开发调试用，通过 debug.bat 运行
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

# 从共享模块导入上传工具函数
from upload_utils import (
    PYAUTOGUI_AVAILABLE, DEPENDENCIES_OK, system,
    get_browser_window, calculate_screen_position,
    move_to_position, click_at_position,
    find_file_dialog, wait_for_file_dialog,
    wait_for_window_focus, focus_window,
    select_file_in_dialog, upload_file_with_retry
)

# 从共享模块导入图片分割函数
from split_utils import (
    get_split_dir, split_grid_image, crop_black_edges
)

app = Flask(__name__)
CORS(app)
sock = Sock(app)

# 全局错误处理器 - 确保所有错误返回 JSON 格式
@app.errorhandler(404)
def not_found(error):
    return jsonify({'success': False, 'error': '接口不存在'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'success': False, 'error': '服务器内部错误'}), 500

@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"未捕获的异常: {e}")
    import traceback
    traceback.print_exc()
    return jsonify({'success': False, 'error': str(e)}), 500

# WebSocket 客户端管理
ws_clients = set()
ws_pending_click = {}  # 待确认的点击请求


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
    
    # 搜索分割目录
    split_dir = get_images_dir() / "split"
    if split_dir.exists():
        for d in split_dir.iterdir():
            if d.is_dir():
                search_dirs.append(d)
    
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


# 上传工具函数已移至 upload_utils.py

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
            preview_only=preview_only,
            hover_check_fn=ws_prepare_click
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


@app.errorhandler(404)
def not_found(error):
    return jsonify({'success': False, 'error': '接口不存在'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'success': False, 'error': '服务器内部错误'}), 500

@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"未捕获的异常: {e}")
    import traceback
    traceback.print_exc()
    return jsonify({'success': False, 'error': str(e)}), 500

# WebSocket 客户端管理
ws_clients = set()
ws_pending_click = {}  # 待确认的点击请求


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


# 上传工具函数已移至 upload_utils.py


# ==================== 图片分割 ====================

@app.route('/api/split-image', methods=['POST'])
def split_image():
    """分割图片"""
    import cv2
    import numpy as np

    data = request.json
    image_url = data.get('imageUrl', '')
    filename = data.get('filename', 'unknown.jpg')

    logger.info(f"[分割] 收到请求: imageUrl={image_url}, filename={filename}")

    if not image_url:
        return jsonify({'success': False, 'error': '图片URL为空'})

    try:
        if image_url.startswith('http'):
            import requests
            logger.info(f"[分割] 下载远程图片: {image_url}")
            response = requests.get(image_url, timeout=10)
            if response.status_code != 200:
                return jsonify({'success': False, 'error': f'下载图片失败: status={response.status_code}'})
            temp_path = get_images_dir() / "temp_split.jpg"
            temp_path.parent.mkdir(parents=True, exist_ok=True)
            with open(temp_path, 'wb') as f:
                f.write(response.content)
            img = cv2.imread(str(temp_path))
        elif image_url.startswith('/images/'):
            img_path = get_images_dir() / image_url.lstrip('/images/')
            logger.info(f"[分割] 读取本地图片: {img_path}")
            if not img_path.exists():
                return jsonify({'success': False, 'error': f'文件不存在: {img_path}'})
            img = cv2.imread(str(img_path))
        else:
            return jsonify({'success': False, 'error': f'不支持的图片URL格式: {image_url}'})

        if img is None:
            return jsonify({'success': False, 'error': '无法读取图片'})

        height, width = img.shape[:2]
        logger.info(f"[分割] 图片尺寸: {width} x {height}")

        regions = split_grid_image(img)
        if not regions:
            return jsonify({'success': False, 'error': '未检测到可分割的区域'})

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        name_without_ext = Path(filename).stem
        output_dir_name = f"{timestamp}_{name_without_ext}"
        output_dir = get_split_dir() / output_dir_name
        output_dir.mkdir(parents=True, exist_ok=True)

        output_images = []
        for i, region_img in enumerate(regions):
            cropped = crop_black_edges(region_img)
            if cropped.shape[0] < 30 or cropped.shape[1] < 30:
                continue
            output_filename = f"split_{i+1:03d}.jpg"
            output_path = output_dir / output_filename
            cv2.imwrite(str(output_path), cropped, [cv2.IMWRITE_JPEG_QUALITY, 95])
            output_url = f"/images/split/{output_dir_name}/{output_filename}"
            output_images.append({'url': output_url, 'filename': output_filename, 'width': cropped.shape[1], 'height': cropped.shape[0]})
            logger.info(f"[分割] 保存: {output_filename}")

        return jsonify({'success': True, 'count': len(output_images), 'images': output_images, 'outputDir': str(output_dir)})

    except Exception as e:
        logger.error(f"[分割] 失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


@app.route('/images/split/<path:filename>')
def serve_split_image(filename):
    """提供分割后的图片访问"""
    split_dir = get_split_dir()
    return send_from_directory(str(split_dir), filename)



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
            preview_only=preview_only,
            hover_check_fn=ws_prepare_click
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


# 图片分割函数已移至 split_utils.py

if __name__ == '__main__':
    work_dir = get_work_dir()
    
    logger.info("=" * 50)
    logger.info("Google Image Search Tool - 本地服务器")
    logger.info("=" * 50)
    logger.info(f"工作目录: {work_dir}")
    logger.info(f"pyautogui: {'可用' if PYAUTOGUI_AVAILABLE else '不可用'}")
    logger.info(f"pygetwindow: {'可用' if DEPENDENCIES_OK else '不可用'}")
    
    logger.info(f"操作系统: {system}")
    logger.info("服务器地址: http://localhost:5277")
    logger.info("=" * 50)

    app.run(host='0.0.0.0', port=5277, debug=False)