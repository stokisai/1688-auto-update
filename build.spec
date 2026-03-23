# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 打包配置文件
用于将 AI绘画工具 打包成 Windows EXE
"""

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# 项目根目录
PROJECT_DIR = os.path.dirname(os.path.abspath(SPEC))

# 收集 PySide6 数据文件
pyside6_datas = collect_data_files('PySide6')
qtawesome_datas = collect_data_files('qtawesome')
qt_material_datas = collect_data_files('qt_material')

# 收集其他依赖的数据文件
datas = pyside6_datas + qtawesome_datas + qt_material_datas + [
    # 项目资源文件
    (os.path.join(PROJECT_DIR, 'assets'), 'assets'),
    (os.path.join(PROJECT_DIR, 'config'), 'config'),
    (os.path.join(PROJECT_DIR, 'license'), 'license'),
    (os.path.join(PROJECT_DIR, 'utils'), 'utils'),
    (os.path.join(PROJECT_DIR, 'version.json'), '.'),
]

# 如果 user_config.json 存在则包含
user_config = os.path.join(PROJECT_DIR, 'user_config.json')
if os.path.exists(user_config):
    datas.append((user_config, '.'))

# 隐藏导入（PyInstaller 可能检测不到的模块）
hiddenimports = [
    'PySide6',
    'PySide6.QtWidgets',
    'PySide6.QtCore',
    'PySide6.QtGui',
    'qt_material',
    'qtawesome',
    'selenium',
    'selenium.webdriver',
    'selenium.webdriver.chrome',
    'selenium.webdriver.chrome.service',
    'selenium.webdriver.chrome.options',
    'selenium.webdriver.common.by',
    'selenium.webdriver.support.ui',
    'selenium.webdriver.support.expected_conditions',
    'bs4',
    'lxml',
    'requests',
    'aiohttp',
    'click',
    'rich',
    'rich.console',
    'rich.table',
    'dashscope',
    'openai',
    'google.cloud.vision',
    'google.genai',
    'license',
    'license.device_fingerprint',
    'license.license_manager',
    'cv2',
    'numpy',
    'PIL',
    'oss2',
]

# 排除不需要的模块（减小体积）
excludes = [
    'matplotlib',
    'pandas',
    'scipy',
    'tkinter',
    'customtkinter',
    'unittest',
]

a = Analysis(
    [os.path.join(PROJECT_DIR, 'main.py')],
    pathex=[PROJECT_DIR],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AI_Drawing_Tool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # False = 不显示控制台窗口（GUI模式）
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(PROJECT_DIR, 'assets', 'logo.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AI_Drawing_Tool',
)
