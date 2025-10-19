# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

# SPECPATH is the directory containing this .spec file (macos/)
# Repository root is one level up
repo_root = os.path.dirname(SPECPATH)
project_dir = os.path.join(repo_root, 'tvhplayer')

# Get version from environment variable (set by CI/CD or manually)
VERSION = os.environ.get('VERSION', '1.0.0')
# Remove 'v' prefix if present (e.g., v4.0.1 -> 4.0.1)
if VERSION.startswith('v'):
    VERSION = VERSION[1:]

# Define paths relative to repository root
icons_dir = os.path.join(repo_root, 'icons')

# Collect all icon files
icon_files = []
if os.path.exists(icons_dir):
    for file in os.listdir(icons_dir):
        if file.endswith(('.svg', '.png', '.ico')):
            icon_files.append((os.path.join(icons_dir, file), 'icons'))

# Collect PyQt6 data files and binaries
# Filter out unnecessary data to reduce size
pyqt6_datas = collect_data_files('PyQt6', include_py_files=False)
# Exclude QML/QtQuick files (not used, saves ~15 MB)
pyqt6_datas = [(src, dst) for src, dst in pyqt6_datas if 'qml' not in src.lower()]
pyqt6_binaries = collect_dynamic_libs('PyQt6')

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
        # Exclude unnecessary Python modules
        'unittest',
        'doctest',
        'pdb',
        'pydoc',
        'http.server',
        'sqlite3',
        'test',
    ],
    noarchive=False,
)

# Note: VLC plugins are NOT bundled to save ~133 MB (like Windows)
# The application will use the system-installed VLC
# Users need VLC installed on their system for video playback to work

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,        # Include binaries in the exe
    a.zipfiles,        # Include zipfiles in the exe
    a.datas,          # Include datas in the exe
    name='TVHplayer',
    debug=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# Create the app bundle
app = BUNDLE(
    exe,
    name='TVHplayer.app',
    icon=os.path.join(repo_root, 'icons', 'tvhplayer.png'),
    bundle_identifier='com.tvhplayer.app',
    info_plist={
        'CFBundleName': 'TVHplayer',
        'CFBundleDisplayName': 'TVHplayer',
        'CFBundleGetInfoString': "TVHplayer",
        'CFBundleIdentifier': "com.tvhplayer.app",
        'CFBundleVersion': VERSION,
        'CFBundleShortVersionString': VERSION,
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '10.13.0',
        'NSRequiresAquaSystemAppearance': False,
        'VLCPluginPath': '@executable_path/../Resources/vlc/plugins',
        'NSAppleEventsUsageDescription': 'TVHplayer needs to control system features.',
        'NSCameraUsageDescription': 'TVHplayer does not use the camera.',
        'NSMicrophoneUsageDescription': 'TVHplayer does not use the microphone.',
    },
)
