"""
Settings persistence module.
Uses PySide6 QSettings to save and restore application settings.
"""
from PySide6.QtCore import QSettings

# Application identifiers
APP_ORG = "LifeSizeViewer"
APP_NAME = "UniversalLifeSizeViewer"


class AppSettings:
    """Manages saving and loading application settings."""

    # Default values for settings keys
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
        # Create and load config.ini in the project root.
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.ini")
        self._settings = QSettings(config_path, QSettings.Format.IniFormat)

    @property
    def file_path(self) -> str:
        """Return the path where the settings file is stored."""
        return self._settings.fileName()

    # --- Loading ---
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
        # QSettings may store the value as a string.
        if isinstance(val, str):
            return val.lower() == "true"
        return bool(val)

    def sensitivity(self) -> float:
        return float(self._settings.value("tracking/sensitivity", self.DEFAULTS["tracking/sensitivity"]))

    def window_geometry(self) -> bytes | None:
        return self._settings.value("window/geometry", None)

    # --- Saving ---
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

    # --- Bulk-save helper ---
    def save_all(self, *, ppi: float, monitor_name: str, target_pd_text: str, target_pd_value: float,
                 show_grid: bool, sensitivity: float, geometry: bytes):
        """Save all settings at once."""
        self.save_ppi(ppi)
        self.save_monitor_name(monitor_name)
        self.save_target_pd_text(target_pd_text)
        self.save_target_pd_value(target_pd_value)
        self.save_show_grid(show_grid)
        self.save_sensitivity(sensitivity)
        self.save_window_geometry(geometry)
        self._settings.sync()
