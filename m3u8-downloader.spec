# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置（onedir）。

构建：pyinstaller m3u8-downloader.spec --noconfirm
产物：dist/m3u8-downloader/（含 GUI 主程序 m3u8-downloader 与命令行 m3u8-downloader-cli；
macOS 下另有 m3u8-downloader.app）。
注意：GUI 与 CLI 是两个独立入口（main.py / main-cli.py），各自 Analysis——
CLI 不打包 PySide6。.spec 纳入版本管理（AGENTS.md「版本管理」）。
"""

import sys

a_gui = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
)
pyz_gui = PYZ(a_gui.pure)

gui = EXE(
    pyz_gui,
    a_gui.scripts,
    [],
    exclude_binaries=True,
    name="m3u8-downloader",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=None,
)

a_cli = Analysis(
    ["main-cli.py"],
    pathex=["."],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "PySide6"],
    noarchive=False,
)
pyz_cli = PYZ(a_cli.pure)

cli = EXE(
    pyz_cli,
    a_cli.scripts,
    [],
    exclude_binaries=True,
    name="m3u8-downloader-cli",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    icon=None,
)

coll = COLLECT(
    gui,
    cli,
    a_gui.binaries,
    a_gui.datas,
    a_cli.binaries,
    a_cli.datas,
    strip=False,
    upx=False,
    name="m3u8-downloader",
)

# macOS 额外产出可双击的 .app；Windows/Linux 仅用 COLLECT 目录
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="m3u8-downloader.app",
        icon=None,
        bundle_identifier=None,
    )
