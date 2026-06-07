# -*- mode: python ; coding: utf-8 -*-
# PyInstaller config - Console version (debug)

import sys
import os
from pathlib import Path

block_cipher = None

# 获取 spec 文件所在目录
SPEC_DIR = os.path.dirname(os.path.abspath(SPEC))

# 获取项目根目录
PROJECT_ROOT = os.path.abspath(os.path.join(SPEC_DIR, '..', '..'))

# 获取 extensions/qingqingHelper 目录路径
chrome_ext_dir = os.path.join(PROJECT_ROOT, 'extensions', 'qingqingHelper')

# local-server 目录
local_server_dir = os.path.join(PROJECT_ROOT, 'local-server')

# venv site-packages 路径
venv_site_packages = os.path.join(SPEC_DIR, 'venv', 'Lib', 'site-packages')

# 共享模块源文件
upload_utils_src = os.path.join(local_server_dir, 'upload_utils.py')
split_utils_src = os.path.join(local_server_dir, 'split_utils.py')

a = Analysis(
    [os.path.join(local_server_dir, 'tray_service.py')],
    pathex=[venv_site_packages, local_server_dir],
    binaries=[],
    datas=[
        (chrome_ext_dir, 'extensions/qingqingHelper'),
        (os.path.join(venv_site_packages, 'certifi', 'cacert.pem'), 'certifi'),
    ],
    hiddenimports=[
        'pystray._win32',
        'PIL._tkinter_finder',
        'PIL.Image',
        'PIL.ImageDraw',
        'flask',
        'flask_cors',
        'flask_sock',
        'jinja2',
        'werkzeug',
        'markupsafe',
        'click',
        'blinker',
        'itsdangerous',
        'colorama',
        'simple_websocket',
        'wsproto',
        'h11',
        'pyautogui',
        'pyperclip',
        'pygetwindow',
        'pyscreeze',
        'pytweening',
        'pymsgbox',
        'pyrect',
        'mouseinfo',
        'win32gui',
        'win32con',
        'win32com',
        'win32com.client',
        'win32com.shell',
        'pythoncom',
        'pywintypes',
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'cv2',
        'numpy',
        'requests',
        'urllib3',
        'certifi',
        'charset_normalizer',
        'idna',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='GoogleImageSearch_Debug',
    debug=True,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)