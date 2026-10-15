"""T-06~T-10 遮罩层状态机回归测试（US-2~US-5）。

用 QTest 合成鼠标/键盘事件驱动 Overlay，覆盖：框选/最小尺寸/反向拖拽/重选清空、
六种标注、撤销、渲染裁剪、完成/取消/保存/贴图动作。离屏运行，无需真实显示器。
"""

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QFileDialog

from snippin.config import Config
from snippin.tools import ShapeType, Tool
from snippin.ui.overlay import _MIN_SELECTION, Overlay


def _base(w: int = 800, h: int = 600) -> QImage:
    img = QImage(w, h, QImage.Format.Format_ARGB32)
    img.fill(0xFF3366CC)
    return img


def _overlay(qapp) -> Overlay:
    ov = Overlay(_base(), Config())
    ov.resize(800, 600)
    ov.show()
    return ov


def _drag(ov: Overlay, a: QPoint, b: QPoint) -> None:
    QTest.mousePress(ov, Qt.MouseButton.LeftButton, pos=a)
    QTest.mouseMove(ov, pos=b)
    QTest.mouseRelease(ov, Qt.MouseButton.LeftButton, pos=b)


def test_selection_drag_enters_editing(qapp):
    ov = _overlay(qapp)
    _drag(ov, QPoint(100, 100), QPoint(300, 250))
    assert ov._editing is True
    assert ov._sel.topLeft() == QPoint(100, 100)
    assert ov._sel.width() == 201 and ov._sel.height() == 151
    assert ov._toolbar.isVisible()


def test_tiny_selection_is_rejected(qapp):
    ov = _overlay(qapp)
    _drag(ov, QPoint(100, 100), QPoint(100 + _MIN_SELECTION - 2, 100))
    assert ov._editing is False
    assert ov._sel.isNull()


def test_reverse_drag_normalizes(qapp):
    """反向拖拽（终点在起点左上方）应得到同一规范化矩形，无 1px 偏移。"""
    ov = _overlay(qapp)
    _drag(ov, QPoint(300, 250), QPoint(100, 100))
    assert ov._sel.topLeft() == QPoint(100, 100)
    assert ov._sel.bottomRight() == QPoint(300, 250)
    assert ov._sel.width() == 201 and ov._sel.height() == 151


def test_redrag_outside_clears_annotations(qapp):
    ov = _overlay(qapp)
    _drag(ov, QPoint(100, 100), QPoint(300, 250))
    # 画一个矩形
    ov._tool = Tool.RECT
    _drag(ov, QPoint(120, 120), QPoint(180, 180))
    assert len(ov._shapes) == 1
    # 在选区外重新拖拽 -> 清空标注并进入新选区
    _drag(ov, QPoint(20, 20), QPoint(400, 300))
    assert len(ov._shapes) == 0
    assert ov._editing is True


def _two_point_tools(qapp):
    return {
        Tool.RECT: ShapeType.RECT,
        Tool.ELLIPSE: ShapeType.ELLIPSE,
        Tool.ARROW: ShapeType.ARROW,
        Tool.MOSAIC: ShapeType.MOSAIC,
    }


def test_two_point_tools_create_shapes(qapp):
    for tool, stype in _two_point_tools(qapp).items():
        ov = _overlay(qapp)
        _drag(ov, QPoint(50, 50), QPoint(400, 400))
        ov._tool = tool
        _drag(ov, QPoint(80, 80), QPoint(200, 200))
        assert len(ov._shapes) == 1, tool
        assert ov._shapes[0].type is stype, tool


def test_pen_creates_polyline(qapp):
    ov = _overlay(qapp)
    _drag(ov, QPoint(50, 50), QPoint(400, 400))
    ov._tool = Tool.PEN
    QTest.mousePress(ov, Qt.MouseButton.LeftButton, pos=QPoint(90, 90))
    for x in (110, 130, 150):
        QTest.mouseMove(ov, pos=QPoint(x, x))
    QTest.mouseRelease(ov, Qt.MouseButton.LeftButton, pos=QPoint(150, 150))
    assert len(ov._shapes) == 1
    assert ov._shapes[0].type is ShapeType.PEN
    assert len(ov._shapes[0].points) >= 3


