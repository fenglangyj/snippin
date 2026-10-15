# -*- mode: python ; coding: utf-8 -*-
"""snippin PyInstaller 打包配置（T-17）.

用法（本地）:
    pyinstaller --noconfirm --clean packaging/snippin.spec
或:
    packaging\\build_exe.bat

产物:
    dist/snippin.exe  （onefile，与既有基线一致）

设计要点:
- onefile 便于单文件分发；R-04（杀软误报）若需缓解，见 docs/RELEASE.md
  中「onedir 备选」方案（改 SPEX_MODE=onedir）。
- OCR 走 Windows 系统 API（Windows.Media.Ocr，winrt/projection），
  不引入任何需要随包分发的模型或二进制，因此打包体积增量应为 0；
  体积回归由 packaging/check_size.py 把关。
- 翻译为在线 API，仅使用标准库/Qt 网络能力，不得引入大依赖。
- 显式裁剪用不到的 Qt 大模块，避免 PyInstaller 默认 hooks 把它们拖进包里。
"""

import os
import sys

from PyInstaller.utils.hooks import collect_submodules

APP_NAME = "snippin"
ENTRY = os.path.join(SPECPATH, "launcher.py")
SRC = os.path.abspath(os.path.join(SPECPATH, "..", "src"))
if SRC not in sys.path:
    sys.path.insert(0, SRC)

# 打包目标形态：onefile（默认）/ onedir。见 docs/RELEASE.md。
MODE = os.environ.get("SNIPPIN_PKG_MODE", "onefile").strip().lower()
ONEFILE = MODE != "onedir"

# 本项目只用 QtCore / Qt QtGui / QtWidgets；其余 Qt 大模块显式排除以控体积。
EXCLUDE_QT = [
    "PySide6.Qt3DAnimation",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DRender",
    "PySide6.QtBluetooth",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtDesigner",
    "PySide6.QtGraphs",
    "PySide6.QtHelp",
    "PySide6.QtLocation",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtNfc",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtPositioning",
    "PySide6.QtQuick",
    "PySide6.QtQuick3D",
    "PySide6.QtQuickWidgets",
    "PySide6.QtRemoteObjects",
    "PySide6.QtScxml",
    "PySide6.QtSensors",
    "PySide6.QtSerialPort",
    "PySide6.QtShapes",
    "PySide6.QtSql",
    "PySide6.QtStateMachine",
    "PySide6.QtTest",
    "PySide6.QtTextToSpeech",
    "PySide6.QtWebChannel",
    "PySide6.QtWebCore",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebView",
    "PySide6.QtXml",
]

# 实测（PySide6 6.12 / PyInstaller 6.22，本机 onedir 119.9 MiB）后确认：
# 仅排除 PySide6.QtXxx 子模块不足以去掉这些 DLL —— PySide6 hook 会按插件依赖把它们拉回包内。
# 因此按下拉的包内文件名再裁剪一次。裁剪理由与风险：
# - opengl32sw.dll(19.7MiB)：Qt 的软件 OpenGL 回退实现；本项目只用 QtWidgets 栅格绘制，
#   正常显卡/远程桌面走 qwindows/qdirect2d 平台插件即可。
#   风险：极端无 GPU 环境下可能渲染异常 -> 需 T-12 手动矩阵覆盖「基本显示驱动/虚拟机」一列。
# - Qt6Quick/Qt6Qml/Qt6QmlModels(12.5MiB)、Qt6Pdf(4.4MiB)、Qt6VirtualKeyboard(0.4MiB)：
#   分别属于 QtQuick、QtPdf、虚拟键盘，均未使用。
# 保留：platforms/*（qwindows、qdirect2d）、imageformats/*（PNG/JPEG 保存）、
# Qt6Network + QtNetwork.pyd + libssl/libcrypto（在线翻译 provider 的 TLS 能力）。
PRUNE_BINARIES = [
    "opengl32sw.dll",
    "qt6quick.dll",
    "qt6qml.dll",
    "qt6qmlmodels.dll",
    "qt6pdf.dll",
    "qt6pdfwidgets.dll",
    "qt6virtualkeyboard.dll",
]

# 应急开关：出现渲染/功能异常时设 SNIPPIN_PKG_PRUNE=0 可完全还原为未裁剪包。
PRUNE_ENABLED = os.environ.get("SNIPPIN_PKG_PRUNE", "1").strip().lower() != "0"

hiddenimports = collect_submodules("snippin")

a = Analysis(
    [ENTRY],
    pathex=[SRC],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtimehooks=[],
    strict_conflict=False,
    noarchive=False,
    exclude_module_names=list(EXCLUDE_QT),
)

def _prunable(entry) -> bool:
    dest = entry[0] if isinstance(entry, (tuple, list)) else str(entry)
    return os.path.basename(dest).lower() in PRUNE_BINARIES


if PRUNE_ENABLED:
    dropped = [e for e in a.binaries if _prunable(e)] + [e for e in a.datas if _prunable(e)]
    a.binaries = [e for e in a.binaries if not _prunable(e)]
    a.datas = [e for e in a.datas if not _prunable(e)]
    print("[snippin.spec] 已裁剪 %d 项: %s"
          % (len(dropped), ", ".join(sorted({os.path.basename(e[0]) for e in dropped}))))

pyz = PYZ(a.pure)

if ONEFILE:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name=APP_NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,  # UPX 压缩会显著提高杀软误报率（R-04），保持关闭
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name=APP_NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        disable_windowed_traceback=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=False,
        name=APP_NAME,
    )
