"""翻译 provider 注册表：按名称选择服务商，缺省取第一个可用服务商。

provider 工厂懒加载：只有被选中时才实例化。
"""

from __future__ import annotations

from collections.abc import Callable

from .base import TranslationError, TranslationProvider

_FACTORIES: dict[str, Callable[[], TranslationProvider]] = {}
_INSTANCES: dict[str, TranslationProvider] = {}


def register_provider(name: str, factory: Callable[[], TranslationProvider]) -> None:
    """注册 provider 工厂（同名重复注册以最后一次为准）。"""
    _FACTORIES[name] = factory


def registered() -> list[str]:
    """已注册的 provider 名称。"""
    return sorted(_FACTORIES)


def _instance(name: str) -> TranslationProvider:
    provider = _INSTANCES.get(name)
    if provider is None:
        provider = _FACTORIES[name]()
        _INSTANCES[name] = provider
    return provider


def get_provider(name: str | None = None) -> TranslationProvider:
    """按名称获取 provider；name 为空时返回第一个已配置完成的服务商。

    全部未配置时抛 TranslationError，附带各 provider 的不可用原因。
    """
    if name:
        factory = _FACTORIES.get(name)
        if factory is None:
            raise TranslationError(f"未注册的翻译服务：{name}")
        provider = _instance(name)
        if not provider.available():
            raise TranslationError(provider.unavailable_reason() or f"翻译服务不可用：{name}")
        return provider

    reasons: list[str] = []
    for key in registered():
        provider = _instance(key)
        if provider.available():
            return provider
        reasons.append(f"{key}：{provider.unavailable_reason() or '不可用'}")
    detail = "；".join(reasons)
    raise TranslationError("没有已配置的翻译服务。" + (detail if detail else "请先在设置中填写翻译服务密钥。"))


def _register_builtin() -> None:
    """注册内置 provider（T-23 实现具体服务商与密钥配置入口）。"""
    try:
        from . import providers  # noqa: F401
    except Exception:  # noqa: BLE001 —— provider 模块缺失或导入失败时静默跳过
        return


_register_builtin()
