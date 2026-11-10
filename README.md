# m3u8-downloader-py

本地运行的 m3u8 视频下载器，带图形界面。支持标准 AES-128 加密流、断点续传、并发可调，
TS 原格式拼接或经 ffmpeg 流复制转封装 MP4。

![License](https://img.shields.io/badge/License-BSD--2--Clause-blue)
![Python](https://img.shields.io/badge/Python-3.11%2B-blue)

## 功能特性

- **加密支持**：VOD 型 m3u8 媒体播放列表；标准 AES-128 加密（IV 严格按 RFC 8216 处理，
  修正了部分同类工具对带显式 IV 的流解密出错的问题）
- **master 播放列表**：自动解析并列出可选码率，由用户选择
- **输出格式**：TS 原格式拼接，或调用外部 ffmpeg 以流复制方式转封装 MP4（不重编码）
- **断点续传**：片段级任务续传；退出、断网、崩溃后重新添加同一地址即可继续
- **请求头与代理**：全局默认 + 任务级覆盖（User-Agent / Referer / Cookie / 自定义头，
  HTTP / SOCKS 代理）
- **并发可调**：并发数、失败重试次数、重试间隔、连接与读取超时均为设置项
- **实用功能**：特定片段区间下载、强制导出不完整视频、点击失败片段单独重试
- **片段网格进度**：灰待下载 / 蓝下载中 / 绿完成 / 红失败，全局进度与统计一目了然

不支持：DRM 与网站专有加密（遇到会明确提示，不做任何绕过）、直播流录制。

## 安装与使用

### 方式一：构建独立程序（推荐）

需要 Python ≥ 3.11：

```bash
pip install requests[socks] PyCryptodome PySide6 pyinstaller
pyinstaller m3u8-downloader.spec --noconfirm
```

产物在 `dist/m3u8-downloader/`：

- `m3u8-downloader` —— 图形界面主程序（macOS 构建另有可双击的 `dist/m3u8-downloader.app`）
- `m3u8-downloader-cli` —— 命令行版，参数见下表

> MP4 转封装需要系统已安装 [ffmpeg](https://ffmpeg.org/)；TS 输出不依赖。

### 方式二：从源码运行（须在仓库根目录）

```bash
python -m m3u8_downloader                          # 图形界面
python -m m3u8_downloader.cli <m3u8地址> [选项]     # 命令行
```

### 命令行常用选项

| 选项 | 说明 | 默认 |
| --- | --- | --- |
| `--format ts\|mp4` | 输出格式 | `ts` |
| `--output 目录` | 输出目录 | `./output` |
| `--range 起始:截止` | 片段区间（1-based 闭区间，如 `3:10`） | 全部 |
| `--variant 序号` | master 播放列表的码率选择 | 最高带宽 |
| `--header "名称: 值"` | 附加请求头，可重复 | — |
| `--proxy 地址` | HTTP / SOCKS 代理 | — |
| `--concurrency N` | 并发数 | 6 |
| `--retries N` | 失败重试次数上限 | 3 |
| `--force` | 有失败片段时仍强制导出不完整视频 | 关 |
| `--no-merge` | 只下载片段不合并（调试用） | 关 |

**断点续传**：下载中断后，重新运行同一条命令即可自动跳过已完成片段、只补缺失部分。
片段与任务状态保存在本地应用数据目录，任务完成后自动清理。

## 工作原理

- 下载核心（m3u8 解析、并发下载、AES 解密、合并）是独立的 Python 包，不依赖任何 GUI 框架，
  可单独通过命令行或测试调用；
- 片段逐个落盘，续传对账以磁盘文件为准，不把整个视频驻留内存；
- MP4 输出通过 ffmpeg 的 stdin 管道流复制完成，不产生中间合并文件、不重编码。

## 致谢

- 功能与思路参考自网页版工具
  [Momo707577045/m3u8-downloader](https://github.com/Momo707577045/m3u8-downloader)，
  在此致谢。本项目仅参考其行为与思路、未复制其代码，并针对本地环境重新设计
  （原仓库无许可证文件）。
- 本项目由 ZCode 智能编程助手使用 GLM 5.3 Flash 模型辅助开发完成。后续通过 Cursor 使用 Gemini 4 Argon 模型辅助开发与完善。

## 免责声明

本项目仅供个人学习研究，以及个人有权访问内容的下载备份。使用时请遵守目标网站的服务
条款与所在地区法律法规，尊重内容版权。本项目不支持、也不计划支持 DRM 或其他加密方式的绕过。

## License

[BSD-2-Clause](LICENSE) © 2026 Xinghao Zuo
