"""平台相关路径与文件名清洗。"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

APP_DIR_NAME = "m3u8-downloader"
DATA_DIR_ENV = "M3U8_DOWNLOADER_DATA_DIR"
_FALLBACK_FILENAME = "download"
_MAX_FILENAME_LENGTH = 180
_WINDOWS_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(10)),
    *(f"LPT{i}" for i in range(10)),
}
_FORBIDDEN_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def app_data_dir() -> Path:
    """应用数据目录（配置与任务临时数据）。

    测试与 CLI 通过环境变量 ``M3U8_DOWNLOADER_DATA_DIR`` 覆盖，
    避免读写真实用户目录。
    """
    override = os.environ.get(DATA_DIR_ENV)
    if override:
        return Path(override)
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_DIR_NAME
    if sys.platform == "win32":
        root = os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local"
        return Path(root) / APP_DIR_NAME
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / APP_DIR_NAME


def tasks_root() -> Path:
    """各下载任务的临时片段与状态文件所在根目录。"""
    return app_data_dir() / "tasks"


def config_file() -> Path:
    return app_data_dir() / "config.json"


def default_output_dir(cli: bool = False) -> Path:
    """默认输出目录：CLI 为 ./output，GUI 为系统「下载」目录。"""
    if cli:
        return Path("output")
    return Path.home() / "Downloads"


def sanitize_filename(name: str, max_length: int = _MAX_FILENAME_LENGTH) -> str:
    """清洗为跨平台（重点 Windows）安全的文件名，不含扩展名约束。

    - 非法字符与控制字符替换为下划线；
    - 去掉首尾空格与点（Windows 不允许结尾为空格或点）；
    - Windows 保留设备名加下划线前缀；
    - 超长截断；清洗后为空时回退到固定名。
    """
    cleaned = _FORBIDDEN_CHARS.sub("_", name).strip(" .")
    stem = cleaned.split(".", 1)[0].upper()
    if stem in _WINDOWS_RESERVED:
        cleaned = f"_{cleaned}"
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rstrip(" .")
    return cleaned or _FALLBACK_FILENAME
