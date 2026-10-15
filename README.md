# snippin · 快截

一款独立、轻量的微信风格截图工具。无需运行微信客户端，按下全局热键即可框选截图、标注、马赛克、保存、复制或贴图，并支持**文字提取**与**翻译**。

> 为什么做：微信自带的截图很好用，但想用截图就必须保持微信客户端运行，常驻资源占用高。snippin 把这套交互复刻为独立应用，专注做好一件事。

> English: snippin is a lightweight, standalone WeChat-style screenshot tool for Windows. Press a global hotkey, select a region, annotate (rect / ellipse / arrow / pen / text / mosaic), then save, copy, pin, extract text (OCR), or translate. MIT licensed. Not affiliated with WeChat / Tencent.

<!-- TODO: 发布后补充 badges（CI、版本、许可证、下载量），以及截图/GIF -->

## 功能特性

| 功能 | 状态 | 说明 |
| --- | --- | --- |
| 全屏遮罩 + 框选截图 | 已实现 | 支持多显示器跨屏选区 |
| 矩形 / 椭圆 / 箭头 / 画笔标注 | 已实现 | 默认红色，可在 `config.py` 调整 |
| 文字标注 | 已实现 | 点击选区内位置输入 |
| 马赛克 | 已实现 | 块级像素化，保护隐私信息 |
| 撤销 | 已实现 | 撤销上一步标注 |
| 保存 / 复制到剪贴板 | 已实现 | 保存弹窗默认按时间戳命名 |
| 贴图（置顶小窗） | 已实现 | 悬浮窗可拖拽，悬停显示操作条 |
| 全局热键 + 系统托盘 | 已实现 | 默认 `Ctrl+Alt+A` |
| 文字提取（OCR） | 规划中 M2 | 采用 Windows 系统 OCR API：离线、图片不出本机；需 Windows 10+ 及对应语言包 |
| 翻译 | 规划中 M2 | 可插拔在线服务（用户自配密钥，仓库不内置任何密钥）；仅在你点击「翻译」时上传识别文本 |
| 放大镜、选区 8 向调整 | 规划中 M2 | 见 docs/TASKS.md |
| 设置面板（热键/路径/配色/密钥） | 规划中 M2 | 当前通过 `src/snippin/config.py` 配置 |
| 截图历史记录 | 规划中 | |

## 隐私说明

- 截图与 OCR 全部在本机完成，**默认不联网、不上传任何图片**。
- 翻译是唯一会联网的功能：仅在你主动点击「翻译」时，把选区的识别文本发送给你自己配置的翻译服务。
- 翻译密钥只保存在本机配置中，不写入代码、不写入仓库、不写入日志。

## 运行

要求 Windows 10/11 + Python 3.10+（文字提取依赖 Windows 系统 OCR；Linux 可运行基础截图功能，但热键与 OCR 受限，见 docs/ARCHITECTURE.md「已知限制」）。

```bash
cd snippin
python -m venv .venv
.venv\Scripts\activate
pip install -e .
snippin              # 或 python -m snippin
```

运行后点击系统托盘图标，或按 `Ctrl+Alt+A` 开始截图。

## 快捷键

| 按键 | 作用 |
| --- | --- |
| `Ctrl+Alt+A` | 开始截图（全局，可在 `Config.DEFAULT_HOTKEY` 修改） |
| 鼠标拖拽 | 框选区域 |
| 双击选区 / `Enter` / 「✓ 完成」 | 复制到剪贴板并退出 |
| `Esc` / 「✕」 | 取消截图 |
| `Delete` / 「撤销」 | 删除上一步标注 |

## 打包为 exe

```bash
pip install pyinstaller
packaging\build_exe.bat
```

产物在 `dist\snippin.exe`（配置见 `packaging/` 目录）。

## 目录结构

```
snippin/
├── src/snippin/
│   ├── app.py             # 入口、系统托盘、Controller（调度核心）
│   ├── config.py          # 配置与密钥读取（QSettings 持久化）
│   ├── hotkey.py          # 全局热键监听
│   ├── tools.py           # 标注数据模型与绘制
│   ├── capture/grabber.py # 跨屏抓屏
│   ├── ocr/               # 文字提取契约与引擎（T-21）
│   ├── translate/         # 翻译契约与 provider（T-23）
│   ├── ui/overlay.py      # 截图遮罩层 + 工具条（核心交互）
│   └── ui/pin.py          # 贴图悬浮窗
├── tests/                 # 单元测试（pytest）
├── docs/                  # PRD / 架构 / 任务 / 风险
└── packaging/             # PyInstaller 打包
```

## 路线图

见 [docs/TASKS.md](docs/TASKS.md) 与 [docs/PRD.md](docs/PRD.md)。

## 贡献

欢迎提交 Issue 与 PR，详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 许可证

[MIT](LICENSE)

## 免责声明

本项目为独立开源学习项目，与微信、腾讯无任何关联，未使用其任何商标或资源。界面交互灵感来自微信截图，仅供学习与技术交流。
