"""任务级请求头与代理覆盖对话框（Material Design 1 风格，字段级覆盖全局默认）。"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from m3u8_downloader.gui import material
from m3u8_downloader.gui.material import (
    MdCard,
    MdLineEdit,
    MdPlainTextEdit,
    ensure_material_theme,
    style_dialog_button_box,
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
        ensure_material_theme()
        self.setWindowTitle("任务级请求头与代理")
        self.setMinimumWidth(480)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 16)
        layout.setSpacing(16)

        card = MdCard("单次任务网络覆盖")
        layout.addWidget(card)

        note = QLabel(
            f"全局代理：{global_proxy or '未设置'}。以下设置仅对本次下载生效，字段级覆盖全局默认。"
        )
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {material.TEXT_SECONDARY}; font-size: 12px;")
        card.body_layout.addWidget(note)

        headers_label = QLabel("请求头（每行「名称: 值」，已按全局默认预填，可增删改）：")
        headers_label.setStyleSheet(f"color: {material.TEXT_SECONDARY}; font-size: 12px;")
        card.body_layout.addWidget(headers_label)

        self.headers_edit = MdPlainTextEdit()
        self.headers_edit.setPlainText(format_header_lines(global_headers))
        self.headers_edit.setPlaceholderText("User-Agent: …\nReferer: …\nCookie: …")
        self.headers_edit.setFixedHeight(140)
        card.body_layout.addWidget(self.headers_edit)

        proxy_label = QLabel("本次任务代理（留空跟随全局）：")
        proxy_label.setStyleSheet(
            f"color: {material.TEXT_SECONDARY}; font-size: 12px; margin-top: 6px;"
        )
        card.body_layout.addWidget(proxy_label)

        self.proxy_edit = MdLineEdit()
        self.proxy_edit.setPlaceholderText("http:// 或 socks5://")
        card.body_layout.addWidget(self.proxy_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok
        )
        style_dialog_button_box(buttons, ok_text="确定", cancel_text="取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def result_values(self) -> tuple[dict[str, str], str | None]:
        from m3u8_downloader.gui.parsers import parse_header_lines

        headers, _errors = parse_header_lines(self.headers_edit.toPlainText())
        proxy = self.proxy_edit.text().strip() or None
        return headers, proxy
