# -*- mode: python ; coding: utf-8 -*-
# PyInstaller config - Service program (server.exe)

import sys
from pathlib import Path

block_cipher = None

# 获取 extensions/qingqingHelper 目录路径（在项目根目录）
chrome_ext_dir = Path('../extensions/qingqingHelper').absolute()

a = Analysis(
    ['tray_service.py'],
    pathex=[],
    binaries=[],
    datas=[(str(chrome_ext_dir), 'extensions/qingqingHelper')],
    hiddenimports=[
        'pystray._win32',
        'PIL._tkinter_finder',
        'flask',
        'flask_cors',
        'pyautogui',
        'pyperclip',
        'pygetwindow',
        'win32gui',
        'win32con',
        'win32com.client',
        'tkinter',
        'tkinter.filedialog',
        'tkinter.messagebox',
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

# 服务程序
server_exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)