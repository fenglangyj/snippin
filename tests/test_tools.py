from PySide6.QtCore import QPoint

from snippin.tools import Shape, ShapeType, Tool


def test_tool_and_shape_names_match():
    assert {t.name for t in Tool} == {s.name for s in ShapeType}


def test_shape_defaults():
    shape = Shape(type=ShapeType.RECT, points=[QPoint(1, 2), QPoint(3, 4)])
    assert shape.color
    assert shape.width >= 1
    assert shape.text == ""
    assert shape.font_size >= 8
