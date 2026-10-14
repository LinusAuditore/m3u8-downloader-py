"""主窗口：地址输入、码率选择、进度与片段网格、设置与任务级覆盖。

线程约定：网络/磁盘耗时操作全部在 workers.py 的 QThread 中执行，
本窗口只在信号槽（主线程）里更新控件。
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from m3u8_downloader.core import paths, resume
from m3u8_downloader.core.config import Settings, load_settings, save_settings
from m3u8_downloader.core.downloader import DownloadResult
from m3u8_downloader.core.models import (
    EventKind,
    MasterPlaylist,
    MediaPlaylist,
    OutputFormat,
    SegmentStatus,
    Task,
    TaskEvent,
    Variant,
)
from m3u8_downloader.gui.segment_grid import SegmentGrid
from m3u8_downloader.gui.settings_dialog import SettingsDialog
from m3u8_downloader.gui.task_override_dialog import TaskOverrideDialog
from m3u8_downloader.gui.workers import DownloadWorker, MergeWorker, ProbeWorker

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("m3u8 下载器")
        self.resize(880, 660)

        self.settings: Settings = load_settings()
        self._task_headers: dict[str, str] = {}
        self._task_proxy: str | None = None
        self._probe_worker: ProbeWorker | None = None
        self._download_worker: DownloadWorker | None = None
        self._merge_worker: MergeWorker | None = None
        self._current_task: Task | None = None
        self._phase = "idle"  # idle / probe / download / merge
        self._paused = False
        self._grid_ready = False

        self._build_ui()

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # —— 任务输入 ——
        input_box = QGroupBox("任务")
        root.addWidget(input_box)
        form = QGridLayout(input_box)

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText(
            "m3u8 播放列表地址（支持 master 播放列表，开始后选择码率）"
        )
        form.addWidget(QLabel("地址"), 0, 0)
        form.addWidget(self.url_edit, 0, 1, 1, 3)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("留空自动命名（取地址主干）")
        form.addWidget(QLabel("文件名"), 1, 0)
        form.addWidget(self.title_edit, 1, 1)

        self.format_combo = QComboBox()
        self.format_combo.addItem("TS（原格式）", OutputFormat.TS)
        self.format_combo.addItem("MP4（需 ffmpeg）", OutputFormat.MP4)
        form.addWidget(QLabel("格式"), 1, 2)
        form.addWidget(self.format_combo, 1, 3)

        range_row = QHBoxLayout()
        self.range_check = QCheckBox("启用")
        self.range_start = QSpinBox()
        self.range_start.setRange(1, 999_999)
        self.range_end = QSpinBox()
        self.range_end.setRange(1, 999_999)
        range_row.addWidget(self.range_check)
        range_row.addWidget(self.range_start)
        range_row.addWidget(QLabel("～"))
        range_row.addWidget(self.range_end)
        range_row.addStretch(1)
        form.addWidget(QLabel("片段区间"), 2, 0)
        form.addLayout(range_row, 2, 1, 1, 3)

        button_row = QHBoxLayout()
        self.start_button = QPushButton("开始下载")
        self.start_button.clicked.connect(self._on_start_clicked)
        self.pause_button = QPushButton("暂停")
        self.pause_button.setEnabled(False)
        self.pause_button.clicked.connect(self._on_pause_clicked)
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self._on_cancel_clicked)
        self.headers_button = QPushButton("请求头覆盖…")
        self.headers_button.clicked.connect(self._open_task_override)
        self.settings_button = QPushButton("设置…")
        self.settings_button.clicked.connect(self._open_settings)
        button_row.addWidget(self.start_button)
        button_row.addWidget(self.pause_button)
        button_row.addWidget(self.cancel_button)
        button_row.addStretch(1)
        button_row.addWidget(self.headers_button)
        button_row.addWidget(self.settings_button)
        form.addLayout(button_row, 3, 0, 1, 4)

        self.output_label = QLabel()
        self.output_label.setStyleSheet("color: #888888;")
        form.addWidget(self.output_label, 4, 0, 1, 4)

        # —— 进度区 ——
        progress_box = QGroupBox("进度")
        root.addWidget(progress_box, 1)
        progress_layout = QVBoxLayout(progress_box)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        progress_layout.addWidget(self.progress_bar)
        self.stats_label = QLabel("待开始")
        progress_layout.addWidget(self.stats_label)

        self.grid = SegmentGrid()
        self.grid.failed_clicked.connect(self._on_retry_segment)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.grid)
        scroll.setMinimumHeight(180)
        progress_layout.addWidget(scroll)

        root.addStretch(1)
        self._refresh_output_label()

    # ------------------------------------------------------------ 启动流程

    def _on_start_clicked(self) -> None:
        url = self.url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "提示", "请输入 m3u8 地址")
            return
        self.stats_label.setText("获取播放列表…")
        self._set_phase("probe", "正在获取播放列表…")
        self._probe_worker = ProbeWorker(
            url, self.settings, dict(self._task_headers), self._task_proxy
        )
        self._probe_worker.succeeded.connect(self._on_probe_ok)
        self._probe_worker.failed.connect(self._on_probe_failed)
        self._probe_worker.start()

    def _on_probe_failed(self, message: str) -> None:
        self.stats_label.setText("获取失败")
        self._set_phase("idle", "播放列表获取失败")
        QMessageBox.critical(self, "获取播放列表失败", message)

    def _on_probe_ok(self, parsed) -> None:
        if isinstance(parsed, MasterPlaylist):
            variant = self._ask_variant(parsed.variants)
            if variant is None:
                self.stats_label.setText("待开始")
                self._set_phase("idle")
                return
            media_url = variant.uri
        elif isinstance(parsed, MediaPlaylist):
            media_url = parsed.url
        else:  # 防御：未知对象
            self.stats_label.setText("获取失败")
            self._set_phase("idle")
            QMessageBox.critical(self, "错误", "播放列表解析结果异常")
            return

        state = resume.find_resumable(media_url)
        if state is not None:
            choice = self._ask_resume(state)
            if choice is None:
                self.stats_label.setText("待开始")
                self._set_phase("idle")
                return
            if choice == "fresh":
                resume.remove_task_dir(resume.task_dir(media_url))
        self._start_download(media_url)

    def _ask_variant(self, variants: list[Variant]) -> Variant | None:
        dialog = QDialog(self)
        dialog.setWindowTitle("选择码率")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("检测到 master 播放列表，请选择要下载的码率："))
        combo = QComboBox()
        best = 0
        for i, variant in enumerate(variants):
            combo.addItem(variant.label(), i)
            if (variant.bandwidth or 0) > (variants[best].bandwidth or 0):
                best = i
        combo.setCurrentIndex(best)
        layout.addWidget(combo)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return variants[combo.currentData()]

    def _ask_resume(self, state: resume.TaskState) -> str | None:
        done = sum(1 for v in state.segments.values() if v == "done")
        total = len(state.segment_urls)
        box = QMessageBox(self)
        box.setWindowTitle("检测到未完成任务")
        box.setText(
            f"该地址存在未完成的任务（记录已完成 {done}/{total} 个片段）。\n"
            "要续传还是丢弃旧进度重新开始？"
        )
        resume_button = box.addButton("续传", QMessageBox.ButtonRole.AcceptRole)
        fresh_button = box.addButton("重新开始", QMessageBox.ButtonRole.DestructiveRole)
        box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked is resume_button:
            return "resume"
        if clicked is fresh_button:
            return "fresh"
        return None

    def _start_download(self, media_url: str) -> None:
        range_start = range_end = None
        if self.range_check.isChecked():
            range_start = self.range_start.value()
            range_end = max(self.range_end.value(), range_start)
        self._current_task = Task(
            url=media_url,
            output_format=self.format_combo.currentData(),
            output_dir=self._output_dir(),
            title=self.title_edit.text().strip() or None,
            range_start=range_start,
            range_end=range_end,
            headers=dict(self._task_headers),
            proxy=self._task_proxy,
        )
        self._grid_ready = False
        self.grid.reset_grid()
        self.progress_bar.setValue(0)
        self.stats_label.setText("下载中…")
        self._paused = False
        self.pause_button.setText("暂停")
        self._set_phase("download", "下载中…")
        self._download_worker = DownloadWorker(self._current_task, self.settings)
        self._download_worker.event_received.connect(self._on_download_event)
        self._download_worker.finished_result.connect(self._on_download_finished)
        self._download_worker.start()

    # ------------------------------------------------------------ 下载事件

    def _on_download_event(self, event: TaskEvent) -> None:
        if event.kind is EventKind.PROGRESS and event.stats is not None:
            stats = event.stats
            if not self._grid_ready and stats.total:
                self.grid.set_total(stats.total)
                self._grid_ready = True
            self.progress_bar.setValue(int(stats.percent))
            self.stats_label.setText(
                f"共 {stats.total} ｜ 完成 {stats.done} ｜ 失败 {stats.failed}"
                f" ｜ 进度 {stats.percent:.1f}%"
            )
        elif (
            event.kind is EventKind.SEGMENT_STATUS
            and event.segment_index is not None
            and event.status is not None
        ):
            # 网格总数由首个 PROGRESS 事件建立；早于它的片段事件被安全忽略
            self.grid.set_status(event.segment_index, event.status)
        elif event.kind is EventKind.WARNING and event.message:
            self.statusBar().showMessage(f"警告：{event.message}", 8000)

    def _on_download_finished(self, result: DownloadResult) -> None:
        self._download_worker = None
        if result.cancelled:
            self.stats_label.setText("已取消")
            self._set_phase("idle", "已取消（已下载片段已保留，重新开始同一任务可续传）")
            return
        if result.error is not None and result.failed == 0:
            self.stats_label.setText("下载失败")
            self._set_phase("idle", "下载失败")
            QMessageBox.critical(self, "下载失败", result.error)
            return
        if result.failed > 0:
            answer = QMessageBox.question(
                self,
                "部分片段失败",
                f"有 {result.failed} 个片段下载失败。\n\n"
                "要强制导出不完整视频吗？\n"
                "（选「No」可稍后点击网格中的红色片段重试）",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                self.stats_label.setText(f"下载未完成：{result.failed} 个片段失败")
                self._set_phase(
                    "idle",
                    f"下载未完成：{result.failed} 个片段失败，可点击红色片段重试",
                )
                return
        self.stats_label.setText("合并输出中…")
        self._set_phase("merge", "合并输出中…")
        self._start_merge()

    def _on_retry_segment(self, index: int) -> None:
        """点击失败片段 = 以同一任务重新下载（续传，自动重试失败片段）。"""
        if self._phase != "idle" or self._current_task is None:
            return
        self._start_download(self._current_task.url)

    # ------------------------------------------------------------ 合并输出

    def _start_merge(self) -> None:
        task = self._current_task
        if task is None:
            self._set_phase("idle")
            return
        self._merge_worker = MergeWorker(task, self.settings)
        self._merge_worker.progress_changed.connect(self._on_merge_progress)
        self._merge_worker.succeeded.connect(self._on_merge_ok)
        self._merge_worker.failed.connect(self._on_merge_failed)
        self._merge_worker.start()

    def _on_merge_progress(self, done: int, total: int) -> None:
        self.statusBar().showMessage(f"合并 {done}/{total}…")

    def _on_merge_ok(self, output) -> None:
        self._merge_worker = None
        self.stats_label.setText("已完成")
        self._set_phase("idle", f"完成：{output}")
        box = QMessageBox(self)
        box.setWindowTitle("完成")
        box.setText(f"已输出：\n{output}")
        open_button = box.addButton("打开所在文件夹", QMessageBox.ButtonRole.ActionRole)
        box.addButton("关闭", QMessageBox.ButtonRole.AcceptRole)
        box.exec()
        if box.clickedButton() is open_button:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(output).parent)))

    def _on_merge_failed(self, message: str) -> None:
        self._merge_worker = None
        self.stats_label.setText("合并失败")
        self._set_phase("idle", "合并失败")
        QMessageBox.critical(self, "合并失败", message)

    # ------------------------------------------------------------ 控制

    def _on_pause_clicked(self) -> None:
        worker = self._download_worker
        if worker is None:
            return
        if self._paused:
            worker.controller.resume()
            self._paused = False
            self.pause_button.setText("暂停")
            self.statusBar().showMessage("已恢复")
        else:
            worker.controller.pause()
            self._paused = True
            self.pause_button.setText("恢复")
            self.statusBar().showMessage("已暂停（在途片段完成后停止派发）")

    def _on_cancel_clicked(self) -> None:
        if self._download_worker is not None:
            self._download_worker.controller.cancel()
            self.statusBar().showMessage("正在取消…")

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.settings = dialog.settings_result()
        try:
            save_settings(self.settings)
        except OSError as exc:
            QMessageBox.warning(self, "保存设置失败", str(exc))
        self._refresh_output_label()

    def _open_task_override(self) -> None:
        dialog = TaskOverrideDialog(
            dict(self._task_headers or self.settings.headers),
            self._task_proxy or self.settings.proxy,
            self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._task_headers, self._task_proxy = dialog.result_values()
        count = len(self._task_headers)
        summary = f"已设置任务级覆盖：{count} 条请求头" + (
            f"，代理 {self._task_proxy}" if self._task_proxy else ""
        )
        self.statusBar().showMessage(summary + "（对下一次下载生效）", 8000)

    # ------------------------------------------------------------ 辅助

    def _output_dir(self) -> Path:
        if self.settings.output_dir:
            return Path(self.settings.output_dir)
        return paths.default_output_dir()

    def _refresh_output_label(self) -> None:
        self.output_label.setText(f"输出目录：{self._output_dir()}")

    def _set_phase(self, phase: str, message: str | None = None) -> None:
        self._phase = phase
        idle = phase == "idle"
        self.start_button.setEnabled(idle)
        self.pause_button.setEnabled(phase == "download")
        self.cancel_button.setEnabled(phase == "download")
        for widget in (
            self.url_edit,
            self.title_edit,
            self.format_combo,
            self.range_check,
            self.range_start,
            self.range_end,
            self.headers_button,
        ):
            widget.setEnabled(idle)
        if message is not None:
            self.statusBar().showMessage(message)

    def closeEvent(self, event) -> None:
        worker = self._download_worker
        if worker is not None and worker.isRunning():
            answer = QMessageBox.question(
                self,
                "退出确认",
                "下载正在进行中，退出将取消任务（已下载片段保留，下次可续传）。\n确定退出？",
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            worker.controller.cancel()
            worker.wait(10_000)
        event.accept()
