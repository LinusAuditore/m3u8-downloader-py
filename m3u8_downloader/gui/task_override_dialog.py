"""任务级请求头与代理覆盖对话框（字段级覆盖全局默认，仅对本次任务生效）。"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from m3u8_downloader.gui.parsers import format_header_lines


class TaskOverrideDialog(QDialog):
    def __init__(
        self,
        global_headers: dict[str, str],
        global_proxy: str | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("任务级请求头与代理")
        layout = QVBoxLayout(self)

        note = f"全局代理：{global_proxy or '未设置'}。以下设置仅对本次下载生效，字段级覆盖全局默认。"
        layout.addWidget(QLabel(note))
        layout.addWidget(QLabel("请求头（每行「名称: 值」，已按全局默认预填，可增删改）："))
        self.headers_edit = QPlainTextEdit()
        self.headers_edit.setPlainText(format_header_lines(global_headers))
        self.headers_edit.setPlaceholderText("User-Agent: …\nReferer: …\nCookie: …")
        self.headers_edit.setFixedHeight(140)
        layout.addWidget(self.headers_edit)

        layout.addWidget(QLabel("本次任务代理（留空跟随全局）："))
        self.proxy_edit = QLineEdit()
        self.proxy_edit.setPlaceholderText("http:// 或 socks5://")
        layout.addWidget(self.proxy_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("确定")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def result_values(self) -> tuple[dict[str, str], str | None]:
        from m3u8_downloader.gui.parsers import parse_header_lines

        headers, _errors = parse_header_lines(self.headers_edit.toPlainText())
        proxy = self.proxy_edit.text().strip() or None
        return headers, proxy
