import os
import sys

import pytest
from PySide6.QtGui import QImage

from snippin.ocr import registry
from snippin.ocr.base import OcrError
from snippin.ocr.windows import _INSTALL_GUIDANCE, WindowsOcrEngine


def _make_sample(path: str) -> None:
    from PySide6.QtGui import QColor, QFont, QPainter
    from PySide6.QtWidgets import QApplication
    if QApplication.instance() is None:
        QApplication([])
    img = QImage(700, 220, QImage.Format.Format_ARGB32)
    img.fill(QColor("white"))
    p = QPainter(img)
    p.setPen(QColor("black"))
    p.setFont(QFont("Microsoft YaHei", 26))
    p.drawText(30, 60, "你好，世界 Hello")
    p.drawText(30, 130, "截图工具 snippin 测试")
    p.end()
    assert img.save(path, "PNG")


def test_engine_registered_in_registry():
    assert "windows" in registry.registered()


def test_contract_surface():
    eng = WindowsOcrEngine()
    assert eng.name == "windows"
    assert isinstance(eng.available(), bool)
    assert isinstance(eng.unavailable_reason(), str)


def test_recognize_empty_image_raises():
    eng = WindowsOcrEngine()
    with pytest.raises(OcrError):
        eng.recognize(QImage())


@pytest.mark.skipif(sys.platform == "win32", reason="非 Windows 平台探测应给出可读原因并不崩溃")
def test_non_windows_unavailable_reason():
    eng = WindowsOcrEngine()
    assert eng.available() is False
    assert "Windows" in eng.unavailable_reason()


def test_result_mapping_from_script(monkeypatch):
    """_run 的 JSON -> OcrResult 映射（不依赖真机 OCR）。"""
    eng = WindowsOcrEngine()
    monkeypatch.setattr(eng, "available", lambda: True)
    payload = {"engine": "zh-Hans-CN", "text": "你好 Hello",
               "lines": [{"text": "你好 Hello", "x": 30, "y": 34, "width": 271, "height": 42}]}
    monkeypatch.setattr(eng, "_run", lambda image: payload)
    img = QImage(10, 10, QImage.Format.Format_ARGB32)
    result = eng.recognize(img)
    assert result.text == "你好 Hello"
    assert result.engine == "windows"
    assert len(result.blocks) == 1
    b = result.blocks[0]
    assert (b.text, b.x, b.y, b.width, b.height) == ("你好 Hello", 30, 34, 271, 42)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows 探测路径单测")
def test_no_language_guidance(monkeypatch):
    eng = WindowsOcrEngine()
    monkeypatch.setattr(WindowsOcrEngine, "_ps", staticmethod(lambda *a: "NO-LANGUAGE\n"))
    assert eng.available() is False
    assert _INSTALL_GUIDANCE[:12] in eng.unavailable_reason()


@pytest.mark.skipif(not (sys.platform == "win32" and os.environ.get("SNIPPIN_SMOKE")),
                    reason="真机 OCR 冒烟需 SNIPPIN_SMOKE=1（Windows + 系统 OCR 语言包）")
def test_real_recognize_chinese_english(tmp_path):
    eng = WindowsOcrEngine()
    assert eng.available(), eng.unavailable_reason()
    png = str(tmp_path / "sample.png")
    _make_sample(png)
    img = QImage(png)
    result = eng.recognize(img)
    compact = result.text.replace(" ", "")  # zh-Hans 识别器在字/词间插入空格
    assert "Hello" in compact, result.text
    assert "世界" in compact or "截图" in compact or "你好" in compact, result.text
    assert result.blocks, "应返回行级坐标块"
    b = result.blocks[0]
    assert b.width > 0 and b.height > 0
