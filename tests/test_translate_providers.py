import io
import json
import urllib.error
import urllib.request

import pytest

from snippin.translate import registry
from snippin.translate.base import TranslationError
from snippin.translate.providers import _SECRET_GUIDANCE, DeepLProvider

FAKE_SECRET = "FAKE-SECRET-1234:fx"


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()
        return False


def _payload(text: str) -> bytes:
    return json.dumps({"source_lang": "EN",
                       "translations": [{"text": text, "detected_language": "en"}]}).encode()


@pytest.fixture
def with_secret(monkeypatch):
    monkeypatch.setattr(DeepLProvider, "_secret", staticmethod(lambda: FAKE_SECRET))


def test_provider_registered_in_registry():
    assert "deepl" in registry.registered()


def test_contract_surface():
    p = DeepLProvider()
    assert p.name == "deepl"
    assert p.requires_secret is True
    assert "zh" in p.supported_targets and "en" in p.supported_targets
    assert isinstance(p.available(), bool)
    assert isinstance(p.unavailable_reason(), str)


def test_missing_secret_gives_guidance(monkeypatch):
    monkeypatch.setattr(DeepLProvider, "_secret", staticmethod(lambda: ""))
    p = DeepLProvider()
    assert p.available() is False
    assert p.unavailable_reason() == _SECRET_GUIDANCE
    with pytest.raises(TranslationError) as ei:
        p.translate("hello", "zh")
    assert "密钥" in str(ei.value)


def test_empty_text_raises():
    p = DeepLProvider()
    with pytest.raises(TranslationError):
        p.translate("   ", "zh")


def test_unsupported_target_lang(monkeypatch):
    monkeypatch.setattr(DeepLProvider, "_secret", staticmethod(lambda: FAKE_SECRET))
    p = DeepLProvider()
    with pytest.raises(TranslationError) as ei:
        p.translate("hello", "klingon")
    assert "klingon" in str(ei.value)
    assert FAKE_SECRET not in str(ei.value)


def test_translate_maps_request_and_result(monkeypatch, with_secret):
    captured = {}

    def fake_open(request, timeout=None):
        captured["url"] = request.full_url
        captured["headers"] = {k.lower(): v for k, v in request.header_items()}
        captured["body"] = request.data.decode("utf-8")
        captured["timeout"] = timeout
        return _Resp(_payload("你好"))

    monkeypatch.setattr(urllib.request, "urlopen", fake_open)
    result = DeepLProvider().translate("hello", target_lang="zh", source_lang="auto")
    assert result.target_text == "你好"
    assert result.provider == "deepl"
    assert result.source_lang == "en"
    assert result.target_lang == "zh"
    assert captured["url"] == "https://api-free.deepl.com/v2/translate"
    assert captured["headers"]["authorization"] == f"DeepL-Auth-Key {FAKE_SECRET}"
    assert "text=hello" in captured["body"]
    assert "target_lang=ZH" in captured["body"]
    assert "source_lang=AUTO" in captured["body"]


def test_http_403_readable_error_without_secret(monkeypatch, with_secret):
    def fake_open(request, timeout=None):
        raise urllib.error.HTTPError(request.full_url, 403, "Forbidden", {}, None)

    monkeypatch.setattr(urllib.request, "urlopen", fake_open)
    with pytest.raises(TranslationError) as ei:
        DeepLProvider().translate("hello", "zh")
    assert "密钥无效" in str(ei.value)
    assert FAKE_SECRET not in str(ei.value)


def test_http_429_quota_hint(monkeypatch, with_secret):
    def fake_open(request, timeout=None):
        raise urllib.error.HTTPError(request.full_url, 429, "Too Many Requests", {}, None)

    monkeypatch.setattr(urllib.request, "urlopen", fake_open)
    with pytest.raises(TranslationError) as ei:
        DeepLProvider().translate("hello", "zh")
    assert "配额" in str(ei.value)


def test_network_error_readable_without_secret(monkeypatch, with_secret):
    def fake_open(request, timeout=None):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(urllib.request, "urlopen", fake_open)
    with pytest.raises(TranslationError) as ei:
        DeepLProvider().translate("hello", "zh")
    assert "无法连接" in str(ei.value)
    assert FAKE_SECRET not in str(ei.value)


def test_malformed_json_error(monkeypatch, with_secret):
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda request, timeout=None: _Resp(b"<html>not json</html>"))
    with pytest.raises(TranslationError) as ei:
        DeepLProvider().translate("hello", "zh")
    assert "解析失败" in str(ei.value)
    assert FAKE_SECRET not in str(ei.value)


def test_get_provider_default_skips_unconfigured(monkeypatch):
    """缺省选择：唯一 provider 未配置密钥时应抛出带引导的 TranslationError。

    注意：test_contracts.py 会向全局 registry 注册 fake provider 且跨文件不还原
    （预存污染，见移交项），故本用例自行隔离 _FACTORIES/_INSTANCES。
    """
    monkeypatch.setattr(DeepLProvider, "_secret", staticmethod(lambda: ""))
    factories, instances = registry._FACTORIES, registry._INSTANCES
    registry._FACTORIES = {"deepl": DeepLProvider}
    registry._INSTANCES = {"deepl": DeepLProvider()}
    try:
        with pytest.raises(TranslationError) as ei:
            registry.get_provider()
        assert "没有已配置的翻译服务" in str(ei.value)
        assert "deepl" in str(ei.value)
    finally:
        registry._FACTORIES, registry._INSTANCES = factories, instances


@pytest.mark.skipif("not DeepLProvider().available()", reason="真实密钥集成测需已配置 deepl 密钥")
def test_real_translate_en_to_zh():
    result = DeepLProvider().translate("Hello world", target_lang="zh")
    assert result.target_text
    assert result.provider == "deepl"
