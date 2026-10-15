"""在线翻译 provider（T-23）。

首个服务商选定 **DeepL Free API**（D-1 选型理由）：
- 翻译质量（尤其中英互译）业界公认，免费档 50 万字符/月足够个人工具；
- 单 token（Auth Key）认证、纯 REST，无签名算法，无需 SDK —— 用标准库
  urllib 即可满足"零新增第三方依赖"约束（百度/有道需 key+secret 双因子与
  MD5 签名，实现与用户配置都更重）；
- 免费端点 api-free.deepl.com 与付费端点分离，用户按密钥类型自配端点。

密钥只从 Config.get_translate_secret("deepl") 读取（本机 QSettings）；
仓库不内置任何密钥，异常与日志绝不包含密钥内容（见 translate/base.py 隐私约束）。
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from .base import TranslationError, TranslationResult
from .registry import register_provider

PROVIDER_NAME = "deepl"
DEFAULT_ENDPOINT = "https://api-free.deepl.com/v2/translate"
DEFAULT_TIMEOUT = 10.0

_SECRET_GUIDANCE = (
    "尚未配置 DeepL API 密钥。获取方式：登录 https://www.deepl.com/account/plan "
    "复制 API Key，在设置面板（M2/T-15）填入；或临时用命令行配置："
    "python -c 'from snippin.config import Config; "
    "Config().set_translate_secret(\"deepl\", \"<你的密钥>\")'"
)

# DeepL 支持的目标语言（zh 映射到官方 DeepLang-8.1+ 的 ZH）
_TARGET_LANGS = {
    "zh": "ZH", "en": "EN-US", "de": "DE", "fr": "FR", "es": "ES", "it": "IT",
    "pt": "PT-BR", "nl": "NL", "pl": "PL", "ru": "RU", "ja": "JA", "ko": "KO",
    "ar": "AR", "bg": "BG", "cs": "CS", "da": "DA", "el": "EL", "et": "ET",
    "fi": "FI", "he": "HE", "hu": "HU", "id": "ID", "lv": "LV", "lt": "LT",
    "no": "NB", "ro": "RO", "sk": "SK", "sl": "SL", "sv": "SV", "tr": "TR",
    "uk": "UK", "vi": "VI",
}
SUPPORTED_TARGETS = tuple(sorted(_TARGET_LANGS))

# 面向用户的 HTTP 错误说明（绝不回显请求内容；密钥仅在 Authorization 头，从不进入消息/日志）
_STATUS_HINTS = {
    400: "DeepL 请求无效：请检查文本与语言参数",
    403: "DeepL 密钥无效或未授权（免费密钥请使用 api-free 端点）",
    404: "DeepL 端点不存在，请检查自定义端点配置",
    413: "文本过长，请缩短选区识别结果后重试",
    424: "DeepL 依赖服务故障，请稍后重试",
    429: "DeepL 配额受限（免费档 50 万字符/月），请稍后重试",
    456: "DeepL 用量上限已达（免费档 50 万字符/月），请升级或稍后重试",
}


class DeepLProvider:
    """DeepL 翻译服务商，实现 translate/base.py 冻结契约。"""

    name = PROVIDER_NAME
    requires_secret = True
    supported_targets = SUPPORTED_TARGETS

    def __init__(self, endpoint: str = DEFAULT_ENDPOINT,
                 timeout: float = DEFAULT_TIMEOUT) -> None:
        self._endpoint = endpoint
        self._timeout = timeout

    # ---------- 契约 ----------

    def available(self) -> bool:
        return bool(self._secret())

    def unavailable_reason(self) -> str:
        return "" if self.available() else _SECRET_GUIDANCE

    def translate(self, text: str, target_lang: str = "zh",
                  source_lang: str = "auto") -> TranslationResult:
        if not text or not text.strip():
            raise TranslationError("待翻译文本为空")
        if not self.available():
            raise TranslationError(self.unavailable_reason())
        if target_lang not in _TARGET_LANGS:
            raise TranslationError(
                f"DeepL 暂不支持目标语言：{target_lang}（支持 {', '.join(SUPPORTED_TARGETS)}）")
        data = urllib.parse.urlencode({
            "text": text,
            "target_lang": _TARGET_LANGS[target_lang],
            "source_lang": "AUTO" if source_lang in ("", "auto") else source_lang.upper(),
        }).encode("utf-8")
        request = urllib.request.Request(
            self._endpoint, data=data, method="POST",
            headers={
                "Authorization": f"DeepL-Auth-Key {self._secret()}",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "snippin/0.1",
            })
        payload = self._post(request)
        target_text = self._extract(payload)
        if not target_text:
            raise TranslationError("DeepL 返回了空译文，请重试")
        return TranslationResult(
            source_text=text,
            target_text=target_text,
            provider=self.name,
            source_lang=str(payload.get("source_lang", source_lang)).lower(),
            target_lang=target_lang,
        )

    # ---------- 内部实现 ----------

    @staticmethod
    def _secret() -> str:
        from snippin.config import Config
        return Config().get_translate_secret(PROVIDER_NAME).strip()

    def _post(self, request: urllib.request.Request) -> dict:
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            raise TranslationError(_STATUS_HINTS.get(
                exc.code, f"DeepL 请求失败（HTTP {exc.code}），请稍后重试")) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            reason = getattr(exc, "reason", None) or exc
            raise TranslationError(
                f"无法连接 DeepL（{type(reason).__name__}），请检查网络后重试") from exc
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            raise TranslationError("DeepL 响应解析失败，请稍后重试或反馈日志") from exc
        if not isinstance(payload, dict):
            raise TranslationError("DeepL 响应格式异常，请稍后重试")
        return payload

    @staticmethod
    def _extract(payload: dict) -> str:
        try:
            return str(payload["translations"][0]["text"])
        except (KeyError, IndexError, TypeError) as exc:
            raise TranslationError("DeepL 响应缺少译文字段，请稍后重试或反馈日志") from exc


register_provider(PROVIDER_NAME, DeepLProvider)
