import math

from PySide6.QtCore import QPoint, QPointF, QRect
from PySide6.QtGui import QPolygonF


def normalize_rect(a: QPoint, b: QPoint) -> QRect:
    """返回由两个角点张成的规范化 QRect（左上角不一定来自 a）。

    注意：不能用 QRect(a, b).normalized()——QRect 的 bottomRight 为闭区间语义，
    角点顺序颠倒时 normalized() 会产生 1px 偏移并收缩尺寸（左/上 +1，右/下 -1）。
    这里统一取两点的最小/最大坐标，保证正拖与反拖得到同一矩形。
    """
    x1, x2 = sorted((a.x(), b.x()))
    y1, y2 = sorted((a.y(), b.y()))
    return QRect(QPoint(x1, y1), QPoint(x2, y2))


def arrow_head(start: QPointF, end: QPointF, length: float = 16.0, angle_deg: float = 28.0) -> QPolygonF:
    """生成箭头头部三角形，尖端位于 end，指向 start -> end。"""
    theta = math.atan2(end.y() - start.y(), end.x() - start.x())
    spread = math.radians(angle_deg)
    left = QPointF(end.x() - length * math.cos(theta - spread),
                   end.y() - length * math.sin(theta - spread))
    right = QPointF(end.x() - length * math.cos(theta + spread),
                    end.y() - length * math.sin(theta + spread))
    return QPolygonF([end, left, right])
