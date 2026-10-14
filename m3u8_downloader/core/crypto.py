"""AES-128 解密（HLS 标准加密，CBC 模式 + PKCS7 填充）。

IV 处理按 RFC 8216（修正参考项目把 IV 当文本编码的缺陷）：
- 播放列表显式给出 IV → 使用之（playlist 解析阶段已解码为 16 字节）；
- 未给出 → 片段的媒体序列号（MEDIA-SEQUENCE + 片段序）的 128 位大端整数。
"""

from __future__ import annotations

from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

from m3u8_downloader.core.models import KeyInfo

_BLOCK_SIZE = AES.block_size  # 16


class DecryptError(Exception):
    """解密失败：密钥/IV 无效、密文长度不对齐或填充非法。"""


def default_iv(media_sequence: int, segment_index: int) -> bytes:
    """未显式给出 IV 时的默认 IV：媒体序列号的 128 位大端表示。"""
    return (media_sequence + segment_index).to_bytes(16, "big")


def segment_iv(key: KeyInfo, media_sequence: int, segment_index: int) -> bytes:
    if key.iv is not None:
        return key.iv
    return default_iv(media_sequence, segment_index)


def decrypt_segment(data: bytes, key_bytes: bytes, iv: bytes) -> bytes:
    """解密单个片段并去除 PKCS7 填充；任何异常统一转 DecryptError。"""
    if len(key_bytes) != 16:
        raise DecryptError(f"密钥长度异常：{len(key_bytes)} 字节（应为 16）")
    if len(iv) != 16:
        raise DecryptError(f"IV 长度异常：{len(iv)} 字节（应为 16）")
    if len(data) == 0 or len(data) % _BLOCK_SIZE != 0:
        raise DecryptError(f"密文长度不是 {_BLOCK_SIZE} 的倍数：{len(data)}")
    try:
        cipher = AES.new(key_bytes, AES.MODE_CBC, iv)
        return unpad(cipher.decrypt(data), _BLOCK_SIZE)
    except ValueError as exc:
        raise DecryptError(f"解密失败（密钥或 IV 可能不正确）：{exc}") from exc
