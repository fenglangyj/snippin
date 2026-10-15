from dataclasses import dataclass
from enum import Enum, auto

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPolygonF

from .utils.geometry import arrow_head, normalize_rect


class Tool(Enum):
    RECT = auto()
    ELLIPSE = auto()
    ARROW = auto()
    PEN = auto()
    TEXT = auto()
    MOSAIC = auto()


class ShapeType(Enum):
    RECT = auto()
    ELLIPSE = auto()
    ARROW = auto()
    PEN = auto()
    TEXT = auto()
    MOSAIC = auto()


@dataclass
class Shape:
    """一条标注。points 为控件坐标：矩形/椭圆/箭头/马赛克取前两点，画笔为轨迹点集，文字为左上角。"""

    type: ShapeType
    points: list[QPoint]
    color: str = "#FF4D4F"
    width: int = 3
    text: str = ""
    font_size: int = 18


def draw_shape(p: QPainter, shape: Shape, mosaic: QImage | None) -> None:
    """在给定坐标系下绘制一条标注；坐标与抓屏图像一一对应。"""
    if shape.type is ShapeType.MOSAIC:
        if len(shape.points) >= 2 and mosaic is not None and not mosaic.isNull():
            rect = normalize_rect(shape.points[0], shape.points[1])
            p.drawImage(rect, mosaic, rect)
        return

    pen = QPen(QColor(shape.color))
    pen.setWidth(shape.width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)

    if shape.type is ShapeType.TEXT:
        font = QFont()
        font.setPointSize(shape.font_size)
        font.setBold(True)
        p.setFont(font)
        p.drawText(shape.points[0], shape.text)
        return

    if shape.type is ShapeType.PEN:
        if len(shape.points) >= 2:
            p.drawPolyline(QPolygonF([QPointF(pt) for pt in shape.points]))
        return

    if len(shape.points) < 2:
        return
    a, b = shape.points[0], shape.points[1]
    rect = normalize_rect(a, b)
    if shape.type is ShapeType.RECT:
        p.drawRect(rect)
    elif shape.type is ShapeType.ELLIPSE:
        p.drawEllipse(rect)
    elif shape.type is ShapeType.ARROW:
        p.drawLine(a, b)
        p.setBrush(QColor(shape.color))
        p.drawPolygon(arrow_head(QPointF(a), QPointF(b)))
