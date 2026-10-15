"""翻译契约 —— 冻结接口，实现 provider 时不得修改本文件签名。

隐私约束（见 README「隐私说明」与 docs/ARCHITECTURE.md）：
- 只有用户主动点击「翻译」时才发起网络请求，且只发送识别出的文本；
- 仓库内不内置任何密钥；密钥由用户在本机配置（Config.get_translate_secret）；
- 异常信息与日志不得包含密钥内容。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class TranslationResult:
    source_text: str
    target_text: str
    provider: str
    source_lang: str = "auto"
    target_lang: str = "zh"


class TranslationError(RuntimeError):
    """翻译不可用或调用失败。异常信息面向用户，不得包含密钥。"""


@runtime_checkable
class TranslationProvider(Protocol):
    """翻译服务商契约。"""

    name: str
    requires_secret: bool
    supported_targets: tuple[str, ...]

    def available(self) -> bool:
        """是否已具备调用条件（通常是已配置密钥）。"""

    def unavailable_reason(self) -> str:
        """不可用原因（面向用户，例如「尚未配置 API 密钥」）；可用时返回空串。"""

    def translate(self, text: str, target_lang: str = "zh",
                  source_lang: str = "auto") -> TranslationResult:
        """翻译文本；未配置或请求失败时抛 TranslationError。"""
