"""核心数据类型：任务、播放列表、片段状态与事件。

核心通过 :class:`TaskEvent` 回调向外报告进度，回调可能来自工作线程，
接收方自行负责线程安全（GUI 侧经信号槽转发）。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from uuid import uuid4


class OutputFormat(str, Enum):
    TS = "ts"
    MP4 = "mp4"


class SegmentStatus(str, Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    DONE = "done"
    FAILED = "failed"


class EventKind(str, Enum):
    TASK_STARTED = "task_started"
    TASK_FINISHED = "task_finished"
    TASK_FAILED = "task_failed"
    SEGMENT_STATUS = "segment_status"
    PROGRESS = "progress"
    WARNING = "warning"


@dataclass(frozen=True)
class KeyInfo:
    """#EXT-X-KEY 解析结果（仅 AES-128 会出现）。"""

    uri: str
    iv: bytes | None  # None 表示未显式给出，按「媒体序列号 + 片段序」推导


@dataclass(frozen=True)
class Variant:
    """master playlist 中的一个可选码率。"""

    uri: str
    bandwidth: int | None = None
    resolution: str | None = None

    def label(self) -> str:
        parts: list[str] = []
        if self.resolution:
            parts.append(self.resolution)
        if self.bandwidth:
            parts.append(f"{self.bandwidth // 1000} kbps")
        if not parts:
            name = self.uri.rstrip("/").rsplit("/", 1)[-1]
            parts.append(name or self.uri)
        return " / ".join(parts)


@dataclass
class MasterPlaylist:
    url: str
    variants: list[Variant] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class MediaPlaylist:
    url: str
    segment_urls: list[str] = field(default_factory=list)
    durations: list[float] = field(default_factory=list)
    media_sequence: int = 0
    key: KeyInfo | None = None  # None 表示未加密
    has_endlist: bool = True
    warnings: list[str] = field(default_factory=list)

    @property
    def total_duration(self) -> float:
        return sum(self.durations)


@dataclass
class Task:
    """一次下载任务，由 GUI 或 CLI 构造后交给 downloader 执行。"""

    url: str  # 媒体播放列表绝对地址（master 时为用户所选变体）
    output_format: OutputFormat = OutputFormat.TS
    output_dir: Path | None = None  # None → 平台默认输出目录
    title: str | None = None  # 文件名（不含扩展名），None → 运行时推导
    range_start: int | None = None  # 1-based 闭区间下限
    range_end: int | None = None  # 1-based 闭区间上限
    headers: dict[str, str] = field(default_factory=dict)  # 任务级请求头覆盖
    proxy: str | None = None  # 任务级代理覆盖
    task_id: str = field(default_factory=lambda: uuid4().hex[:12])

    def __post_init__(self) -> None:
        # 统一规范化为枚举：PySide6 的 currentItemData 会把 str 枚举退化成
        # 普通字符串，调用方可能拿到 "ts"/"mp4" 而非成员
        self.output_format = OutputFormat(self.output_format)


@dataclass(frozen=True)
class ProgressStats:
    total: int
    done: int
    failed: int

    @property
    def percent(self) -> float:
        if self.total <= 0:
            return 0.0
        return self.done / self.total * 100


@dataclass(frozen=True)
class TaskEvent:
    """向外报告的事件。"""

    kind: EventKind
    message: str | None = None
    segment_index: int | None = None  # 0-based 片段序号
    status: SegmentStatus | None = None
    stats: ProgressStats | None = None


TaskEventCallback = Callable[[TaskEvent], None]
