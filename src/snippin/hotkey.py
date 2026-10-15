"""Windows 全局热键监听（ctypes WH_KEYBOARD_LL，零第三方依赖）。

背景（缺陷 D-03，docs/RISKS.md R-08）：keyboard 0.13.5 的 add_hotkey 在
Python 3.12 实测从不触发（原始事件流 on_press 正常，热键匹配层失效），
故基线依赖不可用，改为标准库低级键盘钩子实现。

回调发生在钩子所在线程，通过 Qt 信号（queued connection）切换到主线程。
注册失败不再静默吞掉：写入 error 属性供上层感知（缺陷 D-04），
托盘菜单触发截图始终保留为降级路径。
"""

from __future__ import annotations

import ctypes
import sys
import threading
from ctypes import wintypes

from PySide6.QtCore import QObject, Signal

WH_KEYBOARD_LL = 13
WM_KEYDOWN, WM_KEYUP = 0x0100, 0x0101
WM_SYSKEYDOWN, WM_SYSKEYUP = 0x0104, 0x0105
WM_QUIT = 0x0012

_MODIFIERS: dict[str, int] = {
    "ctrl": 0x11, "control": 0x11,
    "alt": 0x12, "menu": 0x12,
    "shift": 0x10,
    "win": 0x5B, "super": 0x5B, "meta": 0x5B,
}

_NAMED_KEYS: dict[str, int] = {
    "space": 0x20, "enter": 0x0D, "return": 0x0D, "tab": 0x09,
    "esc": 0x1B, "escape": 0x1B, "backspace": 0x08, "delete": 0x2E,
    "insert": 0x2D, "home": 0x24, "end": 0x23,
    "pageup": 0x21, "prior": 0x21, "pagedown": 0x22, "next": 0x22,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "printscreen": 0x2C, "capslock": 0x14,
}
for _i in range(1, 25):
    _NAMED_KEYS[f"f{_i}"] = 0x70 + _i - 1 if _i <= 12 else 0x7C + _i - 13


def _resolve_key(token: str) -> int:
    t = token.strip().lower()
    if not t:
        raise ValueError("空按键名")
    if len(t) == 1:
        vk = ctypes.windll.user32.VkKeyScanW(ord(t.upper()))
        if vk == -1:
            raise ValueError(f"无法解析按键：{token}")
        return vk & 0xFF
    if t in _NAMED_KEYS:
        return _NAMED_KEYS[t]
    raise ValueError(f"无法解析按键：{token}")


def parse_hotkey(spec: str) -> tuple[frozenset[int], int]:
    """解析 "ctrl+alt+a" 为 (修饰键 VK 集合, 主键 VK)。非法定义抛 ValueError。"""
    parts = [p for p in spec.lower().replace(" ", "").split("+") if p]
    if not parts:
        raise ValueError(f"热键定义为空：{spec!r}")
    mods: set[int] = set()
    for p in parts[:-1]:
        if p not in _MODIFIERS:
            raise ValueError(f"修饰键不受支持：{p}")
        mods.add(_MODIFIERS[p])
    primary_token = parts[-1]
    if primary_token in _MODIFIERS:
        raise ValueError(f"主键不能是修饰键：{primary_token}")
    return frozenset(mods), _resolve_key(primary_token)


class _KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]

_HOOKPROC = ctypes.CFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM,
                             ctypes.POINTER(_KBDLLHOOKSTRUCT))


class HotkeyListener(QObject):
    """低级键盘钩子全局热键。接口与基线一致：triggered 信号 + start()。"""

    triggered = Signal()

    def __init__(self, hotkey: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.hotkey = hotkey
        self.error = ""
        self._mods: frozenset[int] = frozenset()
        self._vk = 0
        self._down: set[int] = set()
        self._thread: threading.Thread | None = None
        self._tid = 0
        self._ctypes_cb: object | None = None  # 防止回调被 GC

    # ---------- 纯匹配逻辑（可单测，无需真机钩子） ----------

    def _matches(self, vk_down: int, mods_down: set[int]) -> bool:
        return vk_down == self._vk and self._mods <= mods_down

    def _modifiers_down(self) -> set[int]:
        """钩子事件里的修饰键 vk 分左右（0xA2/0xA4...），改用 GetAsyncKeyState 查通用 vk。"""
        get_async = ctypes.windll.user32.GetAsyncKeyState
        return {m for m in self._mods if get_async(m) & 0x8000}

    # ---------- 生命周期 ----------

    def start(self) -> None:
        if self._thread is not None or self.error:
            return
        if not sys.platform.startswith("win"):
            self.error = "当前平台不支持全局热键，请使用托盘菜单触发截图"
            return
        try:
            self._mods, self._vk = parse_hotkey(self.hotkey)
        except (ValueError, OSError) as exc:
            self.error = f"热键定义无效：{exc}"
            return
        self._thread = threading.Thread(target=self._run, daemon=True, name="hotkey-listener")
        self._thread.start()

    def stop(self) -> None:
        if self._thread is None:
            return
        if self._tid:
            ctypes.windll.user32.PostThreadMessageW(self._tid, WM_QUIT, 0, 0)
        self._thread.join(timeout=2)
        self._thread = None
        self._tid = 0

    def _run(self) -> None:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self._tid = kernel32.GetCurrentThreadId()
        user32.SetWindowsHookExW.restype = wintypes.HHOOK
        user32.CallNextHookEx.restype = ctypes.c_ssize_t
        user32.GetAsyncKeyState.restype = ctypes.c_short
        self._ctypes_cb = _HOOKPROC(self._hook_callback)
        hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._ctypes_cb, None, 0)
        if not hook:
            self.error = (f"全局热键注册失败（Win32 错误 {kernel32.GetLastError()}），"
                          f"请检查热键冲突或使用托盘菜单")
            return
        msg = wintypes.MSG()
        while True:
            got = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if got in (0, -1) or msg.message == WM_QUIT:
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        user32.UnhookWindowsHookEx(hook)

    def _hook_callback(self, code: int, wparam, lparam) -> int:
        if code >= 0:
            try:
                vk = int(lparam.contents.vkCode)
                if wparam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                    newly = vk not in self._down
                    self._down.add(vk)
                    if newly and self._matches(vk, self._modifiers_down()):
                        self.triggered.emit()
                elif wparam in (WM_KEYUP, WM_SYSKEYUP):
                    self._down.discard(vk)
            except Exception:  # noqa: BLE001, S110  # 钩子回调绝不抛异常，否则整条钩子链被切断
                pass
        return ctypes.windll.user32.CallNextHookEx(None, code, wparam, lparam)
