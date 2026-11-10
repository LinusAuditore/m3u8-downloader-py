"""片段状态网格：Material Design 1 风格色块交互（灰待下载/蓝下载中/绿完成/红失败，点击红色重试）。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QGridLayout, QPushButton, QWidget

from m3u8_downloader.core.models import SegmentStatus
from m3u8_downloader.gui import material


class _SegmentLabel(QPushButton):
    """单个片段状态块；继承 QPushButton 以暴露 AXButton / AXPress 无障碍动作。"""

    clicked = Signal(int)

    def __init__(self, index: int, parent: QWidget | None = None) -> None:
        super().__init__(str(index + 1), parent)
        self._index = index
        self.setFlat(True)
        self.setFixedSize(36, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._index)
            event.accept()
            return
        super().mousePressEvent(event)

    def nextCheckState(self) -> None:
        # 供 macOS Accessibility AXPress (QAccessibleButton) 触发
        self.clicked.emit(self._index)


class SegmentGrid(QWidget):
    COLORS = {
        SegmentStatus.PENDING: material.STATUS_PENDING,
        SegmentStatus.DOWNLOADING: material.STATUS_DOWNLOADING,
        SegmentStatus.DONE: material.STATUS_DONE,
        SegmentStatus.FAILED: material.STATUS_FAILED,
    }
    TEXT_COLORS = {
        SegmentStatus.PENDING: material.STATUS_PENDING_TEXT,
        SegmentStatus.DOWNLOADING: material.TEXT_ON_PRIMARY,
        SegmentStatus.DONE: material.TEXT_ON_PRIMARY,
        SegmentStatus.FAILED: material.TEXT_ON_PRIMARY,
    }
    COLUMNS = 20
    failed_clicked = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._labels: list[_SegmentLabel] = []
        self._statuses: list[SegmentStatus] = []
        self.setStyleSheet("background-color: #FAFAFA;")
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(10, 10, 10, 10)
        self._grid.setSpacing(4)
        self._grid.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )

    @property
    def statuses(self) -> list[SegmentStatus]:
        return list(self._statuses)

    def reset_grid(self) -> None:
        self.set_total(0)

    def set_total(self, total: int) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._labels.clear()
        self._statuses.clear()
        for index in range(total):
            label = _SegmentLabel(index)
            label.clicked.connect(self._on_label_clicked)
            self._apply_style(label, SegmentStatus.PENDING)
            label.setToolTip(f"片段 {index + 1}")
            self._grid.addWidget(label, index // self.COLUMNS, index % self.COLUMNS)
            self._labels.append(label)
            self._statuses.append(SegmentStatus.PENDING)

    def set_status(self, index: int, status: SegmentStatus) -> None:
        if not 0 <= index < len(self._labels):
            return
        self._statuses[index] = status
        label = self._labels[index]
        self._apply_style(label, status)
        tooltip = f"片段 {index + 1}（{status.value}）"
        if status is SegmentStatus.FAILED:
            tooltip += "，点击重试"
        label.setToolTip(tooltip)

    def _on_label_clicked(self, index: int) -> None:
        if 0 <= index < len(self._statuses) and self._statuses[index] is SegmentStatus.FAILED:
            self.failed_clicked.emit(index)

    def _apply_style(self, label: _SegmentLabel, status: SegmentStatus) -> None:
        text_color = self.TEXT_COLORS[status]
        label.setStyleSheet(
            f"QPushButton {{"
            f" background-color: {self.COLORS[status]};"
            f" color: {text_color};"
            f" border: none;"
            f" border-radius: 2px;"
            f" font-size: 11px;"
            f" font-weight: 500;"
            f" padding: 0px;"
            f"}}"
        )
