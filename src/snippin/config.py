from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSettings


class Config:
    """运行时配置，基于 QSettings 持久化（Windows 注册表 / Linux ini）。"""

    DEFAULT_HOTKEY = "ctrl+alt+a"
    DEFAULT_OCR_ENGINE = "windows"      # Windows 系统 OCR API（离线）
    DEFAULT_TRANSLATE_PROVIDER = ""     # 空 = 未配置，翻译功能提示用户先配置

    def __init__(self) -> None:
        self._settings = QSettings("snippin", "snippin")
        self.hotkey: str = str(self._settings.value("hotkey", self.DEFAULT_HOTKEY))
        default_dir = Path.home() / "Pictures" / "snippin"
        self.save_dir = Path(str(self._settings.value("save_dir", str(default_dir))))
        self.save_format: str = str(self._settings.value("save_format", "png"))
        self.annotation_color: str = "#FF4D4F"
        self.line_width: int = 3
        self.font_size: int = 18
        # 文字提取（OCR）
        self.ocr_engine: str = str(self._settings.value("ocr/engine", self.DEFAULT_OCR_ENGINE))
        # 翻译：仅保存 provider 名与目标语言；密钥单独存取，绝不写入代码或仓库
        self.translate_provider: str = str(
            self._settings.value("translate/provider", self.DEFAULT_TRANSLATE_PROVIDER))
        self.translate_target_lang: str = str(self._settings.value("translate/target_lang", "zh"))

    # ---------- 翻译服务密钥（仅存本机） ----------

    def get_translate_secret(self, provider: str) -> str:
        return str(self._settings.value(f"translate/secret/{provider}", ""))

    def set_translate_secret(self, provider: str, value: str) -> None:
        self._settings.setValue(f"translate/secret/{provider}", value)
        self._settings.sync()

    def clear_translate_secret(self, provider: str) -> None:
        self._settings.remove(f"translate/secret/{provider}")
        self._settings.sync()

    def next_save_path(self) -> Path:
        """按时间戳生成下一个保存路径。"""
        self.save_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return self.save_dir / f"snippin_{stamp}.{self.save_format}"
