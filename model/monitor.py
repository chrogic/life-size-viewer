"""
モニター情報の自動検出モジュール
PySide6の QScreen API を使用して接続モニターの情報を取得する。
"""
import math
from dataclasses import dataclass
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSizeF


@dataclass
class MonitorInfo:
    """モニター1台分の情報を保持するデータクラス"""
    name: str
    width_px: int
    height_px: int
    width_mm: float
    height_mm: float
    ppi: float
    is_primary: bool

    @property
    def display_label(self) -> str:
        """UI表示用のラベル文字列を生成する"""
        primary_tag = " ★" if self.is_primary else ""
        return f"{self.name} ({self.width_px}x{self.height_px}) — {self.ppi:.2f} PPI{primary_tag}"


def _calc_ppi(width_px: int, height_px: int, phys_size: QSizeF) -> float:
    """
    ピクセル解像度と物理サイズからPPIを計算する。
    物理サイズが取得できない場合は 96.0 (Windowsデフォルト) を返す。
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
    接続されている全モニターの情報を取得する。
    QApplication が存在しない場合は空リストを返す。
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

    # プライマリモニターを先頭にソート
    monitors.sort(key=lambda m: (not m.is_primary, m.name))
    return monitors


def get_primary_monitor() -> MonitorInfo | None:
    """プライマリモニターの情報を返す。取得できなければ None。"""
    monitors = get_monitors()
    for m in monitors:
        if m.is_primary:
            return m
    return monitors[0] if monitors else None


def get_monitor_for_widget(widget) -> MonitorInfo | None:
    """
    指定ウィジェットが表示されているモニターの情報を返す。
    ウィンドウがモニター間を移動した際の検知に使用。
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


# --- 最低解像度チェック ---
# サイドバー固定幅 240px + ビューポート最低 560px = 800px
# コントロール群の高さ + タイトル/ステータスバー = 600px
MIN_WIDTH = 800
MIN_HEIGHT = 600


def check_minimum_resolution(width_px: int, height_px: int) -> tuple[bool, str]:
    """
    指定された解像度が最低要件を満たすかチェックする。
    Returns: (OK: bool, 警告メッセージ: str)
    """
    if width_px >= MIN_WIDTH and height_px >= MIN_HEIGHT:
        return True, ""
    return False, (
        f"解像度 {width_px}x{height_px} は推奨最低解像度 "
        f"{MIN_WIDTH}x{MIN_HEIGHT} を下回っています。"
    )


def check_all_monitors() -> list[str]:
    """
    全モニターを検査し、最低解像度を満たすモニターが1台もない場合に
    警告メッセージのリストを返す。1台でも条件を満たせば空リストを返す。
    """
    monitors = get_monitors()
    if not monitors:
        return ["モニター情報を取得できませんでした。"]

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
        f"接続されている全てのモニターが推奨最低解像度 "
        f"({MIN_WIDTH}x{MIN_HEIGHT}) を満たしていません。\n"
        f"UIの一部が正しく表示されない可能性があります。\n"
    )
    return [header + "\n".join(warnings)]
