# -*- mode: python ; coding: utf-8 -*-
import sys
import os

spec_dir = SPECPATH

assets_dir = os.path.join(spec_dir, 'assets')
if not os.path.exists(assets_dir):
    assets_dir = os.path.join(spec_dir, 'orig', 'src', 'assets')

patch_dir = os.path.join(spec_dir, 'patch')

datas = []
if os.path.exists(assets_dir):
    datas.append((assets_dir, 'assets'))
if os.path.exists(patch_dir):
    datas.append((patch_dir, 'patch'))

icon_path = os.path.join(assets_dir, 'icon.ico')
icon_arg = icon_path if os.path.exists(icon_path) else None

a = Analysis(
    [os.path.join(spec_dir, 'patcher.py')],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

if sys.platform == "darwin":
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='DELTARUNE_KR_Patcher',
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
        name='DELTARUNE_KR_Patcher',
    )
    app = BUNDLE(
        coll,
        name='DELTARUNE_KR_Patcher.app',
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
        name='DELTARUNE_KR_Patcher',
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
