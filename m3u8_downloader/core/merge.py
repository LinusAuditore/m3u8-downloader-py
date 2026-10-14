"""合并输出：TS 顺序拼接；MP4 经外部 ffmpeg 流复制转封装（不重编码）。

- 片段逐个读取（加密流在此解密），不把整个视频驻留内存；
- 输出先写 .part 临时文件，成功后原子改名；
- ffmpeg 通过 stdin 喂 mpegts 流（``-i pipe:0``），stderr 用独立线程收取
  避免管道写满死锁。
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from m3u8_downloader.core import crypto, paths, resume
from m3u8_downloader.core.config import Settings
from m3u8_downloader.core.models import KeyInfo, OutputFormat, Task

logger = logging.getLogger(__name__)

_FFMPEG_WAIT_TIMEOUT = 300.0


class MergeError(Exception):
    """合并失败（缺 ffmpeg、片段/密钥缺失、ffmpeg 报错等）。"""


@dataclass(frozen=True)
class MergeSpec:
    """一次合并的全部输入。indices 为待合并片段的全局序号（升序）。"""

    task_dir: Path
    indices: list[int]
    output_path: Path
    output_format: OutputFormat
    key_file: Path | None = None
    key_info: KeyInfo | None = None
    media_sequence: int = 0
    ffmpeg_path: str | None = None


def find_ffmpeg(explicit: str | None = None) -> str | None:
    """定位 ffmpeg：优先用户设置路径，否则探测 PATH。"""
    if explicit:
        return explicit if Path(explicit).is_file() else None
    return shutil.which("ffmpeg")


def build_spec_from_task(task: Task, settings: Settings) -> MergeSpec:
    """按任务目录现状组装合并规格（只包含已完成的片段）。"""
    task_dir = resume.task_dir(task.url)
    state = resume.load_state(task_dir)
    if state is None:
        raise MergeError("没有可用的任务记录，无法合并（请先下载）")

    total = len(state.segment_urls)
    start = max((task.range_start or 1) - 1, 0)
    end = min(task.range_end or total, total)
    indices = sorted(resume.reconcile_done(task_dir, range(start, end)))
    if not indices:
        raise MergeError("没有已完成的片段，无法合并")

    key_file: Path | None = None
    key_info: KeyInfo | None = None
    if state.key_uri:
        key_file = resume.key_path(task_dir)
        if not (key_file.is_file() and key_file.stat().st_size == 16):
            raise MergeError("密钥文件缺失或无效，无法解密合并")
        key_info = KeyInfo(
            uri=state.key_uri,
            iv=bytes.fromhex(state.key_iv_hex) if state.key_iv_hex else None,
        )

    output_dir = task.output_dir or (
        Path(settings.output_dir)
        if settings.output_dir
        else paths.default_output_dir(cli=True)
    )
    title = task.title or state.title or _title_from_url(task.url)
    ext = ".mp4" if task.output_format is OutputFormat.MP4 else ".ts"
    output_path = _unique_path(output_dir / (paths.sanitize_filename(title) + ext))

    return MergeSpec(
        task_dir=task_dir,
        indices=indices,
        output_path=output_path,
        output_format=task.output_format,
        key_file=key_file,
        key_info=key_info,
        media_sequence=state.media_sequence,
        ffmpeg_path=settings.ffmpeg_path,
    )


def merge(
    spec: MergeSpec, on_progress: Callable[[int], None] | None = None
) -> Path:
    """执行合并，返回输出文件路径。"""
    if not spec.indices:
        raise MergeError("没有可合并的片段")

    key_bytes: bytes | None = None
    if spec.key_file is not None:
        if spec.key_info is None:
            raise MergeError("缺少密钥参数，无法解密")
        if not (spec.key_file.is_file() and spec.key_file.stat().st_size == 16):
            raise MergeError("密钥文件缺失或无效，无法解密")
        key_bytes = spec.key_file.read_bytes()
        if spec.key_info.iv is not None and len(spec.key_info.iv) != 16:
            raise MergeError("IV 长度异常（应为 16 字节）")

    spec.output_path.parent.mkdir(parents=True, exist_ok=True)
    if spec.output_format is OutputFormat.MP4:
        return _merge_mp4(spec, key_bytes, on_progress)
    return _merge_ts(spec, key_bytes, on_progress)


def _iter_segment_data(
    spec: MergeSpec, key_bytes: bytes | None, on_progress: Callable[[int], None] | None
):
    """按序产出片段数据（需要时解密）；进度在产出前回调。"""
    processed = 0
    for index in spec.indices:
        path = resume.segment_path(spec.task_dir, index)
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise MergeError(f"读取片段 {index} 失败：{exc}") from exc
        if key_bytes is not None:
            iv = crypto.segment_iv(spec.key_info, spec.media_sequence, index)
            data = crypto.decrypt_segment(data, key_bytes, iv)
        processed += 1
        if on_progress is not None:
            on_progress(processed)
        yield data


def _merge_ts(
    spec: MergeSpec, key_bytes: bytes | None, on_progress: Callable[[int], None] | None
) -> Path:
    tmp = _part_output(spec.output_path)
    try:
        with tmp.open("wb") as out:
            for data in _iter_segment_data(spec, key_bytes, on_progress):
                out.write(data)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    os.replace(tmp, spec.output_path)
    return spec.output_path


def _merge_mp4(
    spec: MergeSpec, key_bytes: bytes | None, on_progress: Callable[[int], None] | None
) -> Path:
    ffmpeg = find_ffmpeg(spec.ffmpeg_path)
    if ffmpeg is None:
        hint = (
            f"（设置的路径无效：{spec.ffmpeg_path}）"
            if spec.ffmpeg_path
            else "（PATH 中未找到，可在设置中指定路径）"
        )
        raise MergeError(f"未找到 ffmpeg，无法转封装 MP4{hint}")

    tmp = _part_output(spec.output_path)
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        "pipe:0",
        "-map",
        "0",
        "-c",
        "copy",
        "-bsf:a",
        "aac_adtstoasc",
        "-movflags",
        "+faststart",
        "-f",
        "mp4",
        "-y",
        str(tmp),
    ]
    logger.debug("ffmpeg 命令：%s", " ".join(command))
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    assert process.stdin is not None and process.stderr is not None
    stderr_chunks: list[bytes] = []
    stderr_reader = threading.Thread(
        target=lambda: stderr_chunks.append(process.stderr.read()), daemon=True
    )
    stderr_reader.start()

    try:
        for data in _iter_segment_data(spec, key_bytes, on_progress):
            try:
                process.stdin.write(data)
            except BrokenPipeError as exc:
                raise MergeError(
                    f"ffmpeg 提前退出：{_stderr_text(stderr_chunks)}"
                ) from exc
            except OSError as exc:
                raise MergeError(f"向 ffmpeg 写入失败：{exc}") from exc
        process.stdin.close()
        return_code = process.wait(timeout=_FFMPEG_WAIT_TIMEOUT)
    except BaseException:
        process.kill()
        process.wait(timeout=10)
        tmp.unlink(missing_ok=True)
        raise

    stderr_reader.join(timeout=5)
    if return_code != 0:
        tmp.unlink(missing_ok=True)
        raise MergeError(
            f"ffmpeg 转封装失败（退出码 {return_code}）：{_stderr_text(stderr_chunks)}"
        )
    os.replace(tmp, spec.output_path)
    return spec.output_path


def _part_output(final: Path) -> Path:
    return final.with_name(final.name + ".part")


def _stderr_text(chunks: list[bytes]) -> str:
    return b"".join(chunks).decode("utf-8", errors="replace").strip() or "无错误输出"


def _title_from_url(url: str) -> str:
    stem = Path(urlsplit(url).path).stem
    return stem or time.strftime("%Y%m%d_%H%M%S")


def _unique_path(path: Path) -> Path:
    """目标文件已存在时追加序号，避免覆盖。"""
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    for k in range(1, 1000):
        candidate = path.with_name(f"{stem} ({k}){suffix}")
        if not candidate.exists():
            return candidate
    return path
