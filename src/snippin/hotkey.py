import threading

from PySide6.QtCore import QObject, Signal


class HotkeyListener(QObject):
    """基于 keyboard 库的后台全局热键监听。

    回调发生在子线程，通过 Qt 信号切换到主线程。
    Windows 直接可用；Linux 需要 root 权限（见 docs/RISKS.md）。
    """

    triggered = Signal()

    def __init__(self, hotkey: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.hotkey = hotkey
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return

        def _run() -> None:
            try:
                import keyboard

                keyboard.add_hotkey(self.hotkey, self._on_hotkey)
                keyboard.wait()
            except Exception:  # noqa: BLE001 —— 缺库/无权限等任何失败均静默降级
                # 无权限或库不可用时静默降级：仍可通过托盘菜单触发截图
                return

        self._thread = threading.Thread(target=_run, daemon=True, name="hotkey-listener")
        self._thread.start()

    def _on_hotkey(self) -> None:
        self.triggered.emit()
