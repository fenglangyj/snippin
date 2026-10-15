"""OCR 引擎注册表：按名称选择引擎，缺省取第一个可用引擎。

引擎工厂懒加载：只有被选中时才实例化，避免拖慢应用启动。
"""

from __future__ import annotations

from collections.abc import Callable

from .base import OcrEngine, OcrError

_FACTORIES: dict[str, Callable[[], OcrEngine]] = {}
_INSTANCES: dict[str, OcrEngine] = {}


def register_engine(name: str, factory: Callable[[], OcrEngine]) -> None:
    """注册引擎工厂（同名重复注册以最后一次为准）。"""
    _FACTORIES[name] = factory


def registered() -> list[str]:
    """已注册的引擎名称。"""
    return sorted(_FACTORIES)


def _instance(name: str) -> OcrEngine:
    engine = _INSTANCES.get(name)
    if engine is None:
        engine = _FACTORIES[name]()
        _INSTANCES[name] = engine
    return engine


def get_engine(name: str | None = None) -> OcrEngine:
    """按名称获取引擎；name 为空时返回第一个可用引擎。全部不可用时抛 OcrError。"""
    if name:
        factory = _FACTORIES.get(name)
        if factory is None:
            raise OcrError(f"未注册的 OCR 引擎：{name}")
        engine = _instance(name)
        if not engine.available():
            raise OcrError(engine.unavailable_reason() or f"OCR 引擎不可用：{name}")
        return engine

    reasons: list[str] = []
    for key in registered():
        engine = _instance(key)
        if engine.available():
            return engine
        reasons.append(f"{key}：{engine.unavailable_reason() or '不可用'}")
    detail = "；".join(reasons)
    raise OcrError("没有可用的 OCR 引擎。" + (detail if detail else "请先安装系统 OCR 语言包。"))


def _register_builtin() -> None:
    """注册内置引擎（T-21：Windows 系统 OCR）。模块缺失时静默跳过。"""
    try:
        from .windows import WindowsOcrEngine
    except Exception:  # noqa: BLE001 —— 引擎模块缺失或导入失败时静默跳过，不阻塞应用启动
        return
    register_engine(WindowsOcrEngine.name, WindowsOcrEngine)


_register_builtin()
