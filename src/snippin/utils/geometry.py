import math

from PySide6.QtCore import QPoint, QPointF, QRect
from PySide6.QtGui import QPolygonF


def normalize_rect(a: QPoint, b: QPoint) -> QRect:
    """返回由两个角点张成的规范化 QRect（包含式角点，任意拖拽方向结果一致）。

    不使用 QRect(a, b).normalized()：Qt 对对角点反转的矩形行为未定义，
    实测会产生 1px 偏移与 2px 尺寸损失（缺陷 D-01，见 docs/RISKS.md R-02）。
    """
    x1, y1 = min(a.x(), b.x()), min(a.y(), b.y())
    x2, y2 = max(a.x(), b.x()), max(a.y(), b.y())
    return QRect(x1, y1, x2 - x1 + 1, y2 - y1 + 1)


def arrow_head(start: QPointF, end: QPointF, length: float = 16.0, angle_deg: float = 28.0) -> QPolygonF:
    """生成箭头头部三角形，尖端位于 end，指向 start -> end。"""
    theta = math.atan2(end.y() - start.y(), end.x() - start.x())
    spread = math.radians(angle_deg)
    left = QPointF(end.x() - length * math.cos(theta - spread),
                   end.y() - length * math.sin(theta - spread))
    right = QPointF(end.x() - length * math.cos(theta + spread),
                    end.y() - length * math.sin(theta + spread))
    return QPolygonF([end, left, right])
