# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_all

datas = [
    ('templates', 'templates'),
    ('static', 'static'),
]

# Bundle mutagen and yt_dlp
hiddenimports = [
    'mutagen', 'mutagen.mp3', 'mutagen.mp4', 'mutagen.id3',
    'mutagen.flac', 'mutagen.ogg', 'mutagen.wave',
    'yt_dlp', 'flask', 'werkzeug', 'jinja2', 'click',
    'itsdangerous', 'markupsafe',
]

a = Analysis(
    ['launch.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='iPod Manager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

app = BUNDLE(
    exe,
    name='iPod Manager.app',
    icon=None,
    bundle_identifier='com.ipodmanager.app',
)
