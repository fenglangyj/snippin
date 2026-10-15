import pytest

from snippin.ocr import registry as ocr_registry
from snippin.ocr.base import OcrError, OcrResult, TextBlock
from snippin.translate import registry as tr_registry
from snippin.translate.base import TranslationError, TranslationResult


class _FakeEngine:
    name = "fake"

    def __init__(self, ok: bool = True) -> None:
        self.ok = ok

    def available(self) -> bool:
        return self.ok

    def unavailable_reason(self) -> str:
        return "" if self.ok else "测试用不可用原因"

    def recognize(self, image) -> OcrResult:
        return OcrResult(text="hello", blocks=(TextBlock("hello", 0, 0, 10, 10),), engine=self.name)


class _FakeProvider:
    name = "fake-provider"
    requires_secret = True
    supported_targets = ("zh", "en")

    def __init__(self, ok: bool = True) -> None:
        self.ok = ok

    def available(self) -> bool:
        return self.ok

    def unavailable_reason(self) -> str:
        return "" if self.ok else "尚未配置 API 密钥"

    def translate(self, text: str, target_lang: str = "zh", source_lang: str = "auto") -> TranslationResult:
        return TranslationResult(source_text=text, target_text=f"[{target_lang}]{text}",
                                 provider=self.name, source_lang=source_lang,
                                 target_lang=target_lang)


def test_ocr_result_defaults():
    result = OcrResult(text="abc")
    assert result.blocks == ()
    assert result.engine == ""
    assert result.text == "abc"


def test_ocr_registry_selects_registered_engine():
    ocr_registry.register_engine("fake", lambda: _FakeEngine())
    engine = ocr_registry.get_engine("fake")
    assert engine.name == "fake"
    assert engine.recognize(None).text == "hello"
    assert ocr_registry.get_engine("fake") is engine  # 实例被缓存


def test_ocr_registry_reports_reason_when_unavailable():
    ocr_registry.register_engine("fake-down", lambda: _FakeEngine(ok=False))
    with pytest.raises(OcrError) as exc:
        ocr_registry.get_engine("fake-down")
    assert "测试用不可用原因" in str(exc.value)


def test_ocr_registry_rejects_unknown_engine():
    with pytest.raises(OcrError):
        ocr_registry.get_engine("no-such-engine")


def test_translate_provider_contract():
    tr_registry.register_provider("fake-provider", lambda: _FakeProvider())
    provider = tr_registry.get_provider("fake-provider")
    result = provider.translate("你好", target_lang="en")
    assert result.target_text == "[en]你好"
    assert result.provider == "fake-provider"


def test_translate_registry_reports_reason_when_unconfigured():
    tr_registry.register_provider("fake-unconfigured", lambda: _FakeProvider(ok=False))
    with pytest.raises(TranslationError) as exc:
        tr_registry.get_provider("fake-unconfigured")
    assert "尚未配置 API 密钥" in str(exc.value)
