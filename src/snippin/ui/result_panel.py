"""文字提取 / 翻译 结果面板（T-22 / T-24）。

- 均通过冻结契约的 registry 获取引擎 / provider，不直接依赖具体实现，
  因此可在后端（T-21 / T-23）完成前用假引擎联调。
- 引擎 / provider 不可用时，展示其 unavailable_reason 作为面向用户的引导（R-09 / R-11 / R-12）。
- 文本区可选中、可编辑、一键复制；翻译面板支持目标语言切换。

视觉沿用遮罩工具条的暗色风格，待 UI 设计师 T-02 定稿后统一替换。
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..config import Config
from ..ocr import registry as ocr_registry
from ..ocr.base import OcrError, OcrResult
from ..translate import registry as tr_registry
from ..translate.base import TranslationError, TranslationResult

# provider 未就绪时的兜底目标语言，仅用于渲染语言下拉，不承诺可翻译。
_DEFAULT_TARGETS = ("zh", "en", "ja", "ko", "fr", "de", "es", "ru")
_LANG_NAMES = {
    "zh": "中文", "en": "英语", "ja": "日语", "ko": "韩语",
    "fr": "法语", "de": "德语", "es": "西班牙语", "ru": "俄语",
    "auto": "自动检测",
}

_PANEL_QSS = """
QWidget#panel { background: #262626; }
QWidget#panel QLabel { color: #c8c8c8; font-size: 13px; }
QWidget#panel QLabel#title { color: #f0f0f0; font-size: 15px; font-weight: 600; }
QWidget#panel QLabel#guidance { color: #FAAD14; font-size: 13px; }
QWidget#panel QPlainTextEdit {
    background: #1c1c1c; color: #f0f0f0; border: 1px solid #3a3a3a;
    border-radius: 6px; padding: 8px; font-size: 14px;
    selection-background-color: #1890FF; selection-color: #ffffff;
}
QWidget#panel QPushButton {
    background: #333333; color: #eeeeee; border: 1px solid #454545;
    border-radius: 5px; padding: 6px 14px;
}
QWidget#panel QPushButton:hover { background: #1890FF; border-color: #1890FF; }
QWidget#panel QPushButton:pressed { background: #0f6fc4; }
QWidget#panel QPushButton#primary { background: #1890FF; border-color: #1890FF; }
QWidget#panel QPushButton#primary:hover { background: #3aa0ff; }
QWidget#panel QComboBox {
    background: #333333; color: #eeeeee; border: 1px solid #454545;
    border-radius: 5px; padding: 4px 10px;
}
QWidget#panel QComboBox QAbstractItemView {
    background: #2b2b2b; color: #eeeeee; border: 1px solid #454545;
    selection-background-color: #1890FF;
}
"""


def _lang_label(code: str) -> str:
    name = _LANG_NAMES.get(code)
    return f"{name} ({code})" if name else code


def run_ocr(image: QImage, cfg: Config) -> OcrResult:
    """按配置引擎识别选区文字；配置引擎缺失时回退到第一个可用引擎。

    引擎不可用（未安装 / 缺语言包）时抛 OcrError，异常信息即用户引导。
    """
    name = cfg.ocr_engine or None
    try:
        engine = ocr_registry.get_engine(name)
    except OcrError:
        if not name:
            raise
        engine = ocr_registry.get_engine(None)  # 回退：自动选择第一个可用引擎
    return engine.recognize(image)


def run_translate(text: str, target_lang: str, cfg: Config) -> TranslationResult:
    """按配置 provider 翻译文本；未配置 / 失败时抛 TranslationError。"""
    provider = tr_registry.get_provider(cfg.translate_provider or None)
    return provider.translate(text, target_lang=target_lang)


class _PanelBase(QWidget):
    """结果面板通用外壳：标题 + 内容区插槽 + 底部按钮行。"""

    def __init__(self, title: str, cfg: Config) -> None:
        super().__init__(None, Qt.WindowType.Window)
        self._cfg = cfg
        self.setObjectName("panel")
        self.setWindowTitle(f"snippin · {title}")
        self.setStyleSheet(_PANEL_QSS)
        self.resize(540, 440)
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(16, 14, 16, 14)
        self._root.setSpacing(10)
        head = QHBoxLayout()
        lbl = QLabel(title)
        lbl.setObjectName("title")
        head.addWidget(lbl)
        head.addStretch(1)
        self._root.addLayout(head)
        self._actions = QHBoxLayout()
        self._actions.setSpacing(8)

    def _add_button(self, text: str, slot, primary: bool = False) -> QPushButton:
        btn = QPushButton(text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(slot)
        if primary:
            btn.setObjectName("primary")
        return btn

    def _footer(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addStretch(1)
        return row


class OcrPanel(_PanelBase):
    """文字提取结果面板（T-22，US-7）。"""

    translate_requested = Signal(str)  # 携带识别文本，请求翻译

    def __init__(self, image: QImage, cfg: Config) -> None:
        super().__init__("提取文字", cfg)
        self._edit = QPlainTextEdit()
        self._edit.setPlaceholderText("识别结果将显示在此处，可选中、编辑或复制。")
        self._edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self._root.addWidget(self._edit, 1)

        self._guidance = QLabel()
        self._guidance.setObjectName("guidance")
        self._guidance.setWordWrap(True)
        self._guidance.hide()
        self._root.addWidget(self._guidance)

        row = self._footer()
        self._copy_btn = self._add_button("复制全部", self._copy_all)
        self._translate_btn = self._add_button("翻译", self._request_translate, primary=True)
        row.addWidget(self._copy_btn)
        row.addWidget(self._translate_btn)
        row.addWidget(self._add_button("关闭", self.close))
        self._root.addLayout(row)

        self._recognize(image)

    def _recognize(self, image: QImage) -> None:
        try:
            result = run_ocr(image, self._cfg)
        except OcrError as exc:
            self._show_guidance(str(exc))
            return
        self._edit.setPlainText(result.text)
        engine = result.engine or self._cfg.ocr_engine
        if result.text.strip():
            self._show_guidance(f"识别完成 · 引擎：{engine}")
        else:
            self._show_guidance(f"未在选区内识别到文字 · 引擎：{engine}")

    def _show_guidance(self, message: str) -> None:
        self._guidance.setText(message)
        self._guidance.show()

    def _copy_all(self) -> None:
        text = self._edit.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            self._show_guidance("已复制全部文字到剪贴板")

    def _request_translate(self) -> None:
        text = self._edit.toPlainText().strip()
        if text:
            self.translate_requested.emit(text)


class TranslatePanel(_PanelBase):
    """翻译结果面板与语言选择（T-24，US-8）。"""

    def __init__(self, source_text: str, cfg: Config) -> None:
        super().__init__("翻译", cfg)

        self._source = QPlainTextEdit()
        self._source.setPlaceholderText("待翻译文本（可由「提取文字」带入，或直接粘贴 / 输入）")
        self._source.setPlainText(source_text)
        self._source.setMaximumHeight(120)
        self._root.addWidget(QLabel("原文"))
        self._root.addWidget(self._source)

        lang_row = QHBoxLayout()
        lang_row.addWidget(QLabel("目标语言"))
        self._lang = QComboBox()
        self._lang.setCursor(Qt.CursorShape.PointingHandCursor)
        lang_row.addWidget(self._lang)
        lang_row.addSpacing(10)
        lang_row.addWidget(self._add_button("翻译", self._translate, primary=True))
        lang_row.addStretch(1)
        self._root.addLayout(lang_row)

        self._root.addWidget(QLabel("译文"))
        self._target = QPlainTextEdit()
        self._target.setPlaceholderText("译文将显示在此处，可选中、编辑或复制。")
        self._root.addWidget(self._target, 1)

        self._guidance = QLabel()
        self._guidance.setObjectName("guidance")
        self._guidance.setWordWrap(True)
        self._guidance.hide()
        self._root.addWidget(self._guidance)

        row = self._footer()
        row.addWidget(self._add_button("复制译文", self._copy_target))
        row.addWidget(self._add_button("关闭", self.close))
        self._root.addLayout(row)

        self._populate_languages()
        if source_text.strip():
            self._translate()

    def _populate_languages(self) -> None:
        targets = _DEFAULT_TARGETS
        configured = True
        try:
            provider = tr_registry.get_provider(self._cfg.translate_provider or None)
            targets = tuple(provider.supported_targets) or _DEFAULT_TARGETS
        except TranslationError as exc:
            configured = False
            self._show_guidance(str(exc))
        current = self._cfg.translate_target_lang
        for code in targets:
            self._lang.addItem(_lang_label(code), code)
        idx = self._lang.findData(current)
        if idx >= 0:
            self._lang.setCurrentIndex(idx)
        elif targets:
            self._lang.setCurrentIndex(0)
        if not configured:
            self._lang.setEnabled(True)  # 仍允许选择，翻译时给出配置引导

    def _target_lang(self) -> str:
        return self._lang.currentData() or self._cfg.translate_target_lang

    def _translate(self) -> None:
        text = self._source.toPlainText().strip()
        if not text:
            self._show_guidance("请先输入或粘贴要翻译的文本")
            return
        try:
            result = run_translate(text, self._target_lang(), self._cfg)
        except TranslationError as exc:
            self._show_guidance(str(exc))
            return
        self._target.setPlainText(result.target_text)
        self._show_guidance(f"翻译完成 · 服务：{result.provider} · "
                            f"{result.source_lang} → {result.target_lang}")

    def _copy_target(self) -> None:
        text = self._target.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            self._show_guidance("已复制译文到剪贴板")

    def _show_guidance(self, message: str) -> None:
        self._guidance.setText(message)
        self._guidance.show()
