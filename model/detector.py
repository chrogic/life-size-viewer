import math
from pathlib import Path
import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


DEFAULT_MODEL_PATH = str(Path(__file__).resolve().parent.parent / "face_landmarker.task")

class FaceDetector:
    """MediaPipeを使用した静止画の顔検出ロジックを管理するクラス"""
    def __init__(self, model_path: str | None = None):
        self.model_path = model_path or DEFAULT_MODEL_PATH
        self.detector = self._create_detector()
        self.LEFT_IRIS_IDX = 468
        self.RIGHT_IRIS_IDX = 473

    def _create_detector(self):
        try:
            base_options = python.BaseOptions(model_asset_path=self.model_path)
            options = vision.FaceLandmarkerOptions(
                base_options=base_options,
                output_face_blendshapes=False,
                output_facial_transformation_matrixes=True,
                num_faces=1
            )
            return vision.FaceLandmarker.create_from_options(options)
        except Exception as e:
            print(f"FaceDetector Init Error: {e}")
            return None

    def analyze(self, image_bgr: np.ndarray):
        """
        画像を解析し、瞳孔間距離(px)、補正係数、顔の中心座標(px)を返す。
        全体画像で検出できない場合、4分割して再試行する。
        Returns: (dist_px, correction_factor, (center_x, center_y))
        """
        # 1. まず全体画像で試行
        result = self._detect_single(image_bgr)
        if result[0] is not None:
            return result

        # 2. 全体で検出できなければ、重複付き4分割で試行
        return self._detect_with_quadrants(image_bgr)

    def _detect_single(self, image_bgr: np.ndarray):
        """
        単一画像の顔検出を実行する（内部メソッド）。
        Returns: (dist_px, correction_factor, (center_x, center_y))
        """
        if self.detector is None:
            return None, 1.0, None

        h, w, _ = image_bgr.shape
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb)
        
        try:
            result = self.detector.detect(mp_image)
        except Exception:
            return None, 1.0, None

        if not result.face_landmarks:
            return None, 1.0, None

        landmarks = result.face_landmarks[0]
        lx, ly = landmarks[self.LEFT_IRIS_IDX].x * w, landmarks[self.LEFT_IRIS_IDX].y * h
        rx, ry = landmarks[self.RIGHT_IRIS_IDX].x * w, landmarks[self.RIGHT_IRIS_IDX].y * h
        
        # 画面上の単純距離
        apparent_dist = np.hypot(lx - rx, ly - ry)
        center_pt = ((lx + rx) / 2.0, (ly + ry) / 2.0)

        # 角度補正 (Yaw)
        correction_factor = 1.0
        if result.facial_transformation_matrixes:
            try:
                matrix = result.facial_transformation_matrixes[0]
                yaw = math.atan2(matrix[2], matrix[0])
                max_angle = math.radians(60)
                yaw = max(min(yaw, max_angle), -max_angle)
                projection = math.cos(yaw)
                if projection < 0.5: projection = 0.5
                correction_factor = 1.0 / projection
            except Exception:
                pass

        return apparent_dist, correction_factor, center_pt

    def _detect_with_quadrants(self, image_bgr: np.ndarray):
        """
        画像を重複付き4分割し、各領域で顔検出を試みる。
        検出時は座標を元画像の座標系に変換して返す。

        各領域は画像の 62.5% x 62.5%（25%オーバーラップ）
        """
        h, w = image_bgr.shape[:2]
        qw = int(w * 0.625)
        qh = int(h * 0.625)

        # (x_offset, y_offset) で各領域の左上座標を定義
        quadrants = [
            (0,      0),          # 左上
            (w - qw, 0),          # 右上
            (0,      h - qh),     # 左下
            (w - qw, h - qh),     # 右下
        ]

        for ox, oy in quadrants:
            crop = image_bgr[oy:oy + qh, ox:ox + qw]
            dist, correction, center = self._detect_single(crop)

            if dist is not None:
                # 座標を元画像の座標系に変換
                original_center = (center[0] + ox, center[1] + oy)
                return dist, correction, original_center

        return None, 1.0, None
