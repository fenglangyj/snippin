"""文字提取（OCR）契约 —— 冻结接口，实现引擎时不得修改本文件签名。

设计约束（见 docs/ARCHITECTURE.md）：
- 默认引擎为 Windows 系统 OCR API（Windows.Media.Ocr）：离线、图片不出本机；
- 引擎模块不得在 import 期引入平台专属依赖，缺失时由 available() 返回 False；
- recognize() 输入为选区图像（QImage），输出为纯数据 OcrResult。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from PySide6.QtGui import QImage


@dataclass(frozen=True)
class TextBlock:
    """一块识别出的文本及其在图像中的位置（单位：像素）。"""

    text: str
    x: int
    y: int
    width: int
    height: int
    confidence: float | None = None


@dataclass(frozen=True)
class OcrResult:
    """一次识别的完整结果；text 为按阅读顺序拼接的全文。"""

    text: str
    blocks: tuple[TextBlock, ...] = ()
    engine: str = ""


class OcrError(RuntimeError):
    """OCR 引擎不可用或识别失败。异常信息面向用户，不得包含敏感数据。"""


@runtime_checkable
class OcrEngine(Protocol):
    """OCR 引擎契约。"""

    name: str

    def available(self) -> bool:
        """当前环境是否可用（平台、系统语言包、可选依赖是否满足）。"""

    def unavailable_reason(self) -> str:
        """不可用原因（面向用户，例如「需要 Windows 10 及以上」）；可用时返回空串。"""

    def recognize(self, image: QImage) -> OcrResult:
        """识别图像中的文字；图像为空或环境不可用时抛 OcrError。"""
