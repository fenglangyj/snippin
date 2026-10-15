"""测试会话级夹具：强制离屏渲染，提供共享 QApplication。

离屏平台让基于 QTest 合成事件的 UI 测试无需真实显示器即可确定性地运行（CI 友好）。
"""

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance() or QApplication([])
    yield app
