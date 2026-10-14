"""GUI 文本解析工具：多行「名称: 值」请求头编辑。"""

from __future__ import annotations


def parse_header_lines(text: str) -> tuple[dict[str, str], list[str]]:
    """解析每行一条的请求头；返回 (字典, 无法解析的原始行列表)。"""
    headers: dict[str, str] = {}
    errors: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        name, sep, value = line.partition(":")
        if not sep or not name.strip():
            errors.append(line)
            continue
        headers[name.strip()] = value.strip()
    return headers, errors


def format_header_lines(headers: dict[str, str]) -> str:
    return "\n".join(f"{name}: {value}" for name, value in headers.items())
