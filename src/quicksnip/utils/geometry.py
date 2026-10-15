import math

from PySide6.QtCore import QPoint, QPointF, QRect
from PySide6.QtGui import QPolygonF


def normalize_rect(a: QPoint, b: QPoint) -> QRect:
    """返回由两个角点张成的规范化 QRect（左上角不一定来自 a）。"""
    return QRect(a, b).normalized()


def arrow_head(start: QPointF, end: QPointF, length: float = 16.0, angle_deg: float = 28.0) -> QPolygonF:
    """生成箭头头部三角形，尖端位于 end，指向 start -> end。"""
    theta = math.atan2(end.y() - start.y(), end.x() - start.x())
    spread = math.radians(angle_deg)
    left = QPointF(end.x() - length * math.cos(theta - spread),
                   end.y() - length * math.sin(theta - spread))
    right = QPointF(end.x() - length * math.cos(theta + spread),
                    end.y() - length * math.sin(theta + spread))
    return QPolygonF([end, left, right])
