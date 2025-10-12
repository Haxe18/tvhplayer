# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

# SPECPATH is the directory containing this .spec file (windows/)
# Repository root is one level up
repo_root = os.path.dirname(SPECPATH)
project_dir = os.path.join(repo_root, 'tvhplayer')

# Define paths relative to repository root
icons_dir = os.path.join(repo_root, 'icons')

# Collect all icon files
icon_files = []
if os.path.exists(icons_dir):
    for file in os.listdir(icons_dir):
        if file.endswith(('.svg', '.png', '.ico')):
            icon_files.append((os.path.join(icons_dir, file), 'icons'))

block_cipher = None

# Collect PyQt6 data files and binaries
# Filter out unnecessary data to reduce size
pyqt6_datas = collect_data_files('PyQt6', include_py_files=False)
# Exclude QML/QtQuick files (not used, saves ~15 MB)
pyqt6_datas = [(src, dst) for src, dst in pyqt6_datas if 'qml' not in src.lower()]
# Keep all translations (user wants all languages)
pyqt6_binaries = collect_dynamic_libs('PyQt6')

# Filter out unnecessary Qt6 DLLs to reduce size (saves ~40-60 MB)
excluded_dlls = [
    'opengl32sw.dll',  # Software OpenGL renderer (20 MB)
    'd3dcompiler_47.dll',  # DirectX shader compiler (4 MB)
    'qt6designer', 'qt6help', 'qt6bluetooth', 'qt6sensors', 'qt6serialport',
    'qt6multimedia', 'qt6remoteobjects', 'qt6positioning', 'qt6printsupport',
    'qt6network', 'qt6dbus', 'qt6sql', 'qt6test', 'qt6websockets', 'qt6xml',
    'qt6quick', 'qt6qml', 'qt6labs',  # QML/QtQuick modules (~20 MB)
]
pyqt6_binaries = [(src, dest) for src, dest in pyqt6_binaries
                  if not any(excl in src.lower() for excl in excluded_dlls)]

a = Analysis(
    [os.path.join(repo_root, 'tvhplayer', 'tvhplayer.py')],
    pathex=[project_dir],
    binaries=pyqt6_binaries,
    datas=icon_files + pyqt6_datas,
    hiddenimports=[
        'vlc',
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.QtSvg',
        'requests',
        'certifi'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unnecessary PyQt6 modules
        'PyQt6.QtNetwork',
        'PyQt6.QtDBus',
        'PyQt6.QtSql',
        'PyQt6.QtTest',
        'PyQt6.QtXml',
        'PyQt6.QtBluetooth',
        'PyQt6.QtMultimedia',
        'PyQt6.QtWebEngine',
        'PyQt6.QtWebEngineCore',
        'PyQt6.QtWebEngineWidgets',
        'PyQt6.QtWebSockets',
        'PyQt6.QtPositioning',
        'PyQt6.QtSensors',
        'PyQt6.QtSerialPort',
        'PyQt6.QtPrintSupport',
        'PyQt6.QtDesigner',
        'PyQt6.QtHelp',
        'PyQt6.QtOpenGL',
        'PyQt6.QtQml',
        'PyQt6.QtQuick',
        # Exclude unnecessary Python modules (keep json and xml)
        # Note: tkinter must be included because Pillow (PIL) optionally imports it
        'unittest',
        'doctest',
        'pdb',
        'pydoc',
        'http.server',
        'sqlite3',
        'test',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# PyQt6 has better plugin handling, no filtering needed

# Note: VLC plugins are NOT bundled to save ~133 MB
# The application will use the system-installed VLC (like previous versions)
# Users need VLC installed on their system for video playback to work

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Use --onedir mode to create exe + _internal directory
# This is smaller and faster to start than --onefile
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # Binaries go in _internal directory
    name='tvhplayer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(repo_root, 'icons', 'tvhplayer.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='tvhplayer',
)
