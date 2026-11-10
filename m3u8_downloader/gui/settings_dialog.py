"""设置对话框：Material Design 1 风格，并发/重试/超时、输出目录、ffmpeg、全局请求头与代理。"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from m3u8_downloader.core.config import Settings
from m3u8_downloader.gui import material
from m3u8_downloader.gui.material import (
    MdButton,
    MdCard,
    MdDoubleSpinBox,
    MdLineEdit,
    MdPlainTextEdit,
    MdSpinBox,
     ensure_material_theme,
    style_dialog_button_box,
)
from m3u8_downloader.gui.parsers import format_header_lines, parse_header_lines


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        ensure_material_theme()
        self.setWindowTitle("设置")
        self.setMinimumWidth(520)
        self._accepted_headers = dict(settings.headers)
        self._build_ui(settings)

    def _build_ui(self, settings: Settings) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 16)
        layout.setSpacing(16)

        # —— 卡片 1：下载与超时参数 ——
        net_card = MdCard("下载与重试参数")
        layout.addWidget(net_card)
        net_form = QFormLayout()
        net_form.setHorizontalSpacing(16)
        net_form.setVerticalSpacing(10)
        net_card.body_layout.addLayout(net_form)

        self.concurrency_spin = MdSpinBox()
        self.concurrency_spin.setRange(1, 64)
        self.concurrency_spin.setValue(settings.concurrency)
        net_form.addRow(self._field_label("并发数"), self.concurrency_spin)

        self.retries_spin = MdSpinBox()
        self.retries_spin.setRange(0, 20)
        self.retries_spin.setValue(settings.max_retries)
        net_form.addRow(self._field_label("失败重试次数"), self.retries_spin)

        self.interval_spin = MdDoubleSpinBox()
        self.interval_spin.setRange(0.0, 60.0)
        self.interval_spin.setDecimals(1)
        self.interval_spin.setSuffix(" 秒")
        self.interval_spin.setValue(settings.retry_interval)
        net_form.addRow(self._field_label("重试间隔"), self.interval_spin)

        self.connect_spin = MdDoubleSpinBox()
        self.connect_spin.setRange(1.0, 120.0)
        self.connect_spin.setDecimals(1)
        self.connect_spin.setSuffix(" 秒")
        self.connect_spin.setValue(settings.connect_timeout)
        net_form.addRow(self._field_label("连接超时"), self.connect_spin)

        self.read_spin = MdDoubleSpinBox()
        self.read_spin.setRange(1.0, 600.0)
        self.read_spin.setDecimals(1)
        self.read_spin.setSuffix(" 秒")
        self.read_spin.setValue(settings.read_timeout)
        net_form.addRow(self._field_label("读取超时"), self.read_spin)

        # —— 卡片 2：路径、代理与全局请求头 ——
        env_card = MdCard("路径、代理与全局请求头")
        layout.addWidget(env_card)
        env_form = QFormLayout()
        env_form.setHorizontalSpacing(16)
        env_form.setVerticalSpacing(10)
        env_card.body_layout.addLayout(env_form)

        self.output_edit = MdLineEdit(settings.output_dir or "")
        self.output_edit.setPlaceholderText("留空使用系统默认下载目录")
        output_row = QHBoxLayout()
        output_row.setSpacing(8)
        output_row.addWidget(self.output_edit, 1)
        browse_output = MdButton("选择…", variant="flat")
        browse_output.clicked.connect(self._browse_output)
        output_row.addWidget(browse_output)
        env_form.addRow(self._field_label("输出目录"), output_row)

        self.ffmpeg_edit = MdLineEdit(settings.ffmpeg_path or "")
        self.ffmpeg_edit.setPlaceholderText("留空自动从 PATH 探测")
        ffmpeg_row = QHBoxLayout()
        ffmpeg_row.setSpacing(8)
        ffmpeg_row.addWidget(self.ffmpeg_edit, 1)
        browse_ffmpeg = MdButton("选择…", variant="flat")
        browse_ffmpeg.clicked.connect(self._browse_ffmpeg)
        ffmpeg_row.addWidget(browse_ffmpeg)
        env_form.addRow(self._field_label("ffmpeg 路径"), ffmpeg_row)

        self.proxy_edit = MdLineEdit(settings.proxy or "")
        self.proxy_edit.setPlaceholderText("http:// 或 socks5://，留空不使用代理")
        env_form.addRow(self._field_label("全局代理"), self.proxy_edit)

        headers_caption = QLabel("全局默认请求头（每行「名称: 值」，任务可在下载前覆盖）：")
        headers_caption.setStyleSheet(f"color: {material.TEXT_SECONDARY}; font-size: 12px;")
        env_card.body_layout.addWidget(headers_caption)

        self.headers_edit = MdPlainTextEdit()
        self.headers_edit.setPlainText(format_header_lines(settings.headers))
        self.headers_edit.setPlaceholderText(
            "User-Agent: Mozilla/5.0 …\nReferer: https://…\nCookie: …"
        )
        self.headers_edit.setFixedHeight(110)
        env_card.body_layout.addWidget(self.headers_edit)

        # —— 底部对话框操作区（MD1 Flat Buttons）——
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok
        )
        style_dialog_button_box(buttons, ok_text="保存", cancel_text="取消")
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _field_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(f"color: {material.TEXT_SECONDARY}; font-size: 13px;")
        return label

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
