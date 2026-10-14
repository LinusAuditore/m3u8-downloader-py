"""PyInstaller CLI 打包入口，等价于 ``python -m m3u8_downloader.cli``。"""

import sys

from m3u8_downloader.cli import main

if __name__ == "__main__":
    sys.exit(main())
