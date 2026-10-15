from PySide6.QtCore import QRect
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtWidgets import QApplication


def grab_virtual_desktop() -> tuple[QImage, int, int]:
    """把所有显示器拼成一张大图，返回 (图像, 虚拟桌面左上角 x, y)。

    选区坐标系与窗口坐标系均以此虚拟桌面左上角为原点。
    画布为逻辑分辨率（DPR=1）：每块屏的抓屏结果（物理像素、带各自
    devicePixelRatio）被显式缩放绘制到该屏的逻辑几何矩形内，保证任意
    混合 DPI 下拼接位置正确（R-02 / 缺陷 D-02）。
    """
    app = QApplication.instance()
    screens = app.screens() if app else []
    if not screens:
        raise RuntimeError("未检测到显示器")
    left = min(s.geometry().left() for s in screens)
    top = min(s.geometry().top() for s in screens)
    right = max(s.geometry().right() for s in screens)
    bottom = max(s.geometry().bottom() for s in screens)
    entries = [(s.geometry(), s.grabWindow(0)) for s in screens]
    canvas = stitch(entries, left, top, right - left + 1, bottom - top + 1)
    return canvas, left, top


def stitch(entries: list[tuple[QRect, QPixmap | None]], left: int, top: int,
           width: int, height: int) -> QImage:
    """把 (逻辑几何, 抓屏图) 列表拼接进 width x height 画布。

    独立成纯函数便于多屏/混合 DPI 的单测仿真。target 矩形使用逻辑几何尺寸，
    drawPixmap(QRect, pixmap) 会按 pixmap 的 devicePixelRatio 正确换算源尺寸。
    """
    canvas = QImage(width, height, QImage.Format.Format_ARGB32)
    canvas.fill(0)
    painter = QPainter(canvas)
    for geo, pixmap in entries:
        if pixmap is None:
            continue
        target = QRect(geo.left() - left, geo.top() - top, geo.width(), geo.height())
        painter.drawPixmap(target, pixmap)
    painter.end()
    return canvas
