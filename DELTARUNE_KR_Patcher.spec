# -*- mode: python ; coding: utf-8 -*-
import sys
import os

spec_dir = SPECPATH

assets_dir = os.path.join(spec_dir, 'assets')
if not os.path.exists(assets_dir):
    candidates = [
        os.path.join(spec_dir, 'orig', 'src', 'assets'),
        os.path.join(spec_dir, 'src', 'assets'),
    ]
    for cand in candidates:
        if os.path.exists(cand):
            assets_dir = cand
            break

patch_dir = os.path.join(spec_dir, 'patch')
if not os.path.exists(patch_dir):
    candidates = [
        os.path.join(spec_dir, 'orig', 'src', 'patch'),
        os.path.join(spec_dir, 'src', 'patch'),
    ]
    for cand in candidates:
        if os.path.exists(cand):
            patch_dir = cand
            break

datas = []
if os.path.exists(assets_dir):
    datas.append((assets_dir, 'assets'))
if os.path.exists(patch_dir):
    datas.append((patch_dir, 'patch'))

icon_path = os.path.join(assets_dir, 'icon.ico')
icon_arg = icon_path if os.path.exists(icon_path) else None

# pip freeze 및 설치된 패키지의 top_level 모듈 자동 추출 후 필수 모듈 제외 전원 excludes 등록
keep_pkgs = {
    'pyside6', 'pyside6_essentials', 'pyside6_addons', 'shiboken6',
    'pyxdelta', 'pyinstaller', 'pyinstaller-hooks-contrib', 'altgraph',
}

pip_excludes = set()
try:
    import importlib.metadata
    for dist in importlib.metadata.distributions():
        name = dist.metadata.get('Name')
        if name and name.lower() not in keep_pkgs:
            pip_excludes.add(name)
            top_level = dist.read_text('top_level.txt')
            if top_level:
                for mod in top_level.splitlines():
                    mod = mod.strip()
                    if mod and mod.lower() not in keep_pkgs:
                        pip_excludes.add(mod)
except Exception:
    pass

static_excludes = [
    # Unused Python stdlib modules
    'tkinter', 'unittest', 'doctest', 'pydoc', 'xmlrpc', 'email', 'http',
    'ftplib', 'smtplib', 'sqlite3', 'multiprocessing', 'asyncio', 'concurrent',
    'xml', 'html', 'curses', 'dbm', 'gdbm', 'lzma', 'bz2', 'csv', 'ctypes.test',
    
    # Unused PySide6 submodules & Qt bindings
    'PySide6.QtNetwork', 'PySide6.QtDBus', 'PySide6.QtPdf', 'PySide6.QtOpenGL',
    'PySide6.QtSvg', 'PySide6.QtSql', 'PySide6.QtXml', 'PySide6.QtTest',
    'PySide6.QtPrintSupport', 'PySide6.QtQml', 'PySide6.QtQuick',
    'PySide6.QtDesigner', 'PySide6.QtHelp', 'PySide6.QtUiTools',
    'PySide6.QtSensors', 'PySide6.QtPositioning', 'PySide6.QtWebChannel',
    'PySide6.QtWebEngineCore', 'PySide6.QtWebSockets', 'PySide6.QtBluetooth',
    'PySide6.QtNfc', 'PySide6.QtSpatialAudio', 'PySide6.QtMultimedia',
]

excludes = list(pip_excludes.union(set(static_excludes)))

a = Analysis(
    [os.path.join(spec_dir, 'patcher.py')],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=['winreg'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=2,
)
pyz = PYZ(a.pure)

if sys.platform == "darwin":
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='델타룬 한글 패처',
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
        icon=icon_arg,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name='델타룬 한글 패처',
    )
    app = BUNDLE(
        coll,
        name='델타룬 한글 패처.app',
        icon=icon_arg,
        bundle_identifier=None,
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name='델타룬 한글 패처',
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
        icon=icon_arg,
    )
