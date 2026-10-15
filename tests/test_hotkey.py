import os
import time

import pytest

from snippin.hotkey import HotkeyListener, parse_hotkey

CTRL, ALT, SHIFT, F24_VK, A_VK = 0x11, 0x12, 0x10, 0x87, 0x41


def test_parse_ctrl_alt_a():
    mods, vk = parse_hotkey("ctrl+alt+a")
    assert mods == frozenset({CTRL, ALT})
    assert vk == A_VK


def test_parse_case_and_space_insensitive():
    mods, vk = parse_hotkey("Ctrl + Shift + F12")
    assert mods == frozenset({CTRL, SHIFT})
    assert vk == 0x7B


def test_parse_single_key():
    mods, vk = parse_hotkey("f12")
    assert mods == frozenset()
    assert vk == 0x7B


@pytest.mark.parametrize("spec", ["", "ctrl+", "ctrl+shift", "hyper+a", "ctrl+nosuchkey"])
def test_parse_invalid_raises(spec):
    with pytest.raises(ValueError):
        parse_hotkey(spec)


def test_matches_requires_all_modifiers():
    lis = HotkeyListener("ctrl+alt+a")
    lis._mods, lis._vk = frozenset({CTRL, ALT}), A_VK
    assert lis._matches(A_VK, {CTRL, ALT})
    assert not lis._matches(A_VK, {CTRL})
    assert not lis._matches(A_VK + 1, {CTRL, ALT})


def test_left_right_modifier_vk_events_still_match():
    """钩子按左/右独立 vk（0xA2/0xA4）上报，主键匹配不应受影响。"""
    lis = HotkeyListener("ctrl+alt+a")
    lis._mods, lis._vk = frozenset({CTRL, ALT}), A_VK
    # 模拟 _modifiers_down 已由 GetAsyncKeyState 归一化后的集合
    assert lis._matches(A_VK, lis._mods)


def test_invalid_hotkey_sets_error_without_crash():
    lis = HotkeyListener("ctrl+shift")
    lis.start()
    assert lis.error and "热键" in lis.error
    assert lis._thread is None
    lis.start()  # 幂等：不重复报错、不启动线程
    assert lis._thread is None


# ---------- 真机集成：SendInput 注入触发全局钩子（US-1，<500ms） ----------

def _sendinput_vk(vk: int, up: bool = False) -> None:
    import ctypes
    from ctypes import windll, wintypes

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                    ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long),
                    ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD),
                    ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

    class HWI(ctypes.Structure):
        _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD),
                    ("wParamH", wintypes.WORD)]

    class U(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HWI)]

    class INPUT(ctypes.Structure):
        _anonymous_ = ("u",)
        _fields_ = [("type", wintypes.DWORD), ("u", U)]

    i = INPUT(type=1, u=U(ki=KEYBDINPUT(vk, 0, 2 if up else 0, 0, None)))
    assert windll.user32.SendInput(1, ctypes.byref(i), ctypes.sizeof(INPUT)) == 1


@pytest.mark.skipif(not (os.name == "nt" and os.environ.get("SNIPPIN_SMOKE")),
                    reason="真机注入冒烟需 SNIPPIN_SMOKE=1（交互 Windows 会话）")
def test_real_hotkey_trigger_latency(qapp):
    from PySide6.QtCore import QElapsedTimer, QEventLoop, QTimer

    lis = HotkeyListener("ctrl+alt+f24")
    hits: list[int] = []
    lis.triggered.connect(lambda: hits.append(1))
    lis.start()
    assert lis.error == "", lis.error
    time.sleep(0.3)  # 等钩子安装

    loop = QEventLoop()
    timer = QElapsedTimer()
    lis.triggered.connect(loop.quit)
    timer.start()
    _sendinput_vk(CTRL)
    _sendinput_vk(ALT)
    _sendinput_vk(F24_VK)
    _sendinput_vk(F24_VK, up=True)
    _sendinput_vk(ALT, up=True)
    _sendinput_vk(CTRL, up=True)
    QTimer.singleShot(3000, loop.quit)
    loop.exec()
    latency = timer.elapsed()
    lis.stop()
    assert hits, "注入 ctrl+alt+f24 后未触发热键信号"
    assert latency < 500, f"热键唤起延迟 {latency}ms 超过 500ms 验收线"
