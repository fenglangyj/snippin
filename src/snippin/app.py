import sys

from PySide6.QtCore import QObject, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QMenu, QStyle, QSystemTrayIcon

from .capture.grabber import grab_virtual_desktop
from .config import Config
from .hotkey import HotkeyListener
from .ui.overlay import Overlay
from .ui.pin import PinWindow
from .ui.result_panel import OcrPanel, TranslatePanel, run_ocr


class Controller(QObject):
    """调度核心：响应热键/托盘 -> 抓屏 -> 显示遮罩 -> 处理结果。"""

    def __init__(self, cfg: Config) -> None:
        super().__init__()
        self.cfg = cfg
        self.overlay: Overlay | None = None
        self.pins: list[PinWindow] = []
        self.panels: list = []  # OCR / 翻译结果面板，持有引用防止被回收
        self.tray: QSystemTrayIcon | None = None

    def start_capture(self) -> None:
        if self.overlay is not None:
            self.overlay.close()
            self.overlay = None
        image, x, y = grab_virtual_desktop()
        self.overlay = Overlay(image, self.cfg)
        self.overlay.setGeometry(x, y, image.width(), image.height())
        self.overlay.finished.connect(self._on_finished)
        self.overlay.show()
        self.overlay.raise_()
        self.overlay.activateWindow()

    def _on_finished(self, action: int, image, path: str) -> None:
        self.overlay = None
        if action == Overlay.COPY and image is not None:
            QApplication.clipboard().setImage(image)
            self._notify("截图已复制到剪贴板")
        elif action == Overlay.SAVE:
            self._notify(f"截图已保存：{path}")
        elif action == Overlay.PIN and image is not None:
            pin = PinWindow(image, self.cfg)
            pin.show()
            self.pins.append(pin)
        elif action == Overlay.OCR and image is not None:
            self._open_panel(OcrPanel(image, self.cfg))
        elif action == Overlay.TRANSLATE and image is not None:
            source = self._ocr_text_or_empty(image)
            self._open_panel(TranslatePanel(source, self.cfg))

    def _ocr_text_or_empty(self, image) -> str:
        """为翻译面板尽力预取 OCR 文本；引擎不可用时返回空串（面板支持手动粘贴）。"""
        try:
            return run_ocr(image, self.cfg).text
        except Exception:  # noqa: BLE001 —— OCR 不可用不阻断翻译面板打开
            return ""

    def _open_panel(self, panel) -> None:
        panel.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        panel.destroyed.connect(lambda *_: self._forget_panel(panel))
        self.panels.append(panel)
        panel.show()
        panel.raise_()
        panel.activateWindow()

    def _forget_panel(self, panel) -> None:
        if panel in self.panels:
            self.panels.remove(panel)

    def open_save_dir(self) -> None:
        self.cfg.save_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.cfg.save_dir)))

    def _notify(self, message: str) -> None:
        if self.tray is not None and QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.showMessage("snippin", message,
                                  QSystemTrayIcon.MessageIcon.Information, 2000)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("snippin")
    app.setApplicationDisplayName("snippin")
    app.setQuitOnLastWindowClosed(False)

    cfg = Config()
    controller = Controller(cfg)

    tray = QSystemTrayIcon(app.style().standardIcon(QStyle.StandardPixmap.SP_DesktopIcon), app)
    menu = QMenu()
    act_capture = menu.addAction("截图  (Ctrl+Alt+A)")
    act_capture.triggered.connect(controller.start_capture)
    act_open_dir = menu.addAction("打开保存目录")
    act_open_dir.triggered.connect(controller.open_save_dir)
    menu.addSeparator()
    act_quit = menu.addAction("退出")
    act_quit.triggered.connect(app.quit)
    tray.setContextMenu(menu)
    tray.setToolTip("snippin - 轻量截图工具")
    controller.tray = tray
    tray.show()

    listener = HotkeyListener(cfg.hotkey)
    listener.triggered.connect(controller.start_capture)
    listener.start()

    return app.exec()
