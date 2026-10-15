from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSettings


class Config:
    """运行时配置，基于 QSettings 持久化（Windows 注册表 / Linux ini）。"""

    DEFAULT_HOTKEY = "ctrl+alt+a"

    def __init__(self) -> None:
        self._settings = QSettings("quicksnip", "quicksnip")
        self.hotkey: str = str(self._settings.value("hotkey", self.DEFAULT_HOTKEY))
        default_dir = Path.home() / "Pictures" / "quicksnip"
        self.save_dir = Path(str(self._settings.value("save_dir", str(default_dir))))
        self.save_format: str = str(self._settings.value("save_format", "png"))
        self.annotation_color: str = "#FF4D4F"
        self.line_width: int = 3
        self.font_size: int = 18

    def next_save_path(self) -> Path:
        """按时间戳生成下一个保存路径。"""
        self.save_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return self.save_dir / f"quicksnip_{stamp}.{self.save_format}"