def test_text_tool_commits_shape(qapp):
    ov = _overlay(qapp)
    _drag(ov, QPoint(50, 50), QPoint(400, 400))
    ov._tool = Tool.TEXT
    ov._open_text_editor(QPoint(120, 120))
    ov._text_edit.setText("你好 snippin")
    ov._commit_text()
    assert len(ov._shapes) == 1
    assert ov._shapes[0].type is ShapeType.TEXT
    assert ov._shapes[0].text == "你好 snippin"


def test_undo_pops_last_shape(qapp):
    ov = _overlay(qapp)
    _drag(ov, QPoint(50, 50), QPoint(400, 400))
    ov._tool = Tool.RECT
    _drag(ov, QPoint(80, 80), QPoint(160, 160))
    _drag(ov, QPoint(200, 200), QPoint(300, 300))
    assert len(ov._shapes) == 2
    ov._undo()
    assert len(ov._shapes) == 1


def test_undo_via_delete_key(qapp):
    ov = _overlay(qapp)
    _drag(ov, QPoint(50, 50), QPoint(400, 400))
    ov._tool = Tool.RECT
    _drag(ov, QPoint(80, 80), QPoint(160, 160))
    QTest.keyPress(ov, Qt.Key.Key_Delete)
    assert len(ov._shapes) == 0


def test_render_size_and_empty(qapp):
    ov = _overlay(qapp)
    assert ov._render() is None  # 未选区
    _drag(ov, QPoint(100, 100), QPoint(300, 250))
    img = ov._render()
    assert img is not None
    assert img.width() == 201 and img.height() == 151


def test_enter_emits_copy(qapp):
    ov = _overlay(qapp)
    spy = QSignalSpy(ov.finished)
    _drag(ov, QPoint(100, 100), QPoint(300, 250))
    QTest.keyPress(ov, Qt.Key.Key_Return)
    assert spy.count() == 1
    action, image, _ = spy.at(0)
    assert action == Overlay.COPY
    assert isinstance(image, QImage) and image.width() == 201


def test_double_click_inside_selection_completes(qapp):
    ov = _overlay(qapp)
    spy = QSignalSpy(ov.finished)
    _drag(ov, QPoint(100, 100), QPoint(300, 250))
    QTest.mouseDClick(ov, Qt.MouseButton.LeftButton, pos=QPoint(200, 180))
    assert spy.count() == 1
    assert spy.at(0)[0] == Overlay.COPY


def test_escape_emits_cancel(qapp):
    ov = _overlay(qapp)
    spy = QSignalSpy(ov.finished)
    _drag(ov, QPoint(100, 100), QPoint(300, 250))
    QTest.keyPress(ov, Qt.Key.Key_Escape)
    assert spy.count() == 1
    assert spy.at(0)[0] == Overlay.CANCEL


def test_save_action_writes_file(qapp, tmp_path, monkeypatch):
    ov = _overlay(qapp)
    spy = QSignalSpy(ov.finished)
    target = tmp_path / "shot.png"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName",
        staticmethod(lambda *a, **k: (str(target), "PNG 图片 (*.png)")))
    _drag(ov, QPoint(100, 100), QPoint(300, 250))
    ov._on_save()
    assert spy.count() == 1
    action, _, path = spy.at(0)
    assert action == Overlay.SAVE
    assert path == str(target) and target.exists()


def test_pin_action_emits_pin(qapp):
    ov = _overlay(qapp)
    spy = QSignalSpy(ov.finished)
    _drag(ov, QPoint(100, 100), QPoint(300, 250))
    ov._on_pin()
    assert spy.count() == 1
    assert spy.at(0)[0] == Overlay.PIN
