# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

project_root = Path(SPECPATH)
assets = project_root / "converter" / "assets"

sys.path.insert(0, str(project_root / "build"))
from version_info import build_version_info  # noqa: E402

version_info = build_version_info(project_root)

a = Analysis(
    ["converter/gui.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        (str(assets), "converter/assets"),
        (str(project_root / "config.example.json"), "."),
        *collect_data_files("tzdata"),
    ],
    hiddenimports=["tzdata", "zoneinfo"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="HHConverter",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(assets / "app.ico") if (assets / "app.ico").is_file() else None,
    version=version_info,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="HHConverter",
)
