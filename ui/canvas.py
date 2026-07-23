from PySide6.QtWidgets import QLabel, QSizePolicy
from PySide6.QtGui import QMouseEvent
from PySide6.QtCore import Qt, Signal

class ViewerCanvas(QLabel):
    """クリックイベントを取得するためのQLabel拡張"""
    clicked_pos = Signal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.setScaledContents(True)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked_pos.emit(event.pos().x(), event.pos().y())