# -*- mode: python ; coding: utf-8 -*-
# PyInstaller config - Installer (qingqingHelper.exe)

import sys
import os
from pathlib import Path

block_cipher = None

# 获取 spec 文件所在目录
SPEC_DIR = os.path.dirname(os.path.abspath(SPEC))

# 获取需要打包的资源
chrome_ext_dir = os.path.join(SPEC_DIR, '..', '..', 'extensions', 'qingqingHelper')
server_exe = os.path.join(SPEC_DIR, 'dist', 'server.exe')
uninstall_exe = os.path.join(SPEC_DIR, 'dist', 'uninstall.exe')

# 获取项目根目录
PROJECT_ROOT = os.path.abspath(os.path.join(SPEC_DIR, '..', '..'))

# venv site-packages 路径
venv_site_packages = os.path.join(PROJECT_ROOT, 'local-server', 'venv', 'Lib', 'site-packages')

datas = [
    (chrome_ext_dir, 'extensions/qingqingHelper'),
]
# 如果 server.exe 存在，打包进去
if os.path.exists(server_exe):
    datas.append((server_exe, '.'))
# 如果 uninstall.exe 存在，打包进去
if os.path.exists(uninstall_exe):
    datas.append((uninstall_exe, '.'))

a = Analysis(
    [os.path.join(SPEC_DIR, '..', '..', 'local-server', 'installer.py')],
    pathex=[venv_site_packages],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'shutil',
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