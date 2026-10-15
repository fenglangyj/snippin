"""T-22 / T-24 结果面板测试（US-7 / US-8）。

用契约假引擎 / 假 provider 联调，验证：识别文本展示 / 一键复制 / 语言切换 / 翻译，
以及引擎或 provider 不可用时展示 unavailable_reason 作为引导（R-09 / R-11 / R-12）。
"""

from PySide6.QtGui import QImage

from snippin.config import Config
from snippin.ocr import registry as ocr_registry
from snippin.ocr.base import OcrError, OcrResult, TextBlock
from snippin.translate import registry as tr_registry
from snippin.translate.base import TranslationError, TranslationResult
from snippin.ui import result_panel
from snippin.ui.result_panel import OcrPanel, TranslatePanel, run_ocr, run_translate


def _img() -> QImage:
    im = QImage(40, 20, QImage.Format.Format_ARGB32)
    im.fill(0xFFFFFFFF)
    return im


def _cfg(**over) -> Config:
    cfg = Config()
    for k, v in over.items():
        setattr(cfg, k, v)
    return cfg


# ---------- 契约假实现 ----------

class _FakeEngine:
    name = "t22-fake"

    def available(self) -> bool:
        return True

    def unavailable_reason(self) -> str:
        return ""

    def recognize(self, image) -> OcrResult:
        return OcrResult(text="识别到的文字", blocks=(TextBlock("识别到的文字", 0, 0, 10, 10),),
                         engine=self.name)


class _FakeProvider:
    name = "t24-fake"
    requires_secret = True
    supported_targets = ("zh", "en", "ja")

    def available(self) -> bool:
        return True

    def unavailable_reason(self) -> str:
        return ""

    def translate(self, text, target_lang="zh", source_lang="auto") -> TranslationResult:
        return TranslationResult(source_text=text, target_text=f"[{target_lang}]{text}",
                                 provider=self.name, source_lang=source_lang,
                                 target_lang=target_lang)


# ---------- run_* 契约调用 ----------

def test_run_ocr_uses_registered_engine(qapp):
    ocr_registry.register_engine(_FakeEngine.name, _FakeEngine)
    result = run_ocr(_img(), _cfg(ocr_engine=_FakeEngine.name))
    assert result.text == "识别到的文字"
    assert result.engine == _FakeEngine.name


def test_run_ocr_falls_back_when_configured_engine_missing(qapp):
    ocr_registry.register_engine(_FakeEngine.name, _FakeEngine)
    # 配置了一个不存在的引擎名 -> 回退到第一个可用引擎，不抛异常
    result = run_ocr(_img(), _cfg(ocr_engine="t22-no-such-engine"))
    assert result.text  # 至少有一个可用引擎返回了文本


def test_run_translate_uses_registered_provider(qapp):
    tr_registry.register_provider(_FakeProvider.name, _FakeProvider)
    result = run_translate("你好", "en", _cfg(translate_provider=_FakeProvider.name))
    assert result.target_text == "[en]你好"
    assert result.provider == _FakeProvider.name


# ---------- OCR 面板 ----------

def test_ocr_panel_shows_recognized_text(qapp, monkeypatch):
    monkeypatch.setattr(result_panel, "run_ocr",
                        lambda image, cfg: OcrResult(text="面板文字", engine="fake"))
    panel = OcrPanel(_img(), _cfg())
    assert panel._edit.toPlainText() == "面板文字"
    assert not panel._guidance.isHidden()


def test_ocr_panel_copy_all(qapp, monkeypatch):
    from PySide6.QtWidgets import QApplication
    monkeypatch.setattr(result_panel, "run_ocr",
                        lambda image, cfg: OcrResult(text="复制到剪贴板", engine="fake"))
    panel = OcrPanel(_img(), _cfg())
    panel._copy_all()
    assert QApplication.clipboard().text() == "复制到剪贴板"


def test_ocr_panel_guidance_when_engine_unavailable(qapp, monkeypatch):
    def _boom(image, cfg):
        raise OcrError("需要 Windows 10 及以上并安装中文语言包")

    monkeypatch.setattr(result_panel, "run_ocr", _boom)
    panel = OcrPanel(_img(), _cfg())
    assert "Windows 10" in panel._guidance.text()
    assert panel._edit.toPlainText() == ""


def test_ocr_panel_translate_requested_signal(qapp, monkeypatch):
    monkeypatch.setattr(result_panel, "run_ocr",
                        lambda image, cfg: OcrResult(text="要翻译的内容", engine="fake"))
    panel = OcrPanel(_img(), _cfg())
    got = []
    panel.translate_requested.connect(got.append)
    panel._request_translate()
    assert got == ["要翻译的内容"]


# ---------- 翻译面板 ----------

def test_translate_panel_populates_and_translates(qapp, monkeypatch):
    monkeypatch.setattr(
        result_panel.tr_registry, "get_provider",
        lambda name=None: _FakeProvider())
    panel = TranslatePanel("你好", _cfg(translate_target_lang="en"))
    langs = [panel._lang.itemData(i) for i in range(panel._lang.count())]
    assert langs == ["zh", "en", "ja"]
    assert panel._lang.currentData() == "en"
    assert panel._target.toPlainText() == "[en]你好"


def test_translate_panel_language_switch(qapp, monkeypatch):
    monkeypatch.setattr(
        result_panel.tr_registry, "get_provider",
        lambda name=None: _FakeProvider())
    panel = TranslatePanel("hello", _cfg(translate_target_lang="zh"))
    idx = panel._lang.findData("ja")
    panel._lang.setCurrentIndex(idx)
    panel._translate()
    assert panel._target.toPlainText() == "[ja]hello"


def test_translate_panel_unconfigured_guidance(qapp, monkeypatch):
    def _raise(name=None):
        raise TranslationError("尚未配置 API 密钥，请在设置中填写翻译服务密钥")

    monkeypatch.setattr(result_panel.tr_registry, "get_provider", _raise)
    panel = TranslatePanel("text", _cfg())
    assert "尚未配置 API 密钥" in panel._guidance.text()
    # 仍提供兜底语言选择
    assert panel._lang.count() >= 2
    panel._translate()
    assert "尚未配置 API 密钥" in panel._guidance.text()
