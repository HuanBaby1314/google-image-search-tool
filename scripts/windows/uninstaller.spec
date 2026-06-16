# -*- mode: python ; coding: utf-8 -*-
# PyInstaller config - Uninstaller

import sys
import os
from pathlib import Path

block_cipher = None

# 获取 spec 文件所在目录
SPEC_DIR = os.path.dirname(os.path.abspath(SPEC))

# 获取项目根目录
PROJECT_ROOT = os.path.abspath(os.path.join(SPEC_DIR, '..', '..'))

# venv site-packages 路径
venv_site_packages = os.path.join(PROJECT_ROOT, 'local-server', 'venv', 'Lib', 'site-packages')

a = Analysis(
    [os.path.join(SPEC_DIR, '..', '..', 'local-server', 'uninstaller.py')],
    pathex=[venv_site_packages],
    binaries=[],
    datas=[],
    hiddenimports=[
        'tkinter',
        'tkinter.ttk',
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

uninstaller_exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='uninstall',
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