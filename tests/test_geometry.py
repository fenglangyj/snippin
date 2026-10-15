from PySide6.QtCore import QPoint, QPointF

from quicksnip.utils.geometry import arrow_head, normalize_rect


def test_normalize_rect_swapped_corners():
    rect = normalize_rect(QPoint(50, 60), QPoint(10, 20))
    assert rect.left() == 10
    assert rect.top() == 20
    assert rect.right() == 50
    assert rect.bottom() == 60


def test_arrow_head_tip_at_end():
    end = QPointF(100, 40)
    head = arrow_head(QPointF(0, 0), end)
    assert head.count() == 3
    tip = head.at(0)
    assert abs(tip.x() - end.x()) < 1e-6
    assert abs(tip.y() - end.y()) < 1e-6


def test_arrow_head_symmetric():
    head = arrow_head(QPointF(0, 0), QPointF(100, 0), length=14, angle_deg=30)
    left, right = head.at(1), head.at(2)
    assert abs(left.y() + right.y()) < 1e-6
    assert abs(left.x() - right.x()) < 1e-6
