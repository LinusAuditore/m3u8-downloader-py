"""全局配置（config.json）的加载与保存。

损坏或缺失的配置一律回退到默认值，不抛异常；数值项做范围钳制。
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

from m3u8_downloader.core import paths

logger = logging.getLogger(__name__)


@dataclass
class Settings:
    concurrency: int = 6
    max_retries: int = 3
    retry_interval: float = 2.0
    connect_timeout: float = 10.0
    read_timeout: float = 30.0
    output_dir: str | None = None  # 用户固定输出目录；None → 按平台默认
    ffmpeg_path: str | None = None  # None → 从 PATH 探测
    headers: dict[str, str] = field(default_factory=dict)  # 全局默认请求头
    proxy: str | None = None


_LIMITS: dict[str, tuple[int | float, int | float]] = {
    "concurrency": (1, 64),
    "max_retries": (0, 20),
    "retry_interval": (0.0, 60.0),
    "connect_timeout": (1.0, 120.0),
    "read_timeout": (1.0, 600.0),
}
_INT_LIMITED = ("concurrency", "max_retries")
_FLOAT_LIMITED = ("retry_interval", "connect_timeout", "read_timeout")
_STR_OPTIONAL = ("output_dir", "ffmpeg_path", "proxy")


def load_settings(path: Path | None = None) -> Settings:
    file = path or paths.config_file()
    settings = Settings()
    if not file.is_file():
        return settings
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("配置文件读取失败，使用默认配置：%s", file)
        return settings
    if not isinstance(data, dict):
        logger.warning("配置文件格式异常，使用默认配置：%s", file)
        return settings

    for key, value in data.items():
        try:
            if key == "headers":
                if isinstance(value, dict):
                    settings.headers = {str(k): str(v) for k, v in value.items()}
            elif key in _STR_OPTIONAL:
                setattr(settings, key, None if value is None else str(value))
            elif key in _INT_LIMITED:
                setattr(settings, key, int(_clamp(key, int(value))))
            elif key in _FLOAT_LIMITED:
                setattr(settings, key, float(_clamp(key, float(value))))
        except (TypeError, ValueError):
            logger.warning("配置项 %s 的值无效，已忽略：%r", key, value)
    return settings


def save_settings(settings: Settings, path: Path | None = None) -> None:
    file = path or paths.config_file()
    file.parent.mkdir(parents=True, exist_ok=True)
    tmp = file.with_name(file.name + ".tmp")
    tmp.write_text(
        json.dumps(asdict(settings), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(tmp, file)


def _clamp(key: str, value: int | float) -> int | float:
    low, high = _LIMITS[key]
    return min(max(value, low), high)
