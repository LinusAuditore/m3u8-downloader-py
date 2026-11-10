"""``python -m m3u8_downloader``：启动图形界面。"""

from __future__ import annotations

import logging
import sys


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (AttributeError, ValueError, OSError):
                pass
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print("未安装 PySide6，无法启动 GUI。")
        print("可使用命令行：python -m m3u8_downloader.cli --help")
        return 1

    try:
        from m3u8_downloader.core import paths

        log_file = paths.app_data_dir() / "gui.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            filename=str(log_file),
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )
    except OSError:
        logging.basicConfig(level=logging.WARNING)

    from m3u8_downloader.gui.main_window import MainWindow
    from m3u8_downloader.gui.material import apply_material_theme

    app = QApplication(sys.argv)
    apply_material_theme(app)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
