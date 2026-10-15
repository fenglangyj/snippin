from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QImage, QMouseEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import QApplication, QHBoxLayout, QMessageBox, QToolButton, QWidget

from ..config import Config


class PinWindow(QWidget):
    """贴图窗口：把截取的区域以置顶悬浮窗展示，可拖拽，悬停显示操作条。"""

    def __init__(self, image: QImage, cfg: Config) -> None:
        # QWidget 的窗口标志须作为第二位置参数 f 传入（不接受 flags= 关键字）。
        super().__init__(None, Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.Tool)
        self._image = image
        self._cfg = cfg
        self._drag_offset: QPoint | None = None
        self.setWindowTitle("snippin 贴图")
        self.resize(max(image.width(), 120), max(image.height(), 80))

        self._bar = QWidget(self)
        self._bar.setObjectName("pinbar")
        lay = QHBoxLayout(self._bar)
        lay.setContentsMargins(4, 2, 4, 2)
        for label, slot in [("保存", self._save), ("复制", self._copy), ("✕", self.close)]:
            btn = QToolButton()
            btn.setText(label)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(slot)
            lay.addWidget(btn)
        self._bar.setStyleSheet(
            "QWidget#pinbar { background: rgba(38,38,38,235); border-radius: 4px; }"
            "QToolButton { color: #eee; background: transparent; border: none; padding: 3px 8px; }"
            "QToolButton:hover { background: #1890FF; }"
        )
        self._bar.adjustSize()
        self._bar.move(max(self.width() - self._bar.width() - 4, 0), 4)
        self._bar.hide()

    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self)
        p.drawImage(self.rect(), self._image, self._image.rect())
        p.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None:
            self.move(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_offset = None

    def enterEvent(self, event) -> None:
        self._bar.show()

    def leaveEvent(self, event) -> None:
        self._bar.hide()

    def _save(self) -> None:
        path = self._cfg.next_save_path()
        if self._image.save(str(path)):
            QMessageBox.information(self, "snippin", f"已保存：{path}")
        else:
            QMessageBox.warning(self, "snippin", f"保存失败：{path}")

    def _copy(self) -> None:
        QApplication.clipboard().setImage(self._image)
