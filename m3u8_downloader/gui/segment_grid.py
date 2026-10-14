"""片段状态网格：参考项目的片段 Icon 交互（灰待下载/蓝下载中/绿完成/红失败，点击红色重试）。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QGridLayout, QLabel, QWidget

from m3u8_downloader.core.models import SegmentStatus


class _SegmentLabel(QLabel):
    clicked = Signal(int)

    def __init__(self, index: int, parent: QWidget | None = None) -> None:
        super().__init__(str(index + 1), parent)
        self._index = index
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedSize(38, 26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event) -> None:
        self.clicked.emit(self._index)


class SegmentGrid(QWidget):
    COLORS = {
        SegmentStatus.PENDING: "#dddddd",
        SegmentStatus.DOWNLOADING: "#3d8ac7",
        SegmentStatus.DONE: "#0acd76",
        SegmentStatus.FAILED: "#dc5350",
    }
    COLUMNS = 20
    failed_clicked = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._labels: list[_SegmentLabel] = []
        self._statuses: list[SegmentStatus] = []
        self._grid = QGridLayout(self)
        self._grid.setSpacing(3)

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

    def _apply_style(self, label: QLabel, status: SegmentStatus) -> None:
        label.setStyleSheet(
            f"background-color: {self.COLORS[status]};"
            "color: white; border-radius: 3px; font-size: 11px;"
        )
