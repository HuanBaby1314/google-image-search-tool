#!/usr/bin/env python3
"""
上传处理器 - 使用pyautogui操作文件上传对话框
"""

import os
import sys
import time
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 导入依赖
try:
    import pyautogui
    import pyperclip
    import win32gui
    import win32con
    PYAUTOGUI_AVAILABLE = True
except ImportError as e:
    logger.warning(f"依赖缺失: {e}")
    logger.info("尝试安装依赖...")
    import subprocess
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pyautogui', 'pyperclip', 'pywin32'])
        import pyautogui
        import pyperclip
        import win32gui
        import win32con
        PYAUTOGUI_AVAILABLE = True
        logger.info("依赖安装成功")
    except Exception as e:
        logger.error(f"安装失败: {e}")
        PYAUTOGUI_AVAILABLE = False

if PYAUTOGUI_AVAILABLE:
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.05


def find_file_dialog(target_title='打开'):
    """
    查找文件对话框窗口
    target_title: 目标窗口标题，如 '打开', 'Open', '选择文件'
    """
    if not PYAUTOGUI_AVAILABLE:
        return None
    
    result = []
    
    def callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            class_name = win32gui.GetClassName(hwnd)
            
            # 记录所有可见的对话框
            if class_name == '#32770' or any(kw in title for kw in ['打开', 'Open', '选择', 'Choose']):
                result.append({
                    'hwnd': hwnd,
                    'title': title,
                    'class': class_name,
                    'exact_match': title == target_title
                })
    
    try:
        win32gui.EnumWindows(callback, None)
    except Exception:
        pass
    
    # 优先返回精确匹配的
    exact = [d for d in result if d['exact_match']]
    if exact:
        return exact[0]
    
    # 否则返回标题包含目标的
    partial = [d for d in result if target_title in d['title']]
    if partial:
        return partial[0]
    
    # 返回第一个对话框
    return result[0] if result else None


def focus_window(hwnd):
    """聚焦窗口"""
    try:
        # 如果窗口最小化，先恢复
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            time.sleep(0.2)
        
        # 尝试多种方法聚焦
        try:
            shell = __import__('win32com.client').Dispatch("WScript.Shell")
            shell.SendKeys('%')
        except:
            pass
        
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.3)
        
        # 验证是否聚焦成功
        foreground = win32gui.GetForegroundWindow()
        if foreground == hwnd:
            logger.info("窗口聚焦成功")
            return True
        else:
            logger.warning(f"窗口聚焦可能失败，前台窗口: {foreground}, 目标: {hwnd}")
            return True  # 仍然继续尝试
    except Exception as e:
        logger.warning(f"聚焦窗口失败: {e}")
        return False


def select_file_in_dialog(file_path):
    """在文件对话框中选择文件"""
    if not PYAUTOGUI_AVAILABLE:
        logger.error("pyautogui不可用")
        return False

    file_path = os.path.abspath(file_path)
    
    if not os.path.exists(file_path):
        logger.error(f"文件不存在: {file_path}")
        return False

    logger.info(f"准备上传文件: {file_path}")

    # 等待文件对话框出现
    logger.info("等待文件对话框...")
    time.sleep(1.5)
    
    # 查找标题为"打开"的对话框
    dialog = find_file_dialog(target_title='打开')
    
    if dialog:
        hwnd = dialog['hwnd']
        logger.info(f"找到对话框: '{dialog['title']}' (hwnd={hwnd})")
        focus_window(hwnd)
        time.sleep(0.5)
    else:
        logger.warning("未找到文件对话框，尝试直接操作...")

    # 清空并输入文件路径
    try:
        # 保存原始剪贴板
        try:
            original_clipboard = pyperclip.paste()
        except:
            original_clipboard = ''
        
        # 复制文件路径到剪贴板
        pyperclip.copy(file_path)
        time.sleep(0.2)
        
        # 全选当前文本（文件名输入框通常已获得焦点）
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.1)
        
        # 粘贴路径
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.3)
        
        # 按回车确认
        pyautogui.press('enter')
        time.sleep(0.5)
        
        # 恢复剪贴板
        try:
            pyperclip.copy(original_clipboard)
        except:
            pass
        
        logger.info("文件上传完成")
        return True
        
    except Exception as e:
        logger.error(f"操作失败: {e}")
        return False


def test_find_dialog():
    """测试查找对话框"""
    print("等待5秒，请打开文件对话框...")
    print("=" * 50)
    
    for i in range(5, 0, -1):
        print(f"倒计时: {i}秒...")
        time.sleep(1)
    
    print("=" * 50)
    print("开始查找对话框...")
    
    # 查找所有对话框
    all_dialogs = []
    
    def callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            class_name = win32gui.GetClassName(hwnd)
            if class_name == '#32770' or any(kw in title for kw in ['打开', 'Open', '选择', 'Choose']):
                all_dialogs.append({
                    'hwnd': hwnd,
                    'title': title,
                    'class': class_name
                })
    
    try:
        win32gui.EnumWindows(callback, None)
    except:
        pass
    
    if all_dialogs:
        print(f"\n找到 {len(all_dialogs)} 个对话框:")
        for i, d in enumerate(all_dialogs):
            is_target = "← 目标" if d['title'] == '打开' else ""
            print(f"  [{i}] 标题: '{d['title']}' | 类: {d['class']} | 句柄: {d['hwnd']} {is_target}")
        
        # 查找目标
        target = find_file_dialog(target_title='打开')
        if target:
            print(f"\n选择的对话框: '{target['title']}' (hwnd={target['hwnd']})")
        else:
            print("\n未找到标题为'打开'的对话框")
    else:
        print("未找到任何文件对话框")


if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] == '--test':
            test_find_dialog()
        else:
            file_path = sys.argv[1]
            if os.path.exists(file_path):
                print(f"上传文件: {file_path}")
                result = select_file_in_dialog(file_path)
                print(f"结果: {'成功' if result else '失败'}")
            else:
                print(f"文件不存在: {file_path}")
    else:
        print("用法:")
        print("  python upload_handler.py <文件路径>")
        print("  python upload_handler.py --test  # 测试查找对话框")