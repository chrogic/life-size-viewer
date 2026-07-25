"""
Automatic monitor-information detection module.
Uses the PySide6 QScreen API to retrieve information about connected monitors.
"""
import math
from dataclasses import dataclass
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSizeF


@dataclass
class MonitorInfo:
    """Data class that holds information for one monitor."""
    name: str
    width_px: int
    height_px: int
    width_mm: float
    height_mm: float
    ppi: float
    is_primary: bool

    @property
    def display_label(self) -> str:
        """Create a label string for display in the UI."""
        primary_tag = " ★" if self.is_primary else ""
        return f"{self.name} ({self.width_px}x{self.height_px}) — {self.ppi:.2f} PPI{primary_tag}"


def _calc_ppi(width_px: int, height_px: int, phys_size: QSizeF) -> float:
    """
    Calculate PPI from pixel resolution and physical size.
    Return 96.0 (the Windows default) if the physical size is unavailable.
    """
    w_mm = phys_size.width()
    h_mm = phys_size.height()

    if w_mm <= 0 or h_mm <= 0:
        return 96.0

    diag_px = math.sqrt(width_px ** 2 + height_px ** 2)
    diag_mm = math.sqrt(w_mm ** 2 + h_mm ** 2)
    diag_inch = diag_mm / 25.4

    if diag_inch <= 0:
        return 96.0

    return diag_px / diag_inch


def get_monitors() -> list[MonitorInfo]:
    """
    Retrieve information for all connected monitors.
    Return an empty list when no QApplication exists.
    """
    app = QApplication.instance()
    if app is None:
        return []

    primary_screen = app.primaryScreen()
    monitors = []

    for screen in app.screens():
        geo = screen.geometry()
        phys = screen.physicalSize()
        w_px = geo.width()
        h_px = geo.height()

        ppi = _calc_ppi(w_px, h_px, phys)

        info = MonitorInfo(
            name=screen.name(),
            width_px=w_px,
            height_px=h_px,
            width_mm=phys.width(),
            height_mm=phys.height(),
            ppi=ppi,
            is_primary=(screen == primary_screen),
        )
        monitors.append(info)

    # Sort with the primary monitor first.
    monitors.sort(key=lambda m: (not m.is_primary, m.name))
    return monitors


def get_primary_monitor() -> MonitorInfo | None:
    """Return information for the primary monitor, or None if unavailable."""
    monitors = get_monitors()
    for m in monitors:
        if m.is_primary:
            return m
    return monitors[0] if monitors else None


def get_monitor_for_widget(widget) -> MonitorInfo | None:
    """
    Return information for the monitor displaying the specified widget.
    Used to detect when a window moves between monitors.
    """
    screen = widget.screen()
    if screen is None:
        return get_primary_monitor()

    app = QApplication.instance()
    if app is None:
        return None

    primary_screen = app.primaryScreen()
    geo = screen.geometry()
    phys = screen.physicalSize()
    w_px = geo.width()
    h_px = geo.height()

    return MonitorInfo(
        name=screen.name(),
        width_px=w_px,
        height_px=h_px,
        width_mm=phys.width(),
        height_mm=phys.height(),
        ppi=_calc_ppi(w_px, h_px, phys),
        is_primary=(screen == primary_screen),
    )


# --- Minimum-resolution checks ---
# Fixed sidebar width of 240px + minimum viewport width of 560px = 800px
# Control height + title/status bars = 600px
MIN_WIDTH = 800
MIN_HEIGHT = 600


def check_minimum_resolution(width_px: int, height_px: int) -> tuple[bool, str]:
    """
    Check whether a resolution meets the minimum requirement.
    Returns: (OK: bool, warning_message: str)
    """
    if width_px >= MIN_WIDTH and height_px >= MIN_HEIGHT:
        return True, ""
    return False, (
        f"Resolution {width_px}x{height_px} is below the recommended minimum "
        f"of {MIN_WIDTH}x{MIN_HEIGHT}."
    )


def check_all_monitors() -> list[str]:
    """
    Inspect all monitors and return warning messages when none meets the
    minimum resolution. Return an empty list if at least one monitor qualifies.
    """
    monitors = get_monitors()
    if not monitors:
        return ["Unable to retrieve monitor information."]

    warnings = []
    has_suitable = False
    for mon in monitors:
        ok, msg = check_minimum_resolution(mon.width_px, mon.height_px)
        if ok:
            has_suitable = True
        else:
            warnings.append(f"  • {mon.name}: {msg}")

    if has_suitable:
        return []

    header = (
        f"All connected monitors are below the recommended minimum resolution "
        f"of {MIN_WIDTH}x{MIN_HEIGHT}.\n"
        f"Some parts of the UI may not display correctly.\n"
    )
    return [header + "\n".join(warnings)]
