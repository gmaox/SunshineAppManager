# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 打包配置：仅保存 cover 与 apps.json 时会临时请求管理员权限，其余以普通用户运行。

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'PyQt5',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        'PIL.ImageFont',
        'PIL.ImageTk',
        'win32com',
        'win32com.client',
        'pythoncom',
        'win32api',
        'win32con',
        'win32security',
        'win32process',
        'win32gui',
        'winreg',
        'psutil',
        'vdf',
        'colorthief',
        'icoextract',
        'requests',
        'urllib3',
        'tkinter',
        'configparser',
        'ctypes',
        'copy',
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
    name='SunshineAppManager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=fav.ico,  # 可改为 'icon.ico' 若有图标
)
