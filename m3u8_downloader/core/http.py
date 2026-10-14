"""HTTP 会话封装：请求头/代理两层合并、超时与内容取回。

- 代理只认显式配置（``trust_env=False``），不受系统环境变量影响；
- 请求头做字段级合并：全局默认 → 任务覆盖（任务优先）；
- 未配置 User-Agent 时使用本工具默认标识。
"""

from __future__ import annotations

from dataclasses import dataclass, field

import requests

from m3u8_downloader import __version__
from m3u8_downloader.core.config import Settings
from m3u8_downloader.core.models import Task

DEFAULT_USER_AGENT = f"m3u8-downloader-py/{__version__}"

Timeout = tuple[float, float]  # (连接超时, 读取超时)


class HttpError(Exception):
    """HTTP 请求失败：网络异常或非 2xx 响应。"""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class HttpConfig:
    headers: dict[str, str] = field(default_factory=dict)
    proxy: str | None = None
    connect_timeout: float = 10.0
    read_timeout: float = 30.0

    @property
    def timeout(self) -> Timeout:
        return (self.connect_timeout, self.read_timeout)

    @property
    def proxies(self) -> dict[str, str] | None:
        if not self.proxy:
            return None
        return {"http": self.proxy, "https": self.proxy}


def build_http_config(settings: Settings, task: Task) -> HttpConfig:
    """把全局配置与任务覆盖合并为一次任务实际生效的 HTTP 参数。"""
    headers = dict(settings.headers)
    headers.update(task.headers)
    headers.setdefault("User-Agent", DEFAULT_USER_AGENT)
    return HttpConfig(
        headers=headers,
        proxy=task.proxy or settings.proxy,
        connect_timeout=settings.connect_timeout,
        read_timeout=settings.read_timeout,
    )


def create_session(config: HttpConfig) -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    session.headers.update(config.headers)
    if config.proxies:
        session.proxies.update(config.proxies)
    return session


def fetch_bytes(session: requests.Session, url: str, timeout: Timeout) -> bytes:
    """GET 二进制内容；网络异常与非 2xx 一律抛 HttpError。"""
    try:
        response = session.get(url, timeout=timeout)
    except requests.RequestException as exc:
        raise HttpError(f"网络请求失败：{exc}") from exc
    if not 200 <= response.status_code < 300:
        raise HttpError(
            f"HTTP {response.status_code}：{url}", status=response.status_code
        )
    return response.content


def fetch_text(session: requests.Session, url: str, timeout: Timeout) -> str:
    """m3u8 文本按 UTF-8 解码；个别非法字节替换而非失败。"""
    return fetch_bytes(session, url, timeout).decode("utf-8", errors="replace")
