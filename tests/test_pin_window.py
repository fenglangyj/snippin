"""T-10 贴图窗回归测试。

锁死基线缺陷：PinWindow 曾以 super().__init__(flags=...) 构造，PySide6 6.12 不接受
该关键字会在运行时崩溃；现改为 parent + 窗口标志位置参数。
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage

from snippin.config import Config
from snippin.ui.pin import PinWindow


def _image() -> QImage:
    img = QImage(160, 90, QImage.Format.Format_ARGB32)
    img.fill(0xFF22AA55)
    return img


def test_pin_window_constructs(qapp):
    pin = PinWindow(_image(), Config())
    flags = pin.windowFlags()
    assert flags & Qt.WindowType.FramelessWindowHint
    assert flags & Qt.WindowType.WindowStaysOnTopHint
    assert pin.width() >= 120 and pin.height() >= 80


def test_pin_copy_to_clipboard(qapp):
    from PySide6.QtWidgets import QApplication
    pin = PinWindow(_image(), Config())
    pin._copy()
    assert not QApplication.clipboard().image().isNull()
