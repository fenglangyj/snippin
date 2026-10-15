# -*- mode: python ; coding: utf-8 -*-
"""snippin PyInstaller 打包配置（onedir）。

设计说明（详见 docs/CI_CD.md）：
- onedir 模式：启动快（热键即截体验），且杀软误报概率低于 onefile；对外分发整目录压缩为 zip。
- 版本元数据来自 src/snippin/__init__.py 单一版本源（R-04 误报对策之一）。
- 若 packaging/snippin.ico 存在则自动用作 exe 图标（T-18 图标交付后放入即可）。
- 显式禁用 UPX：UPX 压缩是杀软启发式误报的常见诱因。
"""

import os
import sys
from pathlib import Path

SPEC_DIR = Path(SPECPATH)  # noqa: F821  # PyInstaller 注入变量
PROJECT_ROOT = SPEC_DIR.parent

sys.path.insert(0, str(SPEC_DIR))
from make_version_info import create_version_file  # noqa: E402

# ---- 元数据 ----
_icon_candidate = SPEC_DIR / "snippin.ico"
_icon = str(_icon_candidate) if _icon_candidate.exists() else None
_version_file = create_version_file(PROJECT_ROOT / "build" / "version_info.txt")
_version_arg = str(_version_file) if _version_file else None

# ---- 排除未被引用的 Qt 重模块，减小体积 ----
# 注意：后续新增导入时（如 T-23 可能用 QtNetwork、图标可能用 QtSvg）不要把这些模块加入排除列表
EXCLUDES = [
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuickWidgets",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.Qt3DAnimation",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DRender",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtDesigner",
    "PySide6.QtTest",
    "PySide6.QtSql",
    "PySide6.QtWebSockets",
    "PySide6.QtWebChannel",
    "PySide6.QtBluetooth",
    "PySide6.QtNfc",
    "PySide6.QtSensors",
    "PySide6.QtSerialPort",
    "PySide6.QtPositioning",
    "PySide6.QtRemoteObjects",
    "PySide6.QtScxml",
    "tkinter",
]

# ---- DLL 层裁剪（增量，实测依据见 docs/CI_CD.md「体积核查」）----
# 上面的 excludes 只作用于 Python 模块解析，**挡不住 PySide6 hook 按插件依赖把 DLL 拉回包内**。
# 用同一份 spec 在 PySide6 6.12.0 / PyInstaller 6.22.3 / Python 3.12.10 实测：
# opengl32sw.dll、Qt6Quick.dll、Qt6Qml.dll、Qt6QmlModels.dll、Qt6Pdf.dll、
# Qt6VirtualKeyboard.dll 六个文件全部仍在包内，合计 37.1 MiB，占整包 31%（119.9 -> 82.9 MiB）。
#
# 逐项理由：
# - opengl32sw.dll(19.7MiB)：Qt 软件 OpenGL 回退实现。本项目只做 QtWidgets 栅格绘制，
#   正常环境走 platforms/qwindows.dll（D3D/ANGLE）或 qdirect2d.dll。
#   ⚠ 需 T-12 手动矩阵补一列「虚拟机 / 基本显示驱动」验证渲染是否正常；
#     出问题把 SNIPPIN_PKG_PRUNE=0 设上即可完全还原，不需改代码。
# - Qt6Quick/Qt6Qml/Qt6QmlModels(12.5MiB)、Qt6Pdf(4.4MiB)、Qt6VirtualKeyboard(0.4MiB)：
#   对应模块已在 EXCLUDES 中，说明产品确实不使用它们，DLL 属于误带。
PRUNE_BINARIES = {
    "opengl32sw.dll",
    "qt6quick.dll",
    "qt6qml.dll",
    "qt6qmlmodels.dll",
    "qt6pdf.dll",
    "qt6pdfwidgets.dll",
    "qt6virtualkeyboard.dll",
}
PRUNE_ENABLED = os.environ.get("SNIPPIN_PKG_PRUNE", "1").strip().lower() != "0"

a = Analysis(
    [str(SPEC_DIR / "launcher.py")],
    pathex=[str(PROJECT_ROOT / "src")],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
    optimize=0,
)


def _prunable(entry) -> bool:
    dest = entry[0] if isinstance(entry, (tuple, list)) else str(entry)
    return Path(dest).name.lower() in PRUNE_BINARIES


if PRUNE_ENABLED:
    dropped = [e for e in a.binaries if _prunable(e)] + [e for e in a.datas if _prunable(e)]
    a.binaries = [e for e in a.binaries if not _prunable(e)]
    a.datas = [e for e in a.datas if not _prunable(e)]
    print("[snippin.spec] DLL 裁剪 %d 项: %s"
          % (len(dropped), ", ".join(sorted({Path(e[0]).name for e in dropped}))))

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="snippin",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_icon,
    version=_version_arg,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="snippin",
)
