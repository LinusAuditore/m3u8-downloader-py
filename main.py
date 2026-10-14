"""PyInstaller 打包入口，等价于 ``python -m m3u8_downloader``。"""

import sys

from m3u8_downloader.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
