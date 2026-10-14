"""m3u8 播放列表解析。

只做语法层解析与边界检测，不做网络请求；所有地址解析为绝对 URL。
边界行为对应 kb/requirements.md 第 6 节的确认结果：
多 KEY / #EXT-X-MAP / #EXT-X-BYTERANGE 报不支持；缺 #EXT-X-ENDLIST 记警告。
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

from m3u8_downloader.core.models import KeyInfo, MasterPlaylist, MediaPlaylist, Variant


class PlaylistError(Exception):
    """m3u8 内容无法解析、为空或地址无效。"""


class UnsupportedFeatureError(PlaylistError):
    """播放列表使用了 v1 明确不支持的特性。"""


class UnsupportedEncryptionError(PlaylistError):
    """非标准 AES-128 加密（如 SAMPLE-AES / DRM）。本工具不提供任何绕过。"""


_EXTINF_RE = re.compile(r"#EXTINF:\s*(?P<duration>\d+(?:\.\d+)?)")


def resolve_url(base_url: str, target: str) -> str:
    """以播放列表地址为基准把片段/密钥地址解析为绝对 URL。"""
    target = target.strip()
    if not target:
        raise PlaylistError("地址为空，无法解析")
    try:
        resolved = urljoin(base_url, target)
    except ValueError as exc:
        raise PlaylistError(f"地址无法解析：{target!r}") from exc
    if not resolved:
        raise PlaylistError(f"地址无法解析：{target!r}")
    return resolved


def parse_playlist(text: str, base_url: str) -> MasterPlaylist | MediaPlaylist:
    """按内容自动分发：含 STREAM-INF 视为 master，否则视为媒体播放列表。"""
    if "#EXT-X-STREAM-INF" in text:
        return parse_master(text, base_url)
    return parse_media(text, base_url)


def parse_master(text: str, base_url: str) -> MasterPlaylist:
    playlist = MasterPlaylist(url=base_url)
    pending_attrs: dict[str, str] | None = None

    for line in _iter_lines(text):
        if line.startswith("#EXT-X-STREAM-INF:"):
            pending_attrs = _split_attributes(line.split(":", 1)[1])
            continue
        if line.startswith("#"):
            continue
        if pending_attrs is None:
            playlist.warnings.append(f"忽略 STREAM-INF 之前的地址行：{line}")
            continue
        bandwidth: int | None = None
        for name in ("AVERAGE-BANDWIDTH", "BANDWIDTH"):
            value = pending_attrs.get(name, "")
            if value.isdigit():
                bandwidth = int(value)
                break
        playlist.variants.append(
            Variant(
                uri=resolve_url(base_url, line),
                bandwidth=bandwidth,
                resolution=pending_attrs.get("RESOLUTION"),
            )
        )
        pending_attrs = None

    if pending_attrs is not None:
        playlist.warnings.append("#EXT-X-STREAM-INF 之后没有跟随地址行，已忽略")
    if not playlist.variants:
        raise PlaylistError("master 播放列表中没有可用的码率项")
    return playlist


def parse_media(text: str, base_url: str) -> MediaPlaylist:
    playlist = MediaPlaylist(url=base_url)
    key_lines: list[dict[str, str]] = []
    pending_duration: float | None = None
    saw_endlist = False

    for line in _iter_lines(text):
        if not line.startswith("#"):
            playlist.segment_urls.append(resolve_url(base_url, line))
            playlist.durations.append(
                pending_duration if pending_duration is not None else 0.0
            )
            pending_duration = None
            continue

        upper = line.upper()
        if upper.startswith("#EXTINF:"):
            pending_duration = _parse_duration(line)
        elif upper.startswith("#EXT-X-MEDIA-SEQUENCE:"):
            playlist.media_sequence = _parse_int_after(line, "#EXT-X-MEDIA-SEQUENCE:")
        elif upper.startswith("#EXT-X-KEY:"):
            key_lines.append(_split_attributes(line.split(":", 1)[1]))
        elif upper.startswith("#EXT-X-MAP"):
            raise UnsupportedFeatureError("不支持包含 #EXT-X-MAP（fMP4 初始化段）的播放列表")
        elif upper.startswith("#EXT-X-BYTERANGE"):
            raise UnsupportedFeatureError("不支持包含 #EXT-X-BYTERANGE 的播放列表")
        elif upper.startswith("#EXT-X-ENDLIST"):
            saw_endlist = True

    playlist.has_endlist = saw_endlist
    if not saw_endlist:
        playlist.warnings.append(
            "播放列表缺少 #EXT-X-ENDLIST，可能为直播流；仅下载当前片段快照"
        )
    playlist.key = _resolve_key(key_lines, base_url)

    if not playlist.segment_urls:
        raise PlaylistError("播放列表中没有找到任何视频片段")
    return playlist


def _iter_lines(text: str):
    """按行产出非空行，兼容 CRLF 与行首尾空白。"""
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw.strip()
        if line:
            yield line


def _split_attributes(raw: str) -> dict[str, str]:
    """把 `ATTR=VALUE,ATTR="V,1"` 形式的属性串切成字典，引号内的逗号不切分。"""
    attributes: dict[str, str] = {}
    item_chars: list[str] = []
    in_quotes = False

    def flush() -> None:
        item = "".join(item_chars).strip()
        item_chars.clear()
        if not item or "=" not in item:
            return
        name, _, value = item.partition("=")
        name = name.strip().upper()
        value = value.strip()
        if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
            value = value[1:-1]
        if name:
            attributes[name] = value

    for ch in raw:
        if ch == '"':
            in_quotes = not in_quotes
            item_chars.append(ch)
        elif ch == "," and not in_quotes:
            flush()
        else:
            item_chars.append(ch)
    flush()
    return attributes


def _resolve_key(key_lines: list[dict[str, str]], base_url: str) -> KeyInfo | None:
    unique: list[dict[str, str]] = []
    for attrs in key_lines:
        if attrs not in unique:
            unique.append(attrs)
    if not unique:
        return None
    if len(unique) > 1:
        raise UnsupportedFeatureError("播放列表包含多个不同的 #EXT-X-KEY，暂不支持多密钥")

    attrs = unique[0]
    method = attrs.get("METHOD", "").upper()
    if method in ("", "NONE"):
        return None
    if method != "AES-128":
        raise UnsupportedEncryptionError(f"不支持该加密方式：METHOD={method}")
    uri = attrs.get("URI")
    if not uri:
        raise PlaylistError("#EXT-X-KEY 缺少密钥地址 URI")
    keyformat = attrs.get("KEYFORMAT")
    if keyformat and keyformat.strip().lower() != "identity":
        raise UnsupportedEncryptionError(f"不支持该密钥格式：KEYFORMAT={keyformat}")
    return KeyInfo(uri=resolve_url(base_url, uri), iv=_parse_iv(attrs.get("IV")))


def _parse_iv(raw: str | None) -> bytes | None:
    """IV 按 RFC 8216 解为 16 字节大端；修正参考项目把 IV 当文本编码的缺陷。"""
    if raw is None:
        return None
    try:
        return int(raw, 16).to_bytes(16, "big")
    except (ValueError, OverflowError) as exc:
        raise PlaylistError(f"IV 不是合法的十六进制值：{raw!r}") from exc


def _parse_duration(line: str) -> float:
    match = _EXTINF_RE.match(line)
    if not match:
        raise PlaylistError(f"#EXTINF 时长无法解析：{line!r}")
    return float(match.group("duration"))


def _parse_int_after(line: str, prefix: str) -> int:
    try:
        return int(line[len(prefix):].strip())
    except ValueError as exc:
        raise PlaylistError(f"{prefix.rstrip(':')} 无法解析：{line!r}") from exc
