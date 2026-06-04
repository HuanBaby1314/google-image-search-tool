     1|#!/usr/bin/env python3
     2|"""
     3|本地服务器 - 处理Chrome扩展的请求
     4|"""
     5|
     6|import os
     7|import sys
     8|import json
     9|import time
    10|import logging
    11|import shutil
    12|from pathlib import Path
    13|from datetime import datetime
    14|from threading import Thread
    15|
    16|from flask import Flask, request, jsonify
    17|from flask_cors import CORS
    18|
    19|logging.basicConfig(
    20|    level=logging.INFO,
    21|    format='%(asctime)s - %(levelname)s - %(message)s'
    22|)
    23|logger = logging.getLogger(__name__)
    24|
    25|app = Flask(__name__)
    26|CORS(app)
    27|
    28|# 导入依赖
    29|try:
    30|    import pyautogui
    31|    import pyperclip
    32|    import pygetwindow as gw
    33|    import win32gui
    34|    import win32con
    35|    PYAUTOGUI_AVAILABLE = True
    36|    pyautogui.FAILSAFE = True
    37|    pyautogui.PAUSE = 0.05
    38|except ImportError as e:
    39|    logger.warning(f"依赖缺失: {e}")
    40|    PYAUTOGUI_AVAILABLE = False
    41|
    42|
    43|def get_base_dir():
    44|    return Path.home() / "Downloads"
    45|
    46|
    47|def get_today_dir():
    48|    return datetime.now().strftime('%Y%m%d')
    49|
    50|
    51|def get_work_dir():
    52|    base = get_base_dir()
    53|    today = get_today_dir()
    54|    work_dir = base / "qingqing_helper_dir" / today
    55|    work_dir.mkdir(parents=True, exist_ok=True)
    56|    return work_dir
    57|
    58|
    59|def find_file(filename):
    60|    """查找文件，支持扩展名映射"""
    61|    base = get_base_dir()
    62|    work_dir = get_work_dir()
    63|    
    64|    name_stem = Path(filename).stem
    65|    name_ext = Path(filename).suffix
    66|    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
    67|    
    68|    if name_ext.lower() in image_extensions:
    69|        search_extensions = [name_ext] + [ext for ext in image_extensions if ext != name_ext]
    70|    else:
    71|        search_extensions = image_extensions
    72|    
    73|    search_dirs = [work_dir, base / "qingqing_helper_dir", base]
    74|    
    75|    helper_dir = base / "qingqing_helper_dir"
    76|    if helper_dir.exists():
    77|        for date_dir in sorted(helper_dir.iterdir(), reverse=True):
    78|            if date_dir.is_dir() and date_dir.name != "local" and date_dir != work_dir:
    79|                search_dirs.append(date_dir)
    80|    
    81|    # 1. 原始文件名
    82|    for search_dir in search_dirs:
    83|        if search_dir.exists():
    84|            target = search_dir / filename
    85|            if target.exists():
    86|                logger.info(f"找到原始文件: {target}")
    87|                return str(target)
    88|    
    89|    # 2. 扩展名映射
    90|    for search_dir in search_dirs:
    91|        if search_dir.exists():
    92|            for ext in search_extensions:
    93|                target = search_dir / (name_stem + ext)
    94|                if target.exists():
    95|                    logger.info(f"找到映射文件: {target} (原始: {filename})")
    96|                    return str(target)
    97|    
    98|    # 3. 模糊匹配
    99|    for search_dir in search_dirs:
   100|        if search_dir.exists():
   101|            for f in search_dir.iterdir():
   102|                if f.is_file() and name_stem in f.stem:
   103|                    if f.suffix.lower() in image_extensions:
   104|                        logger.info(f"找到模糊匹配: {f} (原始: {filename})")
   105|                        return str(f)
   106|    
   107|    return None
   108|
   109|
   110|def get_browser_window():
   111|    """获取浏览器窗口"""
   112|    if not PYAUTOGUI_AVAILABLE:
   113|        return None
   114|    
   115|    # 尝试获取Chrome或Edge窗口
   116|    browsers = ['Chrome', 'Edge', 'Google Chrome', 'Microsoft Edge']
   117|    
   118|    for browser_name in browsers:
   119|        try:
   120|            windows = gw.getWindowsWithTitle(browser_name)
   121|            if windows:
   122|                # 返回第一个非最小化的窗口，或第一个窗口
   123|                for win in windows:
   124|                    if not win.isMinimized and win.width > 100 and win.height > 100:
   125|                        return win
   126|                return windows[0]
   127|        except Exception:
   128|            continue
   129|    
   130|    return None
   131|
   132|
   133|def calculate_screen_position(viewport_x, viewport_y, nav_bar_height=85):
   134|    """将浏览器视口坐标转换为屏幕绝对坐标"""
   135|    window = get_browser_window()
   136|    
   137|    if not window:
   138|        logger.error("未找到浏览器窗口")
   139|        return None, None
   140|    
   141|    try:
   142|        if window.isMinimized:
   143|            window.restore()
   144|        window.activate()
   145|        time.sleep(0.3)
   146|    except Exception as e:
   147|        logger.warning(f"激活窗口失败: {e}")
   148|    
   149|    browser_x = window.left
   150|    browser_y = window.top
   151|    
   152|    # 使用动态计算的导航栏高度
   153|    screen_x = browser_x + viewport_x
   154|    screen_y = browser_y + viewport_y + nav_bar_height
   155|    
   156|    logger.info(f"浏览器位置: ({browser_x}, {browser_y})")
   157|    logger.info(f"视口坐标: ({viewport_x}, {viewport_y})")
   158|    logger.info(f"导航栏高度: {nav_bar_height} (动态计算)")
   159|    logger.info(f"屏幕坐标: ({screen_x}, {screen_y})")
   160|    
   161|    return screen_x, screen_y
   162|
   163|
   164|def click_at_position(viewport_x, viewport_y, nav_bar_height=85):
   165|    """点击浏览器页面中的元素"""
   166|    if not PYAUTOGUI_AVAILABLE:
   167|        logger.error("pyautogui不可用")
   168|        return False
   169|    
   170|    try:
   171|        screen_x, screen_y = calculate_screen_position(viewport_x, viewport_y, nav_bar_height)
   172|        
   173|        if screen_x is None or screen_y is None:
   174|            return False
   175|        
   176|        screen_width, screen_height = pyautogui.size()
   177|        if screen_x < 0 or screen_x > screen_width or screen_y < 0 or screen_y > screen_height:
   178|            logger.error(f"坐标超出屏幕范围: ({screen_x}, {screen_y})")
   179|            return False
   180|        
   181|        logger.info(f"点击屏幕坐标: ({screen_x}, {screen_y})")
   182|        pyautogui.click(screen_x, screen_y)
   183|        time.sleep(0.5)
   184|        return True
   185|        
   186|    except Exception as e:
   187|        logger.error(f"点击失败: {e}")
   188|        return False
   189|        
   202|        logger.error(f"点击失败: {e}")
   203|        return False
   204|
   205|
   206|def find_file_dialog(target_title='打开'):
   207|    """查找文件对话框"""
   208|    if not PYAUTOGUI_AVAILABLE:
   209|        return None
   210|    
   211|    result = []
   212|    
   213|    def callback(hwnd, _):
   214|        if win32gui.IsWindowVisible(hwnd):
   215|            title = win32gui.GetWindowText(hwnd)
   216|            class_name = win32gui.GetClassName(hwnd)
   217|            
   218|            if class_name == '#32770' or any(kw in title for kw in ['打开', 'Open', '选择', 'Choose']):
   219|                result.append({
   220|                    'hwnd': hwnd,
   221|                    'title': title,
   222|                    'exact_match': title == target_title
   223|                })
   224|    
   225|    try:
   226|        win32gui.EnumWindows(callback, None)
   227|    except Exception:
   228|        pass
   229|    
   230|    exact = [d for d in result if d['exact_match']]
   231|    if exact:
   232|        return exact[0]
   233|    
   234|    partial = [d for d in result if target_title in d['title']]
   235|    if partial:
   236|        return partial[0]
   237|    
   238|    return result[0] if result else None
   239|
   240|
   241|def focus_window(hwnd):
   242|    """聚焦窗口"""
   243|    try:
   244|        if win32gui.IsIconic(hwnd):
   245|            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
   246|            time.sleep(0.2)
   247|        
   248|        try:
   249|            shell = __import__('win32com.client').Dispatch("WScript.Shell")
   250|            shell.SendKeys('%')
   251|        except:
   252|            pass
   253|        
   254|        win32gui.SetForegroundWindow(hwnd)
   255|        time.sleep(0.3)
   256|        return True
   257|    except Exception as e:
   258|        logger.warning(f"聚焦窗口失败: {e}")
   259|        return False
   260|
   261|
   262|def select_file_in_dialog(file_path):
   263|    """在文件对话框中选择文件"""
   264|    if not PYAUTOGUI_AVAILABLE:
   265|        logger.error("pyautogui不可用")
   266|        return False
   267|
   268|    file_path = os.path.abspath(file_path)
   269|    
   270|    if not os.path.exists(file_path):
   271|        logger.error(f"文件不存在: {file_path}")
   272|        return False
   273|
   274|    logger.info(f"准备上传文件: {file_path}")
   275|
   276|    time.sleep(1.5)
   277|    
   278|    dialog = find_file_dialog(target_title='打开')
   279|    
   280|    if dialog:
   281|        hwnd = dialog['hwnd']
   282|        logger.info(f"找到对话框: '{dialog['title']}'")
   283|        focus_window(hwnd)
   284|        time.sleep(0.5)
   285|    else:
   286|        logger.warning("未找到文件对话框，尝试直接操作...")
   287|
   288|    try:
   289|        try:
   290|            original_clipboard = pyperclip.paste()
   291|        except:
   292|            original_clipboard = ''
   293|        
   294|        pyperclip.copy(file_path)
   295|        time.sleep(0.2)
   296|        
   297|        pyautogui.hotkey('ctrl', 'a')
   298|        time.sleep(0.1)
   299|        
   300|        pyautogui.hotkey('ctrl', 'v')
   301|        time.sleep(0.3)
   302|        
   303|        pyautogui.press('enter')
   304|        time.sleep(0.5)
   305|        
   306|        try:
   307|            pyperclip.copy(original_clipboard)
   308|        except:
   309|            pass
   310|        
   311|        logger.info("文件上传完成")
   312|        return True
   313|        
   314|    except Exception as e:
   315|        logger.error(f"操作失败: {e}")
   316|        return False
   317|
   318|
   319|# ==================== Flask路由 ====================
   320|
   321|@app.route('/api/health', methods=['GET'])
   322|def health_check():
   323|    return jsonify({'status': 'ok', 'message': '服务正常'})
   324|
   325|
   326|@app.route('/api/get-download-dir', methods=['GET'])
   327|def get_download_dir():
   328|    return jsonify({'download_dir': str(get_work_dir())})
   329|
   330|
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
   371|
   372|
   373|@app.route('/api/upload-and-search', methods=['POST'])
   374|def upload_and_search():
   375|    data = request.json
   376|    files = data.get('files', [])
   377|
   378|    if not files:
   379|        return jsonify({'success': False, 'error': '没有文件'})
   380|
   381|    for file_info in files:
   382|        filename = file_info.get('filename', '')
   383|        if filename:
   384|            thread = Thread(target=process_upload, args=(filename,))
   385|            thread.daemon = True
   386|            thread.start()
   387|
   388|    return jsonify({'success': True, 'count': len(files)})
   389|
   390|
   391|def process_upload(filename):
   392|    """处理单个文件上传"""
   393|    try:
   394|        full_path = find_file(filename)
   395|        if not full_path:
   396|            logger.error(f"文件不存在: {filename}")
   397|            return
   398|
   399|        success = select_file_in_dialog(full_path)
   400|        if success:
   401|            logger.info(f"上传成功: {filename}")
   402|        else:
   403|            logger.error(f"上传失败: {filename}")
   404|    except Exception as e:
   405|        logger.error(f"上传异常: {str(e)}")
   406|
   407|
   408|@app.route('/api/debug/browser-info', methods=['GET'])
   409|def debug_browser_info():
   410|    """调试：获取浏览器窗口信息"""
   411|    window = get_browser_window()
   412|    
   413|    if not window:
   414|        return jsonify({'success': False, 'error': '未找到浏览器窗口'})
   415|    
   416|    return jsonify({
   417|        'success': True,
   418|        'browser': {
   419|            'title': window.title,
   420|            'left': window.left,
   421|            'top': window.top,
   422|            'width': window.width,
   423|            'height': window.height,
   424|            'isMinimized': window.isMinimized,
   425|            'isActive': window.isActive
   426|        }
   427|    })
   428|
   429|
   430|@app.route('/api/debug/test-click', methods=['POST'])
   431|def debug_test_click():
   432|    """调试：测试点击坐标"""
   433|    data = request.json
   434|    viewport_x = data.get('x', 0)
   435|    viewport_y = data.get('y', 0)
   436|    
   437|    logger.info(f"测试点击: viewport({viewport_x}, {viewport_y})")
   438|    
   439|    success = click_at_position(viewport_x, viewport_y)
   440|    
   441|    return jsonify({
   442|        'success': success,
   443|        'viewport': {'x': viewport_x, 'y': viewport_y}
   444|    })
   445|
   446|
   447|if __name__ == '__main__':
   448|    work_dir = get_work_dir()
   449|    
   450|    logger.info("=" * 50)
   451|    logger.info("Google Image Search Tool - 本地服务器")
   452|    logger.info("=" * 50)
   453|    logger.info(f"工作目录: {work_dir}")
   454|    logger.info(f"pyautogui: {'可用' if PYAUTOGUI_AVAILABLE else '不可用'}")
   455|    logger.info(f"pygetwindow: {'可用' if 'gw' in dir() else '不可用'}")
   456|    logger.info("服务器地址: http://localhost:5000")
   457|    logger.info("=" * 50)
   458|
   459|    app.run(host='0.0.0.0', port=5000, debug=False)