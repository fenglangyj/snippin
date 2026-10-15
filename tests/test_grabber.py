import os

import pytest
from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QPixmap

from snippin.capture.grabber import grab_virtual_desktop, stitch

RED, BLUE = QColor("red"), QColor("blue")


def _screen_pixmap(width: int, height: int, color: QColor, dpr: float = 1.0) -> QPixmap:
    pm = QPixmap(int(width * dpr), int(height * dpr))
    pm.fill(color)
    if dpr != 1.0:
        pm.setDevicePixelRatio(dpr)
    return pm


def test_stitch_single_screen_dpr100():
    pm = _screen_pixmap(200, 100, RED)
    canvas = stitch([(QRect(0, 0, 200, 100), pm)], 0, 0, 200, 100)
    assert canvas.size() == (200, 100) or (canvas.width(), canvas.height()) == (200, 100)
    assert canvas.pixelColor(100, 50).name() == RED.name()


def test_stitch_mixed_dpi_positions_correct():
    """100% 主屏 + 150% 副屏：副屏内容必须落在其逻辑几何矩形内（R-02/AC-1）。"""
    pm_a = _screen_pixmap(200, 100, RED, dpr=1.0)
    pm_b = _screen_pixmap(100, 100, BLUE, dpr=1.5)  # 物理 150x150
    canvas = stitch([(QRect(0, 0, 200, 100), pm_a), (QRect(200, 0, 100, 100), pm_b)],
                    0, 0, 300, 100)
    assert (canvas.width(), canvas.height()) == (300, 100)
    assert canvas.pixelColor(100, 50).name() == RED.name()
    # 副屏区域整体应为蓝色（缩放绘制，不溢出、不偏移）
    for x in (201, 250, 299):
        assert canvas.pixelColor(x, 50).name() == BLUE.name(), x
    # 副屏边界外（画布右下角预留）不得被染色
    assert canvas.pixelColor(199, 50).name() == RED.name()


def test_stitch_negative_origin_offset():
    """主屏在右侧、副屏 x 为负时，偏移换算仍正确。"""
    pm_left = _screen_pixmap(100, 100, BLUE, dpr=1.0)
    pm_right = _screen_pixmap(100, 100, RED, dpr=1.0)
    canvas = stitch([(QRect(-100, 0, 100, 100), pm_left), (QRect(0, 0, 100, 100), pm_right)],
                    -100, 0, 200, 100)
    assert canvas.pixelColor(50, 50).name() == BLUE.name()
    assert canvas.pixelColor(150, 50).name() == RED.name()


def test_stitch_skips_none_pixmap():
    canvas = stitch([(QRect(0, 0, 50, 50), None)], 0, 0, 50, 50)
    assert canvas.pixelColor(25, 25).alpha() == 0


@pytest.mark.skipif(not (os.name == "nt" and os.environ.get("SNIPPIN_SMOKE")),
                    reason="真机抓屏冒烟需 SNIPPIN_SMOKE=1（交互 Windows 会话）")
def test_real_grab_matches_virtual_geometry(qapp):
    from PySide6.QtWidgets import QApplication

    image, x, y = grab_virtual_desktop()
    vg = QApplication.primaryScreen().virtualGeometry()
    assert (image.width(), image.height()) == (vg.width(), vg.height())
    assert (x, y) == (vg.x(), vg.y())
