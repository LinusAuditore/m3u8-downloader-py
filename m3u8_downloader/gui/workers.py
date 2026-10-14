"""GUI 工作线程：核心的同步阻塞调用桥接为 Qt 信号（跨线程队列投递）。

工作线程只做一件事：在 QThread.run 里调用核心 API，把结果/事件经信号
发回主线程；不直接触碰任何控件。
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from m3u8_downloader.core.config import Settings
from m3u8_downloader.core.downloader import (
    DownloadController,
    DownloadResult,
    download,
    fetch_playlist,
)
from m3u8_downloader.core.http import build_http_config, create_session
from m3u8_downloader.core.merge import build_spec_from_task, merge
from m3u8_downloader.core.models import Task, TaskEvent

logger = logging.getLogger(__name__)


class ProbeWorker(QThread):
    """拉取并解析播放列表，用于判断 master / 媒体列表。"""

    succeeded = Signal(object)  # MasterPlaylist | MediaPlaylist
    failed = Signal(str)

    def __init__(
        self,
        url: str,
        settings: Settings,
        headers: dict[str, str],
        proxy: str | None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._url = url
        self._settings = settings
        self._headers = headers
        self._proxy = proxy

    def run(self) -> None:
        try:
            task = Task(url=self._url, headers=self._headers, proxy=self._proxy)
            session = create_session(build_http_config(self._settings, task))
            parsed = fetch_playlist(
                session,
                self._url,
                (self._settings.connect_timeout, self._settings.read_timeout),
            )
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.succeeded.emit(parsed)


class DownloadWorker(QThread):
    """执行一次下载任务；事件经信号转发，控制句柄供主线程暂停/取消。"""

    event_received = Signal(object)  # TaskEvent
    finished_result = Signal(object)  # DownloadResult

    def __init__(self, task: Task, settings: Settings, parent=None) -> None:
        super().__init__(parent)
        self._task = task
        self._settings = settings
        self.controller = DownloadController()

    def run(self) -> None:
        try:
            result = download(
                self._task, self._settings, self.event_received.emit, self.controller
            )
        except Exception as exc:  # 兜底，避免线程静默消亡
            logger.exception("下载线程内部异常")
            result = DownloadResult(task_dir=Path("."), error=f"内部错误：{exc}")
        self.finished_result.emit(result)


class MergeWorker(QThread):
    """合并输出（含 ffmpeg 转封装），进度按片段数回报。"""

    progress_changed = Signal(int, int)
    succeeded = Signal(object)  # Path
    failed = Signal(str)

    def __init__(self, task: Task, settings: Settings, parent=None) -> None:
        super().__init__(parent)
        self._task = task
        self._settings = settings

    def run(self) -> None:
        from m3u8_downloader.core.merge import MergeError

        try:
            spec = build_spec_from_task(self._task, self._settings)
            total = len(spec.indices)
            output = merge(
                spec,
                on_progress=lambda n: self.progress_changed.emit(n, total),
            )
        except MergeError as exc:
            self.failed.emit(str(exc))
            return
        except Exception as exc:
            self.failed.emit(f"合并失败：{exc}")
            return
        self.succeeded.emit(output)
