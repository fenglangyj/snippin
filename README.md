# quicksnip · 快截

一款独立、轻量的微信风格截图工具。无需运行微信客户端，按下全局热键即可框选截图、标注、马赛克、保存、复制或贴图。

> 为什么做：微信自带的截图（Alt+A）很好用，但想用截图就必须保持微信客户端运行，常驻资源占用高。quicksnip 把这套交互复刻为独立应用，专注做好一件事。

> English: quicksnip is a lightweight, standalone WeChat-style screenshot tool for Windows. Press a global hotkey, select a region, annotate (rect / ellipse / arrow / pen / text / mosaic), then save, copy, or pin. MIT licensed. Not affiliated with WeChat / Tencent.

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
| 放大镜、选区 8 向调整 | 规划中 | 见 docs/TASKS.md |
| 设置面板（热键/路径/配色） | 规划中 | 当前通过 `src/quicksnip/config.py` 配置 |
| 截图历史记录 | 规划中 | |

## 运行

要求 Windows + Python 3.10+（Linux 可运行但热键与抓屏行为受限，见 docs/ARCHITECTURE.md「已知限制」）。

```bash
cd quicksnip
python -m venv .venv
.venv\Scripts\activate
pip install -e .
quicksnip            # 或 python -m quicksnip
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

产物在 `dist\quicksnip.exe`（配置见 `packaging/` 目录）。

## 目录结构

```
quicksnip/
├── src/quicksnip/
│   ├── app.py            # 入口、系统托盘、Controller（调度核心）
│   ├── config.py         # 配置（QSettings 持久化）
│   ├── hotkey.py         # 全局热键监听
│   ├── tools.py          # 标注数据模型与绘制
│   ├── capture/grabber.py# 跨屏抓屏
│   ├── ui/overlay.py     # 截图遮罩层 + 工具条（核心交互）
│   └── ui/pin.py         # 贴图悬浮窗
├── tests/                # 单元测试（pytest）
├── docs/                 # PRD / 架构 / 任务 / 风险
└── packaging/            # PyInstaller 打包
```

## 路线图

见 [docs/TASKS.md](docs/TASKS.md) 与 [docs/PRD.md](docs/PRD.md)。

## 贡献

欢迎提交 Issue 与 PR，详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 许可证

[MIT](LICENSE)

## 免责声明

本项目为独立开源学习项目，与微信、腾讯无任何关联，未使用其任何商标或资源。界面交互灵感来自微信截图，仅供学习与技术交流。
