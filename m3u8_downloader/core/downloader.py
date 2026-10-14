"""下载编排：线程池并发、重试、暂停/取消、事件回调与断点续传对接。

:func:`download` 是同步阻塞调用，内部用线程池并发下载片段；事件回调可能
来自工作线程，接收方自行负责线程安全。片段落盘为加密原文（如有），
解密在合并阶段进行（M3），因此本模块不涉及 AES。
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from m3u8_downloader.core import playlist as playlist_mod
from m3u8_downloader.core import resume
from m3u8_downloader.core.config import Settings
from m3u8_downloader.core.http import (
    HttpError,
    Timeout,
    build_http_config,
    create_session,
    fetch_bytes,
    fetch_text,
)
from m3u8_downloader.core.models import (
    EventKind,
    MasterPlaylist,
    MediaPlaylist,
    ProgressStats,
    SegmentStatus,
    Task,
    TaskEvent,
    TaskEventCallback,
)
from m3u8_downloader.core.resume import TaskState

logger = logging.getLogger(__name__)


@dataclass
class DownloadResult:
    task_dir: Path
    total: int = 0
    done: int = 0
    failed: int = 0
    cancelled: bool = False
    key_file: Path | None = None
    error: str | None = None  # None = 正常完成（取消除外）


class DownloadController:
    """线程安全的控制句柄：暂停 / 恢复 / 取消。"""

    def __init__(self) -> None:
        self._resume_gate = threading.Event()
        self._resume_gate.set()
        self._cancelled = threading.Event()

    def pause(self) -> None:
        self._resume_gate.clear()

    def resume(self) -> None:
        self._resume_gate.set()

    def cancel(self) -> None:
        self._cancelled.set()
        self._resume_gate.set()  # 唤醒暂停中的工作线程以便退出

    def wait_if_paused(self) -> None:
        self._resume_gate.wait()

    @property
    def cancelled(self) -> bool:
        return self._cancelled.is_set()


def fetch_playlist(
    session, url: str, timeout: Timeout
) -> MasterPlaylist | MediaPlaylist:
    """拉取并解析播放列表。GUI/CLI 用它在 master 场景下让用户选码率。"""
    text = fetch_text(session, url, timeout)
    return playlist_mod.parse_playlist(text, url)


def download(
    task: Task,
    settings: Settings,
    on_event: TaskEventCallback,
    controller: DownloadController | None = None,
) -> DownloadResult:
    """执行一次下载任务（阻塞直到完成、失败或被取消）。

    失败不抛异常：通过返回值的 ``error`` 与 TASK_FAILED 事件表达；
    未完成的片段保留在任务目录，再次以同一地址调用即为续传。
    """
    controller = controller or DownloadController()
    emit = _make_emitter(on_event)
    task_dir = resume.task_dir(task.url)
    result = DownloadResult(task_dir=task_dir)
    timeout: Timeout = (settings.connect_timeout, settings.read_timeout)

    def fail(message: str) -> DownloadResult:
        result.error = message
        emit(TaskEvent(kind=EventKind.TASK_FAILED, message=message))
        return result

    emit(TaskEvent(kind=EventKind.TASK_STARTED))
    session = create_session(build_http_config(settings, task))

    # 1. 拉取并解析播放列表（续传时亦借此刷新时效性 URL）
    try:
        parsed = fetch_playlist(session, task.url, timeout)
    except (HttpError, playlist_mod.PlaylistError) as exc:
        logger.info("播放列表获取失败：%s", exc)
        return fail(f"播放列表获取失败：{exc}")
    if isinstance(parsed, MasterPlaylist):
        return fail("输入是 master 播放列表，请先选择具体码率后再下载")
    playlist = parsed

    # 2. 计算下载范围（1-based 闭区间 → 0-based 全局序号）
    total_segments = len(playlist.segment_urls)
    start_raw = task.range_start or 1
    end_raw = task.range_end or total_segments
    if start_raw < 1 or end_raw < start_raw:
        return fail("下载范围无效：起点应不小于 1，且不早于终点")
    if start_raw > total_segments:
        return fail(f"下载范围超出片段总数（{total_segments}）")
    indices = list(range(start_raw - 1, min(end_raw, total_segments)))
    result.total = len(indices)

    # 3. 续传对账：旧任务片段数与当前播放列表不一致则按新任务处理
    old_state = resume.load_state(task_dir)
    if old_state is not None and len(old_state.segment_urls) != total_segments:
        emit(
            TaskEvent(
                kind=EventKind.WARNING,
                message="已有任务的片段数与当前播放列表不一致，按新任务处理",
            )
        )
        resume.remove_task_dir(task_dir)
    done_set = resume.reconcile_done(task_dir, indices)

    # 4. 密钥（已存在且长度正确则复用，避免续传时密钥地址过期）
    key_file: Path | None = None
    if playlist.key is not None:
        key_file = resume.key_path(task_dir)
        if not (key_file.is_file() and key_file.stat().st_size == 16):
            try:
                key_data = fetch_bytes(session, playlist.key.uri, timeout)
            except HttpError as exc:
                return fail(f"密钥下载失败：{exc}")
            if len(key_data) != 16:
                return fail(f"密钥长度异常：{len(key_data)} 字节（应为 16 字节）")
            resume.write_key(task_dir, key_data)
    result.key_file = key_file

    # 5. 写状态文件（片段真实完成度以磁盘为准，结束时再刷新一次）
    http_conf = build_http_config(settings, task)
    state = TaskState(
        url=task.url,
        segment_urls=playlist.segment_urls,
        media_sequence=playlist.media_sequence,
        key_uri=playlist.key.uri if playlist.key else None,
        key_iv_hex=playlist.key.iv.hex() if playlist.key and playlist.key.iv else None,
        output_format=task.output_format.value,
        output_dir=str(task.output_dir) if task.output_dir else None,
        title=task.title,
        range_start=task.range_start,
        range_end=task.range_end,
        headers=dict(http_conf.headers),
        proxy=http_conf.proxy,
    )
    _refresh_state(state, task_dir, indices)
    resume.save_state(task_dir, state)

    # 6. 并发下载
    pending = [i for i in indices if i not in done_set]
    counters = {"done": len(done_set), "failed": 0}
    stats_lock = threading.Lock()

    def progress_event() -> TaskEvent:
        return TaskEvent(
            kind=EventKind.PROGRESS,
            stats=ProgressStats(
                total=len(indices),
                done=counters["done"],
                failed=counters["failed"],
            ),
        )

    emit(progress_event())
    # 续传时把已完成的片段状态立即报告给界面（片段网格直接显示为绿色）。
    # 注意：必须在首个 PROGRESS 之后——GUI 依赖 PROGRESS 先建立网格总数。
    for index in sorted(done_set):
        emit(
            TaskEvent(
                kind=EventKind.SEGMENT_STATUS,
                segment_index=index,
                status=SegmentStatus.DONE,
            )
        )

    if pending:
        task_queue: queue.Queue[int | None] = queue.Queue()
        for index in pending:
            task_queue.put(index)
        worker_count = max(1, min(settings.concurrency, len(pending)))
        for _ in range(worker_count):
            task_queue.put(None)  # 退出哨兵

        def worker() -> None:
            while True:
                index = task_queue.get()
                if index is None:
                    return
                controller.wait_if_paused()
                if controller.cancelled:
                    return
                url = playlist.segment_urls[index]
                attempts = 0
                while True:
                    emit(
                        TaskEvent(
                            kind=EventKind.SEGMENT_STATUS,
                            segment_index=index,
                            status=SegmentStatus.DOWNLOADING,
                        )
                    )
                    try:
                        data = fetch_bytes(session, url, timeout)
                        resume.write_segment(task_dir, index, data)
                    except (HttpError, OSError) as exc:
                        logger.debug(
                            "片段 %d 下载失败（第 %d 次尝试）：%s",
                            index,
                            attempts + 1,
                            exc,
                        )
                        if controller.cancelled:
                            return
                        if attempts < settings.max_retries:
                            attempts += 1
                            _sleep_interruptible(settings.retry_interval, controller)
                            if controller.cancelled:
                                return
                            continue
                        with stats_lock:
                            counters["failed"] += 1
                        emit(
                            TaskEvent(
                                kind=EventKind.SEGMENT_STATUS,
                                segment_index=index,
                                status=SegmentStatus.FAILED,
                            )
                        )
                        emit(progress_event())
                        break  # 回到队列取下一个片段，不退出 worker
                    else:
                        with stats_lock:
                            counters["done"] += 1
                        emit(
                            TaskEvent(
                                kind=EventKind.SEGMENT_STATUS,
                                segment_index=index,
                                status=SegmentStatus.DONE,
                            )
                        )
                        emit(progress_event())
                        break

        with ThreadPoolExecutor(
            max_workers=worker_count, thread_name_prefix="seg-dl"
        ) as pool:
            futures = [pool.submit(worker) for _ in range(worker_count)]
            for future in futures:
                future.result()

    # 7. 收尾
    if controller.cancelled:
        result.cancelled = True
        result.done, result.failed = _final_counts(state, task_dir, indices)
        resume.save_state(task_dir, state)
        emit(TaskEvent(kind=EventKind.TASK_FINISHED, message="已取消"))
        return result

    result.done, result.failed = _final_counts(state, task_dir, indices)
    resume.save_state(task_dir, state)
    if result.failed > 0:
        return fail(f"{result.failed} 个片段下载失败，可重试或使用强制导出")
    emit(TaskEvent(kind=EventKind.TASK_FINISHED))
    return result


def _final_counts(
    state: TaskState, task_dir: Path, indices: list[int]
) -> tuple[int, int]:
    """重新对账得到最终完成/失败数，并刷新状态文件中的片段状态。"""
    final_done = resume.reconcile_done(task_dir, indices)
    for index in indices:
        state.segments[str(index)] = "done" if index in final_done else "failed"
    return len(final_done), len(indices) - len(final_done)


def _refresh_state(state: TaskState, task_dir: Path, indices: list[int]) -> None:
    done = resume.reconcile_done(task_dir, indices)
    for index in indices:
        state.segments[str(index)] = "done" if index in done else "pending"


def _sleep_interruptible(seconds: float, controller: DownloadController) -> None:
    deadline = time.monotonic() + max(0.0, seconds)
    while time.monotonic() < deadline:
        if controller.cancelled:
            return
        time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))


def _make_emitter(callback: TaskEventCallback) -> Callable[[TaskEvent], None]:
    def emit(event: TaskEvent) -> None:
        try:
            callback(event)
        except Exception:
            logger.exception("任务事件回调执行异常")

    return emit
