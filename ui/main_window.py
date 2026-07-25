import cv2
import numpy as np
import re
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QLabel, QPushButton, QFileDialog, 
                               QScrollArea, QDoubleSpinBox, QComboBox, QGroupBox, 
                               QMessageBox, QCheckBox, QApplication)
from PySide6.QtGui import QPixmap, QImage, QPalette, QShortcut, QKeySequence
from PySide6.QtCore import Qt, Slot, QTimer

# Imports from the split modules.
from model.detector import FaceDetector
from model.worker import WebcamWorker
from model.monitor import get_monitors, get_monitor_for_widget, MonitorInfo, check_all_monitors
from model.settings import AppSettings
from ui.canvas import ViewerCanvas

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Universal Life-Size Viewer (Modular)")
        self.resize(1200, 900)

        # Logic Modules
        # Each module resolves its model path to an absolute path from the project root.
        self.detector = FaceDetector()
        self.webcam_worker = WebcamWorker()
        self.webcam_worker.ratio_signal.connect(self.on_tracking_update)

        # State Variables
        self.original_image = None
        self.pd_pixel_base = None
        self.face_center_ratio = (0.5, 0.5)
        self.angle_correction = 1.0
        
        self.manual_mode = False
        self.manual_points = []
        self.manual_view_scale = 1.0

        self.dynamic_ratio = 1.0
        self.current_scale = 1.0

        # Monitor detection
        self._current_monitor_name = None
        self._monitors: list[MonitorInfo] = []

        # Settings persistence
        self._settings = AppSettings()

        self.setup_ui()
        self._populate_monitors()
        self._load_settings()
        self._check_screen_resolution()

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        # --- Left Sidebar Controls ---
        controls = QVBoxLayout()
        controls.setSpacing(6)

        # 1. Monitor Setting
        grp_ppi = QGroupBox("Monitor PPI")
        l_ppi = QVBoxLayout()
        self.combo_monitor = QComboBox()
        self.combo_monitor.currentIndexChanged.connect(self._on_monitor_selected)
        l_ppi.addWidget(self.combo_monitor)
        h_ppi = QHBoxLayout()
        h_ppi.addWidget(QLabel("PPI:"))
        self.spin_ppi = QDoubleSpinBox()
        self.spin_ppi.setRange(50, 500); self.spin_ppi.setValue(96.0)
        self.spin_ppi.valueChanged.connect(self.refresh_view)
        h_ppi.addWidget(self.spin_ppi)
        l_ppi.addLayout(h_ppi)
        grp_ppi.setLayout(l_ppi)
        controls.addWidget(grp_ppi)

        # 2. Target PD
        grp_pd = QGroupBox("Target PD (mm)")
        l_pd = QVBoxLayout()
        self.combo_pd = QComboBox()
        self.combo_pd.addItems(["Adult Male (64)", "Adult Female (62)", "Child (55)", "Anime/Wide (68)", "Custom (Manual Input)"])
        self.combo_pd.setEditable(False)
        self.combo_pd.currentIndexChanged.connect(self._on_pd_preset_selected)
        l_pd.addWidget(self.combo_pd)

        h_pd_val = QHBoxLayout()
        h_pd_val.addWidget(QLabel("PD:"))
        self.spin_pd = QDoubleSpinBox()
        self.spin_pd.setRange(20, 150)
        self.spin_pd.setValue(64.0)
        self.spin_pd.setSingleStep(1.0)
        self.spin_pd.valueChanged.connect(self.refresh_view)
        h_pd_val.addWidget(self.spin_pd)
        l_pd.addLayout(h_pd_val)

        grp_pd.setLayout(l_pd)
        controls.addWidget(grp_pd)

        # 3. Tracking
        grp_track = QGroupBox("Distance Tracking")
        l_track = QVBoxLayout()
        self.chk_track = QCheckBox("Enable")
        self.chk_track.stateChanged.connect(self.toggle_tracking)
        l_track.addWidget(self.chk_track)
        self.btn_calib = QPushButton("Calibrate")
        self.btn_calib.clicked.connect(lambda: self.webcam_worker.calibrate())
        self.btn_calib.setEnabled(False)
        l_track.addWidget(self.btn_calib)

        # Sensitivity
        h_sens = QHBoxLayout()
        h_sens.addWidget(QLabel("Sens:"))
        self.spin_sens = QDoubleSpinBox()
        
        default_sens = AppSettings.DEFAULTS["tracking/sensitivity"]
        self.spin_sens.setDecimals(3)
        self.spin_sens.setRange(default_sens / 10.0, default_sens * 10.0)
        self.spin_sens.setValue(default_sens)
        self.spin_sens.setSingleStep(default_sens / 2.0)
        self.spin_sens.valueChanged.connect(self.refresh_view)
        h_sens.addWidget(self.spin_sens)
        l_track.addLayout(h_sens)

        grp_track.setLayout(l_track)
        controls.addWidget(grp_track)

        # 4. Actions
        grp_act = QGroupBox("Actions")
        l_act = QVBoxLayout()
        self.btn_load = QPushButton("Load Image")
        self.btn_load.clicked.connect(self.load_image)
        l_act.addWidget(self.btn_load)
        self.btn_save = QPushButton("Save View")
        self.btn_save.clicked.connect(self.save_image)
        self.btn_save.setEnabled(False)
        l_act.addWidget(self.btn_save)
        self.chk_grid = QCheckBox("Show Grid")
        self.chk_grid.setChecked(True)
        self.chk_grid.toggled.connect(self.refresh_view)
        l_act.addWidget(self.chk_grid)
        self.btn_fullscreen = QPushButton("Fullscreen (F11)")
        self.btn_fullscreen.clicked.connect(self.toggle_fullscreen)
        l_act.addWidget(self.btn_fullscreen)
        grp_act.setLayout(l_act)
        controls.addWidget(grp_act)

        # Add a bottom spacer to keep controls aligned to the top.
        controls.addStretch()

        # Wrap controls in a widget so their visibility can be toggled.
        self.controls_widget = QWidget()
        self.controls_widget.setLayout(controls)
        self.controls_widget.setFixedWidth(240)
        main_layout.addWidget(self.controls_widget)

        # --- Main Viewport ---
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(False)
        
        # ColorRole corrected for PySide6.
        self.scroll_area.setBackgroundRole(QPalette.ColorRole.Dark)
        
        self.canvas = ViewerCanvas()
        self.canvas.clicked_pos.connect(self.on_canvas_clicked)
        self.scroll_area.setWidget(self.canvas)
        main_layout.addWidget(self.scroll_area)

        # --- Status Bar ---
        self.status_label = QLabel("Ready. Load an image.")
        self.status_label.setStyleSheet("font-weight: bold; color: #333;")
        self.statusBar().addWidget(self.status_label)

        # F11 shortcut.
        shortcut_f11 = QShortcut(QKeySequence(Qt.Key.Key_F11), self)
        shortcut_f11.activated.connect(self.toggle_fullscreen)
        # Exit fullscreen with Escape.
        shortcut_esc = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        shortcut_esc.activated.connect(self.exit_fullscreen)

        # Floating button for exiting fullscreen.
        self.btn_exit_fs = QPushButton("✖ Exit Fullscreen", self)
        self.btn_exit_fs.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 0, 0, 160);
                color: white;
                font-weight: bold;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: rgba(80, 80, 80, 200);
            }
        """)
        self.btn_exit_fs.clicked.connect(self.exit_fullscreen)
        self.btn_exit_fs.hide()

    # --- Logic ---
    def load_image(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Open Image", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if not fname: return

        try:
            stream = open(fname, "rb")
            bytes_data = bytearray(stream.read())
            stream.close()
            numpyarray = np.asarray(bytes_data, dtype=np.uint8)
            img = cv2.imdecode(numpyarray, cv2.IMREAD_COLOR)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load image: {e}")
            return

        if img is None:
            QMessageBox.critical(self, "Error", "Failed to load image.")
            return

        self.original_image = img
        self.reset_state()
        
        self.status_label.setText("Analyzing face...")
        QApplication.processEvents()

        dist, correction, center = self.detector.analyze(img)

        if dist is not None:
            self.pd_pixel_base = dist
            self.angle_correction = correction
            h, w = img.shape[:2]
            self.face_center_ratio = (center[0] / w, center[1] / h)
            self.status_label.setText(f"Face Detected. PD: {dist:.1f}px (Corrected)")
            self.btn_save.setEnabled(True)
            self.refresh_view()
        else:
            self.status_label.setText("Face not detected. Manual Mode: Click LEFT EYE center.")
            self.start_manual_mode()

    def reset_state(self):
        self.pd_pixel_base = None
        self.manual_mode = False
        self.manual_points = []
        self.angle_correction = 1.0
        self.dynamic_ratio = 1.0
        self.btn_save.setEnabled(False)

    def start_manual_mode(self):
        self.manual_mode = True
        if self.original_image is None: return
        h, w = self.original_image.shape[:2]
        view_w = self.scroll_area.viewport().width()
        view_h = self.scroll_area.viewport().height()
        scale = min(view_w / w, view_h / h, 1.0)
        self.manual_view_scale = scale
        disp_w, disp_h = int(w * scale), int(h * scale)
        resized = cv2.resize(self.original_image, (disp_w, disp_h))
        self.display_cv_image(resized)

    def on_canvas_clicked(self, x, y):
        if not self.manual_mode: return
        real_x = x / self.manual_view_scale
        real_y = y / self.manual_view_scale
        self.manual_points.append((real_x, real_y))
        
        temp_img = self.original_image.copy()
        r = int(max(temp_img.shape) * 0.005) + 2
        for pt in self.manual_points:
            cv2.circle(temp_img, (int(pt[0]), int(pt[1])), r, (0, 0, 255), -1)
        
        h, w = temp_img.shape[:2]
        disp_w, disp_h = int(w * self.manual_view_scale), int(h * self.manual_view_scale)
        resized_view = cv2.resize(temp_img, (disp_w, disp_h))
        self.display_cv_image(resized_view)

        if len(self.manual_points) == 1:
            self.status_label.setText("Click RIGHT EYE center.")
        elif len(self.manual_points) == 2:
            p1 = np.array(self.manual_points[0])
            p2 = np.array(self.manual_points[1])
            dist = np.linalg.norm(p1 - p2)
            center_x = (p1[0] + p2[0]) / 2.0
            center_y = (p1[1] + p2[1]) / 2.0
            h, w = self.original_image.shape[:2]
            
            self.pd_pixel_base = dist
            self.angle_correction = 1.0
            self.face_center_ratio = (center_x / w, center_y / h)
            
            self.manual_mode = False
            self.status_label.setText(f"Manual Set. PD: {dist:.1f}px")
            self.btn_save.setEnabled(True)
            self.refresh_view()

    def get_target_pd(self):
        return self.spin_pd.value()

    def _on_pd_preset_selected(self, index: int):
        """Handle a PD preset selection."""
        txt = self.combo_pd.currentText()
        m = re.search(r"\((\d+(\.\d+)?)\)", txt)
        if m:
            self.spin_pd.setValue(float(m.group(1)))
        # Keep the current spin_pd value for the Custom option.

    def refresh_view(self):
        if self.original_image is None or self.pd_pixel_base is None or self.manual_mode:
            return

        target_pd_mm = self.get_target_pd()
        ppi = self.spin_ppi.value()
        px_per_mm = ppi / 25.4
        
        estimated_pd_px = self.pd_pixel_base * self.angle_correction
        base_scale = (target_pd_mm * px_per_mm) / estimated_pd_px
        
        sensitivity = self.spin_sens.value()
        tracking_delta = (self.dynamic_ratio - 1.0) * sensitivity
        final_scale = base_scale * (1.0 + tracking_delta)
        
        if final_scale < 0.01: final_scale = 0.01
        
        h, w = self.original_image.shape[:2]
        new_w, new_h = int(w * final_scale), int(h * final_scale)
        
        if new_w > 20000 or new_h > 20000:
            self.status_label.setText("Warning: Image too large to render.")
            return

        self.current_scale = final_scale
        resized_img = cv2.resize(self.original_image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

        if self.chk_grid.isChecked():
            grid_color = (0, 255, 0)
            step_mm = 10.0
            step_px = int(step_mm * px_per_mm)
            for x in range(0, new_w, step_px):
                cv2.line(resized_img, (x, 0), (x, new_h), grid_color, 1)
            for y in range(0, new_h, step_px):
                cv2.line(resized_img, (0, y), (new_w, y), grid_color, 1)

        self.display_cv_image(resized_img)
        QTimer.singleShot(0, self.center_on_face)

    def display_cv_image(self, cv_img):
        rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        q_img = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(q_img)
        
        self.canvas.setPixmap(pixmap)
        self.canvas.adjustSize()

    def center_on_face(self):
        if self.pd_pixel_base is None: return

        curr_w = self.canvas.width()
        curr_h = self.canvas.height()
        viewport_w = self.scroll_area.viewport().width()
        viewport_h = self.scroll_area.viewport().height()

        cx = curr_w * self.face_center_ratio[0]
        cy = curr_h * self.face_center_ratio[1]

        target_x = int(cx - (viewport_w / 2))
        target_y = int(cy - (viewport_h / 2))

        self.scroll_area.horizontalScrollBar().setValue(target_x)
        self.scroll_area.verticalScrollBar().setValue(target_y)

    def toggle_tracking(self, state):
        if self.chk_track.isChecked():
            self.webcam_worker.start()
            self.btn_calib.setEnabled(True)
            self.webcam_worker.calibrate()
        else:
            self.webcam_worker.stop()
            self.btn_calib.setEnabled(False)
            self.dynamic_ratio = 1.0
            self.refresh_view()

    @Slot(float)
    def on_tracking_update(self, ratio):
        if abs(self.dynamic_ratio - ratio) > 0.005:
            self.dynamic_ratio = ratio
            self.refresh_view()

    def save_image(self):
        if self.canvas.pixmap() is None: return
        fname, _ = QFileDialog.getSaveFileName(self, "Save View", "resized_view.jpg", "Images (*.jpg *.png)")
        if fname:
            self.canvas.pixmap().save(fname)
            QMessageBox.information(self, "Saved", "Image saved successfully.")

    # --- Monitor Detection ---
    def _populate_monitors(self):
        """Populate the combo box with detected monitor information."""
        self._monitors = get_monitors()
        self.combo_monitor.blockSignals(True)
        self.combo_monitor.clear()

        current_monitor = get_monitor_for_widget(self)
        selected_idx = 0

        for i, mon in enumerate(self._monitors):
            self.combo_monitor.addItem(mon.display_label, mon)
            if current_monitor and mon.name == current_monitor.name:
                selected_idx = i

        # Add the Custom option last.
        self.combo_monitor.addItem("Custom (Manual Input)")

        self.combo_monitor.setCurrentIndex(selected_idx)
        self.combo_monitor.blockSignals(False)

        # Apply the initial PPI value.
        if self._monitors and selected_idx < len(self._monitors):
            self._current_monitor_name = self._monitors[selected_idx].name
            self.spin_ppi.setValue(self._monitors[selected_idx].ppi)

    def _on_monitor_selected(self, index: int):
        """Handle changes to the monitor-selection combo box."""
        if index < 0:
            return
        if index < len(self._monitors):
            mon = self._monitors[index]
            self._current_monitor_name = mon.name
            self.spin_ppi.setValue(mon.ppi)
        else:
            # Custom selection: manual PPI input mode.
            self._current_monitor_name = None

    def resizeEvent(self, event):
        """Keep the image centered when the window is resized."""
        super().resizeEvent(event)
        if getattr(self, 'pd_pixel_base', None) is not None:
            QTimer.singleShot(0, self.center_on_face)
        if hasattr(self, '_update_floating_btn_pos'):
            self._update_floating_btn_pos()

    def moveEvent(self, event):
        """Detect monitor changes when the window moves."""
        super().moveEvent(event)
        current = get_monitor_for_widget(self)
        if current is None:
            return
        if self._current_monitor_name and current.name != self._current_monitor_name:
            self.status_label.setText(
                f"Monitor changed: {current.name} ({current.ppi:.1f} PPI). "
                f"You can update it from the combo box."
            )
            # Automatically select the matching monitor in the combo box.
            for i, mon in enumerate(self._monitors):
                if mon.name == current.name:
                    self.combo_monitor.setCurrentIndex(i)
                    break

    # --- Fullscreen ---
    def _update_floating_btn_pos(self):
        """Move the floating button to the top right."""
        if hasattr(self, 'btn_exit_fs') and self.btn_exit_fs.isVisible():
            self.btn_exit_fs.resize(self.btn_exit_fs.sizeHint())
            self.btn_exit_fs.move(self.width() - self.btn_exit_fs.width() - 20, 20)

    def toggle_fullscreen(self):
        """Toggle fullscreen mode."""
        if self.isFullScreen():
            self.exit_fullscreen()
        else:
            self.controls_widget.hide()
            self.statusBar().hide()
            self.showFullScreen()
            self.btn_fullscreen.setText("Exit Fullscreen (F11)")
            
            self.btn_exit_fs.show()
            self.btn_exit_fs.raise_()
            self._update_floating_btn_pos()

    def exit_fullscreen(self):
        """Exit fullscreen mode."""
        if not self.isFullScreen():
            return
        self.btn_exit_fs.hide()
        self.controls_widget.show()
        self.statusBar().show()
        self.showNormal()
        self.btn_fullscreen.setText("Fullscreen (F11)")

    # --- Settings Persistence ---
    def _load_settings(self):
        """Restore saved settings."""
        # Prefer a saved PPI value to preserve manual calibration.
        saved_ppi = self._settings.ppi()
        saved_monitor = self._settings.monitor_name()

        if saved_monitor:
            # Select the saved monitor name if it is in the list.
            for i, mon in enumerate(self._monitors):
                if mon.name == saved_monitor:
                    self.combo_monitor.blockSignals(True)
                    self.combo_monitor.setCurrentIndex(i)
                    self.combo_monitor.blockSignals(False)
                    self._current_monitor_name = saved_monitor
                    break

        if saved_ppi != 96.0:  # Apply the saved value if it is not the default.
            self.spin_ppi.setValue(saved_ppi)

        # Target PD
        saved_pd_text = self._settings.target_pd_text()
        saved_pd_value = self._settings.target_pd_value()

        idx = self.combo_pd.findText(saved_pd_text)
        if idx >= 0:
            self.combo_pd.blockSignals(True)
            self.combo_pd.setCurrentIndex(idx)
            self.combo_pd.blockSignals(False)
        
        self.spin_pd.setValue(saved_pd_value)

        # Grid
        self.chk_grid.setChecked(self._settings.show_grid())

        # Sensitivity
        self.spin_sens.setValue(self._settings.sensitivity())

        # Window geometry
        geometry = self._settings.window_geometry()
        if geometry:
            self.restoreGeometry(geometry)

    def _save_settings(self):
        """Save the current settings."""
        self._settings.save_all(
            ppi=self.spin_ppi.value(),
            monitor_name=self._current_monitor_name or "",
            target_pd_text=self.combo_pd.currentText(),
            target_pd_value=self.spin_pd.value(),
            show_grid=self.chk_grid.isChecked(),
            sensitivity=self.spin_sens.value(),
            geometry=self.saveGeometry(),
        )

    def _check_screen_resolution(self):
        """Warn at startup if no screen meets the minimum resolution."""
        warnings = check_all_monitors()
        if warnings:
            QMessageBox.warning(
                self,
                "Screen Resolution Warning",
                "\n\n".join(warnings),
            )

    def closeEvent(self, event):
        self._save_settings()
        self.webcam_worker.stop()
        event.accept()
