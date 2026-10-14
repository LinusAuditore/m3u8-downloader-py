"""设置对话框：并发/重试/超时、输出目录、ffmpeg、全局请求头与代理。"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from m3u8_downloader.core.config import Settings
from m3u8_downloader.gui.parsers import format_header_lines, parse_header_lines


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("设置")
        self._accepted_headers = dict(settings.headers)
        self._build_ui(settings)

    def _build_ui(self, settings: Settings) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self.concurrency_spin = QSpinBox()
        self.concurrency_spin.setRange(1, 64)
        self.concurrency_spin.setValue(settings.concurrency)
        form.addRow("并发数", self.concurrency_spin)

        self.retries_spin = QSpinBox()
        self.retries_spin.setRange(0, 20)
        self.retries_spin.setValue(settings.max_retries)
        form.addRow("失败重试次数", self.retries_spin)

        self.interval_spin = QDoubleSpinBox()
        self.interval_spin.setRange(0.0, 60.0)
        self.interval_spin.setDecimals(1)
        self.interval_spin.setSuffix(" 秒")
        self.interval_spin.setValue(settings.retry_interval)
        form.addRow("重试间隔", self.interval_spin)

        self.connect_spin = QDoubleSpinBox()
        self.connect_spin.setRange(1.0, 120.0)
        self.connect_spin.setSuffix(" 秒")
        self.connect_spin.setValue(settings.connect_timeout)
        form.addRow("连接超时", self.connect_spin)

        self.read_spin = QDoubleSpinBox()
        self.read_spin.setRange(1.0, 600.0)
        self.read_spin.setSuffix(" 秒")
        self.read_spin.setValue(settings.read_timeout)
        form.addRow("读取超时", self.read_spin)

        self.output_edit = QLineEdit(settings.output_dir or "")
        output_row = QHBoxLayout()
        output_row.addWidget(self.output_edit)
        browse_output = QPushButton("选择…")
        browse_output.clicked.connect(self._browse_output)
        output_row.addWidget(browse_output)
        form.addRow("输出目录", output_row)

        self.ffmpeg_edit = QLineEdit(settings.ffmpeg_path or "")
        self.ffmpeg_edit.setPlaceholderText("留空自动从 PATH 探测")
        ffmpeg_row = QHBoxLayout()
        ffmpeg_row.addWidget(self.ffmpeg_edit)
        browse_ffmpeg = QPushButton("选择…")
        browse_ffmpeg.clicked.connect(self._browse_ffmpeg)
        ffmpeg_row.addWidget(browse_ffmpeg)
        form.addRow("ffmpeg 路径", ffmpeg_row)

        self.proxy_edit = QLineEdit(settings.proxy or "")
        self.proxy_edit.setPlaceholderText("http:// 或 socks5://，留空不使用代理")
        form.addRow("全局代理", self.proxy_edit)

        layout.addWidget(QLabel("全局默认请求头（每行「名称: 值」，任务可在下载前覆盖）："))
        self.headers_edit = QPlainTextEdit()
        self.headers_edit.setPlainText(format_header_lines(settings.headers))
        self.headers_edit.setPlaceholderText("User-Agent: Mozilla/5.0 …\nReferer: https://…\nCookie: …")
        self.headers_edit.setFixedHeight(120)
        layout.addWidget(self.headers_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse_output(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if chosen:
            self.output_edit.setText(chosen)

    def _browse_ffmpeg(self) -> None:
        chosen, _ = QFileDialog.getOpenFileName(self, "选择 ffmpeg 可执行文件")
        if chosen:
            self.ffmpeg_edit.setText(chosen)

    def _on_accept(self) -> None:
        headers, errors = parse_header_lines(self.headers_edit.toPlainText())
        if errors:
            QMessageBox.warning(
                self,
                "请求头格式错误",
                "以下行不是「名称: 值」格式：\n" + "\n".join(errors),
            )
            return
        self._accepted_headers = headers
        self.accept()

    def settings_result(self) -> Settings:
        return Settings(
            concurrency=self.concurrency_spin.value(),
            max_retries=self.retries_spin.value(),
            retry_interval=self.interval_spin.value(),
            connect_timeout=self.connect_spin.value(),
            read_timeout=self.read_spin.value(),
            output_dir=self.output_edit.text().strip() or None,
            ffmpeg_path=self.ffmpeg_edit.text().strip() or None,
            proxy=self.proxy_edit.text().strip() or None,
            headers=self._accepted_headers,
        )
