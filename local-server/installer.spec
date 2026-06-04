# -*- mode: python ; coding: utf-8 -*-
# PyInstaller config - Installer (qingqingHelper.exe)

import sys
from pathlib import Path

block_cipher = None

# 获取需要打包的资源
chrome_ext_dir = Path('../chrome-extension').absolute()
server_exe = Path('dist/server.exe').absolute()

datas = [
    (str(chrome_ext_dir), 'chrome-extension'),
]
# 如果 server.exe 存在，打包进去
if server_exe.exists():
    datas.append((str(server_exe), '.'))

a = Analysis(
    ['installer.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'tkinter',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'tkinter.ttk',
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

installer_exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='qingqingHelper',
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