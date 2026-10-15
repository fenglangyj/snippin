from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QImage, QKeyEvent, QMouseEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLineEdit, QToolButton, QWidget

from ..config import Config
from ..tools import Shape, ShapeType, Tool, draw_shape
from ..utils.geometry import normalize_rect

_MIN_SELECTION = 10  # 选区最小边长（像素）


class Overlay(QWidget):
    """全屏遮罩层：框选区域 -> 标注 -> 保存/复制/贴图。

    坐标系即虚拟桌面坐标系，与抓屏图像一一对应。
    """

    CANCEL, COPY, SAVE, PIN, OCR, TRANSLATE = range(6)
    finished = Signal(int, object, str)  # action, QImage|None, 保存路径（若已保存）

    _DIM = QColor(0, 0, 0, 110)
    _BORDER = QColor("#00A6FF")

    def __init__(self, base: QImage, cfg: Config) -> None:
        super().__init__()
        self._base = base
        self._cfg = cfg
        factor = max(4, min(base.width(), base.height()) // 150)
        small = base.scaled(base.width() // factor, base.height() // factor,
                            Qt.AspectRatioMode.IgnoreAspectRatio,
                            Qt.TransformationMode.FastTransformation)
        self._mosaic = small.scaled(base.width(), base.height(),
                                    Qt.AspectRatioMode.IgnoreAspectRatio,
                                    Qt.TransformationMode.FastTransformation)
        self._sel = QRect()
        self._anchor = QPoint()
        self._editing = False
        self._tool = Tool.RECT
        self._shapes: list[Shape] = []
        self._current: Shape | None = None
        self._text_edit: QLineEdit | None = None
        self._text_origin = QPoint()

        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setWindowFlag(Qt.WindowType.Tool, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        self._toolbar = self._build_toolbar()
        self._toolbar.hide()

    # ---------- 绘制 ----------

    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self)
        p.drawImage(0, 0, self._base)
        p.fillRect(self.rect(), self._DIM)
        if not self._sel.isNull():
            p.drawImage(self._sel, self._base, self._sel)
            # 标注裁剪到选区内，与输出图像保持一致（拖出选区外的笔画不显示）
            p.save()
            p.setClipRect(self._sel)
            for shape in self._shapes:
                draw_shape(p, shape, self._mosaic)
            if self._current is not None:
                draw_shape(p, self._current, self._mosaic)
            p.restore()
            p.setPen(QPen(self._BORDER, 1))
            p.drawRect(self._sel.adjusted(0, 0, -1, -1))
        p.end()

    # ---------- 鼠标 ----------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position().toPoint()
        if not self._editing:
            self._start_selection(pos)
            return
        if self._sel.contains(pos):
            if self._tool is Tool.TEXT:
                self._open_text_editor(pos)
            else:
                self._current = Shape(type=ShapeType[self._tool.name], points=[pos, pos],
                                      color=self._cfg.annotation_color,
                                      width=self._cfg.line_width)
        else:
            self._shapes.clear()
            self._editing = False
            self._start_selection(pos)
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        if not self._editing:
            if not self._sel.isNull():
                self._sel = normalize_rect(self._anchor, pos)
                self.update()
            return
        if self._current is not None:
            if self._current.type is ShapeType.PEN:
                self._current.points.append(pos)
            else:
                self._current.points[1] = pos
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position().toPoint()
        if not self._editing:
            self._sel = normalize_rect(self._anchor, pos)
            if self._sel.width() >= _MIN_SELECTION and self._sel.height() >= _MIN_SELECTION:
                self._editing = True
                self._place_toolbar()
            else:
                self._sel = QRect()
            self.update()
            return
        if self._current is not None:
            if self._current.type is not ShapeType.PEN:
                rect = normalize_rect(self._current.points[0], self._current.points[1])
                if rect.width() >= 2 and rect.height() >= 2:
                    self._shapes.append(self._current)
            elif len(self._current.points) >= 2:
                self._shapes.append(self._current)
            self._current = None
            self.update()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if self._editing and self._sel.contains(event.position().toPoint()):
            self._on_copy_done()

    # ---------- 键盘 ----------

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self._cancel()
        elif key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and self._editing:
            self._undo()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self._editing:
            self._on_copy_done()

    # ---------- 工具条 ----------

    def _build_toolbar(self) -> QWidget:
        bar = QWidget(self)
        bar.setObjectName("toolbar")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(2)
        self._tool_buttons: dict[Tool, QToolButton] = {}
        for tool, label in [(Tool.RECT, "矩形"), (Tool.ELLIPSE, "椭圆"), (Tool.ARROW, "箭头"),
                            (Tool.PEN, "画笔"), (Tool.TEXT, "文字"), (Tool.MOSAIC, "马赛克")]:
            btn = self._mk_btn(label, lambda checked=False, t=tool: self._set_tool(t), checkable=True)
            self._tool_buttons[tool] = btn
            lay.addWidget(btn)
        lay.addWidget(self._mk_btn("撤销", lambda checked=False: self._undo()))
        lay.addSpacing(6)
        lay.addWidget(self._mk_btn("提取文字", lambda checked=False: self._on_ocr()))
        lay.addWidget(self._mk_btn("翻译", lambda checked=False: self._on_translate()))
        lay.addSpacing(6)
        lay.addWidget(self._mk_btn("保存", lambda checked=False: self._on_save()))
        lay.addWidget(self._mk_btn("贴图", lambda checked=False: self._on_pin()))
        lay.addWidget(self._mk_btn("✓ 完成", lambda checked=False: self._on_copy_done()))
        lay.addWidget(self._mk_btn("✕", lambda checked=False: self._cancel()))
        bar.setStyleSheet(
            "QWidget#toolbar { background: rgba(38,38,38,235); border-radius: 6px; }"
            "QToolButton { color: #eee; background: transparent; border: none;"
            " padding: 5px 8px; border-radius: 4px; }"
            "QToolButton:hover { background: #1890FF; }"
            "QToolButton:checked { background: #1890FF; }"
        )
        self._tool_buttons[Tool.RECT].setChecked(True)
        return bar

    def _mk_btn(self, text: str, slot, checkable: bool = False) -> QToolButton:
        btn = QToolButton()
        btn.setText(text)
        btn.setCheckable(checkable)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(slot)
        return btn

    def _set_tool(self, tool: Tool) -> None:
        self._tool = tool
        for t, btn in self._tool_buttons.items():
            btn.setChecked(t is tool)
        self.setCursor(Qt.CursorShape.IBeamCursor if tool is Tool.TEXT else Qt.CursorShape.CrossCursor)

    def _place_toolbar(self) -> None:
        self._toolbar.adjustSize()
        margin = 8
        x = self._sel.right() - self._toolbar.width()
        y = self._sel.bottom() + margin
        if y + self._toolbar.height() > self.height():
            y = self._sel.top() - self._toolbar.height() - margin
        x = max(4, min(x, self.width() - self._toolbar.width() - 4))
        y = max(4, min(y, self.height() - self._toolbar.height() - 4))
        self._toolbar.move(x, y)
        self._toolbar.show()
        self._toolbar.raise_()

    # ---------- 内部逻辑 ----------

    def _start_selection(self, pos: QPoint) -> None:
        self._anchor = pos
        self._sel = QRect(pos, pos)
        self._toolbar.hide()

    def _open_text_editor(self, pos: QPoint) -> None:
        if self._text_edit is None:
            edit = QLineEdit(self)
            edit.setStyleSheet("background: rgba(30,30,30,220); color: white;"
                               " border: 1px solid #1890FF; padding: 2px 4px;")
            edit.returnPressed.connect(self._commit_text)
            self._text_edit = edit
        self._text_origin = pos
        self._text_edit.move(pos)
        self._text_edit.resize(180, 28)
        self._text_edit.clear()
        self._text_edit.show()
        self._text_edit.setFocus()

    def _commit_text(self) -> None:
        edit = self._text_edit
        if edit is None:
            return
        text = edit.text().strip()
        if text and not self._sel.isNull():
            self._shapes.append(Shape(type=ShapeType.TEXT, points=[self._text_origin],
                                      text=text, color="#FFFFFF",
                                      font_size=self._cfg.font_size))
        edit.hide()
        self.setFocus()
        self.update()

    def _undo(self) -> None:
        if self._shapes:
            self._shapes.pop()
            self.update()

    def _render(self) -> QImage | None:
        if self._sel.isNull() or self._sel.width() < 2 or self._sel.height() < 2:
            return None
        image = QImage(self._sel.size(), QImage.Format.Format_ARGB32)
        image.fill(0)
        p = QPainter(image)
        p.drawImage(QRect(0, 0, self._sel.width(), self._sel.height()), self._base, self._sel)
        p.translate(-self._sel.topLeft())
        for shape in self._shapes:
            draw_shape(p, shape, self._mosaic)
        if self._current is not None:
            draw_shape(p, self._current, self._mosaic)
        p.end()
        return image

    # ---------- 动作 ----------

    def _on_save(self) -> None:
        image = self._render()
        if image is None:
            return
        default = str(self._cfg.next_save_path())
        path, _ = QFileDialog.getSaveFileName(
            self, "保存截图", default, "PNG 图片 (*.png);;JPEG 图片 (*.jpg)")
        if path and image.save(path):
            self._done(self.SAVE, image, path)

    def _on_copy_done(self) -> None:
        image = self._render()
        if image is not None:
            self._done(self.COPY, image, "")

    def _on_pin(self) -> None:
        image = self._render()
        if image is not None:
            self._done(self.PIN, image, "")

    def _on_ocr(self) -> None:
        image = self._render()
        if image is not None:
            self._done(self.OCR, image, "")

    def _on_translate(self) -> None:
        image = self._render()
        if image is not None:
            self._done(self.TRANSLATE, image, "")

    def _cancel(self) -> None:
        self._done(self.CANCEL, None, "")

    def _done(self, action: int, image: QImage | None, path: str) -> None:
        self.finished.emit(action, image, path)
        self.close()
