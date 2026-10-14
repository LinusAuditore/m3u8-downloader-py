"""任务临时目录与状态文件管理（断点续传）。

设计要点（kb/plan.md 4.4）：
- 任务目录由 m3u8 地址哈希确定，重新添加同一地址即命中同一目录；
- 片段按全局序号零填充命名，写完经 ``os.replace`` 原子改名，半截文件可识别；
- 对账以磁盘为准：片段文件存在（非 .part、非空）即视为完成，state.json
  中的片段状态只是参考值，崩溃丢状态不丢数据；
- 状态文件损坏或版本不符一律按无状态处理。
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path

from m3u8_downloader.core import paths

logger = logging.getLogger(__name__)

KEY_FILENAME = "key.bin"
STATE_FILENAME = "state.json"
_STATE_VERSION = 1
_SEGMENT_EXT = ".ts"
_PART_SUFFIX = ".part"


def task_dir(url: str) -> Path:
    digest = hashlib.sha256(url.strip().encode("utf-8")).hexdigest()[:16]
    return paths.tasks_root() / digest


def segment_filename(index: int) -> str:
    return f"{index:05d}{_SEGMENT_EXT}"


def segment_path(directory: Path, index: int) -> Path:
    return directory / segment_filename(index)


def part_path(directory: Path, index: int) -> Path:
    return directory / (segment_filename(index) + _PART_SUFFIX)


def key_path(directory: Path) -> Path:
    return directory / KEY_FILENAME


def write_segment(directory: Path, index: int, data: bytes) -> None:
    _atomic_write(part_path(directory, index), segment_path(directory, index), data)


def write_key(directory: Path, data: bytes) -> None:
    _atomic_write(
        key_path(directory).with_name(KEY_FILENAME + _PART_SUFFIX),
        key_path(directory),
        data,
    )


def remove_task_dir(directory: Path) -> None:
    shutil.rmtree(directory, ignore_errors=True)


@dataclass
class TaskState:
    """state.json 的内存形态，记录播放列表快照与任务配置。"""

    url: str
    segment_urls: list[str] = field(default_factory=list)
    media_sequence: int = 0
    key_uri: str | None = None
    key_iv_hex: str | None = None
    output_format: str = "ts"
    output_dir: str | None = None
    title: str | None = None
    range_start: int | None = None
    range_end: int | None = None
    headers: dict[str, str] = field(default_factory=dict)
    proxy: str | None = None
    segments: dict[str, str] = field(default_factory=dict)  # 序号→状态，参考值
    version: int = _STATE_VERSION


def state_path(directory: Path) -> Path:
    return directory / STATE_FILENAME


def save_state(directory: Path, state: TaskState) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    file = state_path(directory)
    tmp = file.with_name(STATE_FILENAME + ".tmp")
    tmp.write_text(
        json.dumps(asdict(state), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    os.replace(tmp, file)


def load_state(directory: Path) -> TaskState | None:
    """读取状态文件；缺失、损坏或版本不符返回 None。"""
    file = state_path(directory)
    if not file.is_file():
        return None
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("任务状态文件损坏，按无状态处理：%s", file)
        return None
    if not isinstance(data, dict) or data.get("version") != _STATE_VERSION:
        logger.warning("任务状态文件版本不符，按无状态处理：%s", file)
        return None
    try:
        return TaskState(
            url=str(data["url"]),
            segment_urls=[str(u) for u in data.get("segment_urls", [])],
            media_sequence=int(data.get("media_sequence", 0)),
            key_uri=data.get("key_uri"),
            key_iv_hex=data.get("key_iv_hex"),
            output_format=str(data.get("output_format", "ts")),
            output_dir=data.get("output_dir"),
            title=data.get("title"),
            range_start=data.get("range_start"),
            range_end=data.get("range_end"),
            headers={str(k): str(v) for k, v in (data.get("headers") or {}).items()},
            proxy=data.get("proxy"),
            segments={str(k): str(v) for k, v in (data.get("segments") or {}).items()},
            version=int(data["version"]),
        )
    except (KeyError, TypeError, ValueError):
        logger.warning("任务状态文件字段异常，按无状态处理：%s", file)
        return None


def find_resumable(url: str) -> TaskState | None:
    """启动任务前查询：该地址是否存在可续传的历史任务。"""
    return load_state(task_dir(url))


def reconcile_done(directory: Path, indices: Iterable[int]) -> set[int]:
    """以磁盘为准对账；同时清理可能残留的 .part 半截文件。"""
    done: set[int] = set()
    for index in indices:
        final = segment_path(directory, index)
        if final.is_file() and final.stat().st_size > 0:
            done.add(index)
        else:
            part_path(directory, index).unlink(missing_ok=True)
    return done


def _atomic_write(tmp: Path, final: Path, data: bytes) -> None:
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_bytes(data)
    os.replace(tmp, final)
