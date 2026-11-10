"""命令行入口：不依赖 GUI 的完整下载流程（探测 → 下载 → 合并）。"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from m3u8_downloader import __version__
from m3u8_downloader.core import paths
from m3u8_downloader.core.config import Settings, load_settings
from m3u8_downloader.core.downloader import (
    DownloadController,
    download,
    fetch_playlist,
)
from m3u8_downloader.core.http import HttpError, build_http_config, create_session
from m3u8_downloader.core.merge import MergeError, build_spec_from_task, merge
from m3u8_downloader.core.models import (
    EventKind,
    MasterPlaylist,
    MediaPlaylist,
    OutputFormat,
    Task,
    TaskEvent,
)
from m3u8_downloader.core.playlist import PlaylistError


class ConsoleProgress:
    """终端单行动态进度；输出整行消息前先断行，避免互相覆盖。"""

    def __init__(self, stream=None) -> None:
        self._stream = stream or sys.stdout
        self._active = False

    def status(self, text: str) -> None:
        self._stream.write("\r" + text + "\x1b[K")
        self._stream.flush()
        self._active = True

    def line(self, text: str) -> None:
        if self._active:
            self._stream.write("\n")
            self._active = False
        if text:
            self._stream.write(text + "\n")
        self._stream.flush()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m m3u8_downloader.cli",
        description=f"m3u8 视频下载器命令行 v{__version__}",
    )
    parser.add_argument("url", help="m3u8 播放列表地址（master 会列出码率供选择）")
    parser.add_argument(
        "--format", choices=["ts", "mp4"], default="ts", help="输出格式（默认 ts；mp4 需外部 ffmpeg）"
    )
    parser.add_argument("--output", help="输出目录（默认 ./output 或全局设置）")
    parser.add_argument("--title", help="输出文件名（不含扩展名）")
    parser.add_argument(
        "--variant", type=int, help="master 播放列表的码率序号（缺省选最高带宽）"
    )
    parser.add_argument("--range", metavar="START:END", help="片段区间，1-based 闭区间，如 3:10")
    parser.add_argument(
        "--header", action="append", metavar="名称:值", help="附加请求头，可重复"
    )
    parser.add_argument("--proxy", help="代理地址（http:// 或 socks5://）")
    parser.add_argument("--concurrency", type=int, help="并发数（默认 6）")
    parser.add_argument("--retries", type=int, help="每片段失败重试次数上限（默认 3）")
    parser.add_argument("--retry-interval", type=float, help="重试间隔秒数（默认 2）")
    parser.add_argument("--connect-timeout", type=float, help="连接超时秒数（默认 10）")
    parser.add_argument("--read-timeout", type=float, help="读取超时秒数（默认 30）")
    parser.add_argument("--ffmpeg", help="ffmpeg 可执行文件路径（默认探测 PATH）")
    parser.add_argument("--data-dir", help="应用数据目录（默认按平台）")
    parser.add_argument(
        "--force", action="store_true", help="有失败片段时仍强制导出不完整视频"
    )
    parser.add_argument(
        "--no-merge", action="store_true", help="只下载片段，不合并输出（调试用）"
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    args = build_arg_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.WARNING, format="%(levelname)s:%(name)s:%(message)s"
    )
    if args.data_dir:
        os.environ[paths.DATA_DIR_ENV] = str(Path(args.data_dir).expanduser())

    settings = load_settings()
    if args.concurrency is not None:
        settings.concurrency = args.concurrency
    if args.retries is not None:
        settings.max_retries = args.retries
    if args.retry_interval is not None:
        settings.retry_interval = args.retry_interval
    if args.connect_timeout is not None:
        settings.connect_timeout = args.connect_timeout
    if args.read_timeout is not None:
        settings.read_timeout = args.read_timeout
    if args.ffmpeg:
        settings.ffmpeg_path = args.ffmpeg

    headers = _parse_headers(args.header)
    if headers is None:
        return 2
    range_values = _parse_range(args.range)
    if range_values is None:
        return 2

    output_dir = (
        Path(args.output).expanduser()
        if args.output
        else (
            Path(settings.output_dir)
            if settings.output_dir
            else paths.default_output_dir(cli=True)
        )
    )
    output_format = OutputFormat(args.format)

    controller = DownloadController()
    console = ConsoleProgress()
    timeout = (settings.connect_timeout, settings.read_timeout)

    # 1. 探测播放列表（master 让用户选码率）
    probe_task = Task(url=args.url, headers=headers, proxy=args.proxy)
    try:
        session = create_session(build_http_config(settings, probe_task))
        parsed = fetch_playlist(session, args.url, timeout)
    except (HttpError, PlaylistError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2

    if isinstance(parsed, MasterPlaylist):
        variants = parsed.variants
        console.line("检测到 master 播放列表，可选码率：")
        for i, variant in enumerate(variants):
            console.line(f"  [{i}] {variant.label()}")
        index = args.variant if args.variant is not None else _default_variant(variants)
        if not 0 <= index < len(variants):
            print(
                f"错误：--variant 序号超出范围（0～{len(variants) - 1}）", file=sys.stderr
            )
            return 2
        console.line(f"已选择码率 [{index}] {variants[index].label()}")
        media_url = variants[index].uri
    else:
        media_url = args.url

    # 2. 下载
    task = Task(
        url=media_url,
        output_format=output_format,
        output_dir=output_dir,
        title=args.title,
        range_start=range_values[0],
        range_end=range_values[1],
        headers=headers,
        proxy=args.proxy,
    )

    def on_event(event: TaskEvent) -> None:
        if event.kind is EventKind.PROGRESS and event.stats is not None:
            stats = event.stats
            console.status(
                f"下载片段 {stats.done}/{stats.total}（失败 {stats.failed}）"
            )
        elif event.kind is EventKind.WARNING and event.message:
            console.line(f"警告：{event.message}")
        elif event.kind is EventKind.TASK_FAILED and event.message:
            console.line(f"错误：{event.message}")

    try:
        result = download(task, settings, on_event, controller)
    except KeyboardInterrupt:
        controller.cancel()
        console.line("")
        print("已取消：已下载片段已保留，重新运行同一命令可续传。")
        return 130

    console.line("")
    if result.cancelled:
        print("已取消：已下载片段已保留，重新运行同一命令可续传。")
        return 130
    if result.error is not None and result.failed == 0:
        print(f"错误：{result.error}", file=sys.stderr)
        return 2
    if result.failed > 0 and not args.force:
        print(f"错误：{result.error}", file=sys.stderr)
        print(
            "提示：重跑同一命令可续传缺失片段；加 --force 可强制导出不完整视频。",
            file=sys.stderr,
        )
        return 2
    if result.failed > 0:
        print(f"警告：缺失 {result.failed} 个片段，导出的视频不完整。")

    # 3. 合并
    if args.no_merge:
        print(f"片段目录：{result.task_dir}")
        return 0
    try:
        spec = build_spec_from_task(task, settings)
        output = merge(
            spec,
            on_progress=lambda n: console.status(f"合并 {n}/{len(spec.indices)}"),
        )
    except MergeError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2
    console.line("")
    print(f"完成：{output}")
    return 0


def _parse_headers(items: list[str] | None) -> dict[str, str] | None:
    if not items:
        return {}
    headers: dict[str, str] = {}
    for item in items:
        name, sep, value = item.partition(":")
        if not sep or not name.strip():
            print(f"错误：请求头格式应为「名称: 值」：{item!r}", file=sys.stderr)
            return None
        headers[name.strip()] = value.strip()
    return headers


def _parse_range(text: str | None) -> tuple[int | None, int | None] | None:
    if not text:
        return (None, None)
    start, sep, end = text.partition(":")
    if not sep or not start.isdigit() or not end.isdigit():
        print(f"错误：--range 格式应为「起始:截止」，如 3:10：{text!r}", file=sys.stderr)
        return None
    return int(start), int(end)


def _default_variant(variants) -> int:
    best = 0
    for i, variant in enumerate(variants):
        if (variant.bandwidth or 0) > (variants[best].bandwidth or 0):
            best = i
    return best


def _configure_stdio() -> None:
    """将标准输出/错误重配置为 UTF-8，并在 Windows 终端启用 VT100 控制序列。"""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (AttributeError, ValueError, OSError):
                pass
    if sys.platform == "win32":
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
            mode = ctypes.c_uint32()
            if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                kernel32.SetConsoleMode(handle, mode.value | 0x0004)
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
