"""
設定の永続化モジュール
PySide6の QSettings を使用してアプリ設定を保存・復元する。
"""
from PySide6.QtCore import QSettings

# アプリ識別子
APP_ORG = "LifeSizeViewer"
APP_NAME = "UniversalLifeSizeViewer"


class AppSettings:
    """アプリケーション設定の保存・読込を管理するクラス"""

    # 設定キーのデフォルト値
    DEFAULTS = {
        "monitor/ppi": 96.0,
        "monitor/selected_name": "",
        "target_pd/text": "Adult Male (64)",
        "target_pd/value": 64.0,
        "view/show_grid": True,
        "tracking/sensitivity": 0.02,
        "window/geometry": None,
    }

    def __init__(self):
        import os
        # プロジェクトルートに config.ini を作成・読込する
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.ini")
        self._settings = QSettings(config_path, QSettings.Format.IniFormat)

    @property
    def file_path(self) -> str:
        """設定ファイルの保存先パスを返す"""
        return self._settings.fileName()

    # --- 読込 ---
    def ppi(self) -> float:
        return float(self._settings.value("monitor/ppi", self.DEFAULTS["monitor/ppi"]))

    def monitor_name(self) -> str:
        return str(self._settings.value("monitor/selected_name", self.DEFAULTS["monitor/selected_name"]))

    def target_pd_text(self) -> str:
        return str(self._settings.value("target_pd/text", self.DEFAULTS["target_pd/text"]))

    def target_pd_value(self) -> float:
        return float(self._settings.value("target_pd/value", self.DEFAULTS["target_pd/value"]))

    def show_grid(self) -> bool:
        val = self._settings.value("view/show_grid", self.DEFAULTS["view/show_grid"])
        # QSettings は文字列で保存する場合がある
        if isinstance(val, str):
            return val.lower() == "true"
        return bool(val)

    def sensitivity(self) -> float:
        return float(self._settings.value("tracking/sensitivity", self.DEFAULTS["tracking/sensitivity"]))

    def window_geometry(self) -> bytes | None:
        return self._settings.value("window/geometry", None)

    # --- 保存 ---
    def save_ppi(self, value: float):
        self._settings.setValue("monitor/ppi", value)

    def save_monitor_name(self, name: str):
        self._settings.setValue("monitor/selected_name", name)

    def save_target_pd_text(self, text: str):
        self._settings.setValue("target_pd/text", text)

    def save_target_pd_value(self, value: float):
        self._settings.setValue("target_pd/value", value)

    def save_show_grid(self, checked: bool):
        self._settings.setValue("view/show_grid", checked)

    def save_sensitivity(self, value: float):
        self._settings.setValue("tracking/sensitivity", value)

    def save_window_geometry(self, geometry: bytes):
        self._settings.setValue("window/geometry", geometry)

    # --- 一括保存ヘルパー ---
    def save_all(self, *, ppi: float, monitor_name: str, target_pd_text: str, target_pd_value: float,
                 show_grid: bool, sensitivity: float, geometry: bytes):
        """全設定を一括保存する"""
        self.save_ppi(ppi)
        self.save_monitor_name(monitor_name)
        self.save_target_pd_text(target_pd_text)
        self.save_target_pd_value(target_pd_value)
        self.save_show_grid(show_grid)
        self.save_sensitivity(sensitivity)
        self.save_window_geometry(geometry)
        self._settings.sync()
