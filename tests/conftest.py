import os
import sys

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session", autouse=True)
def qapp():
    """QPixmap/QScreen 等 GUI 类要求存在 QGuiApplication；非 Windows 环境用 offscreen。"""
    if sys.platform != "win32":
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    yield app
