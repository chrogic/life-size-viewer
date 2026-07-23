import time
import math
from pathlib import Path
import cv2
import mediapipe as mp
from collections import deque
from PySide6.QtCore import QThread, Signal

# MediaPipe imports needed locally for the thread
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


DEFAULT_MODEL_PATH = str(Path(__file__).resolve().parent.parent / "face_landmarker.task")

class WebcamWorker(QThread):
    """Webカメラでユーザーの距離変化を監視するスレッド"""
    ratio_signal = Signal(float)  # 基準距離に対する現在の比率を送る

    def __init__(self, model_path: str | None = None):
        super().__init__()
        self.running = False
        self.model_path = model_path or DEFAULT_MODEL_PATH
        self.base_dist = None
        self.history = deque(maxlen=10) # スムージング用

    def calibrate(self):
        """現在の距離を基準(1.0)とする"""
        self.base_dist = None
        self.history.clear()

    def run(self):
        self.running = True
        
        # Workerスレッド内でDetectorを初期化 (スレッドセーフ対策)
        try:
            base_options = python.BaseOptions(model_asset_path=self.model_path)
            options = vision.FaceLandmarkerOptions(
                base_options=base_options,
                output_face_blendshapes=False,
                output_facial_transformation_matrixes=False,
                num_faces=1
            )
            detector = vision.FaceLandmarker.create_from_options(options)
        except Exception:
            print("Webcam Detector Failed")
            return

        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("Cannot open webcam")
            return

        LEFT_IRIS, RIGHT_IRIS = 468, 473

        while self.running:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.1)
                continue

            # MediaPipe処理
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            
            try:
                res = detector.detect(mp_img)
                ratio_out = 1.0

                if res.face_landmarks:
                    lms = res.face_landmarks[0]
                    lx, ly = lms[LEFT_IRIS].x, lms[LEFT_IRIS].y
                    rx, ry = lms[RIGHT_IRIS].x, lms[RIGHT_IRIS].y
                    # 正規化座標での距離を使用（解像度依存を減らす）
                    dist = math.hypot(lx - rx, ly - ry)

                    if self.base_dist is None:
                        self.base_dist = dist
                    
                    if self.base_dist > 0 and dist > 0:
                        raw_ratio = self.base_dist / dist
                        self.history.append(raw_ratio)
                        ratio_out = sum(self.history) / len(self.history)

                    self.ratio_signal.emit(ratio_out)
            except Exception:
                pass
            
            time.sleep(0.03) # ~30fps

        cap.release()

    def stop(self):
        self.running = False
        self.wait()
