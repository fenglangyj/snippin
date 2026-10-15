from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication


def grab_virtual_desktop() -> tuple[QImage, int, int]:
    """把所有显示器拼成一张大图，返回 (图像, 虚拟桌面左上角 x, y)。

    选区坐标系与窗口坐标系均以此虚拟桌面左上角为原点。
    """
    app = QApplication.instance()
    screens = app.screens() if app else []
    if not screens:
        raise RuntimeError("未检测到显示器")
    left = min(s.geometry().left() for s in screens)
    top = min(s.geometry().top() for s in screens)
    right = max(s.geometry().right() for s in screens)
    bottom = max(s.geometry().bottom() for s in screens)
    canvas = QImage(right - left + 1, bottom - top + 1, QImage.Format.Format_ARGB32)
    canvas.fill(0)
    painter = QPainter(canvas)
    for screen in screens:
        pixmap = screen.grabWindow(0)
        geo = screen.geometry()
        painter.drawPixmap(geo.left() - left, geo.top() - top, pixmap)
    painter.end()
    return canvas, left, top
