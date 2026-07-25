import math
from pathlib import Path
import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


DEFAULT_MODEL_PATH = str(Path(__file__).resolve().parent.parent / "face_landmarker.task")

class FaceDetector:
    """Manages MediaPipe face detection for still images."""
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
        Analyze an image and return pupillary distance (px), correction factor,
        and face-center coordinates (px). If full-image detection fails, retry
        with four overlapping image regions.
        Returns: (dist_px, correction_factor, (center_x, center_y))
        """
        # 1. Try the full image first.
        result = self._detect_single(image_bgr)
        if result[0] is not None:
            return result

        # 2. If that fails, try four overlapping image regions.
        return self._detect_with_quadrants(image_bgr)

    def _detect_single(self, image_bgr: np.ndarray):
        """
        Detect a face in one image (internal method).
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
        
        # Straight-line distance in the image.
        apparent_dist = np.hypot(lx - rx, ly - ry)
        center_pt = ((lx + rx) / 2.0, (ly + ry) / 2.0)

        # Yaw-angle correction.
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
        Split the image into four overlapping regions and try face detection in
        each. When detection succeeds, convert coordinates to the original
        image coordinate system before returning them.

        Each region is 62.5% x 62.5% of the image (25% overlap).
        """
        h, w = image_bgr.shape[:2]
        qw = int(w * 0.625)
        qh = int(h * 0.625)

        # Define each region by its top-left (x_offset, y_offset) coordinate.
        quadrants = [
            (0,      0),          # Top left
            (w - qw, 0),          # Top right
            (0,      h - qh),     # Bottom left
            (w - qw, h - qh),     # Bottom right
        ]

        for ox, oy in quadrants:
            crop = image_bgr[oy:oy + qh, ox:ox + qw]
            dist, correction, center = self._detect_single(crop)

            if dist is not None:
                # Convert coordinates to the original image coordinate system.
                original_center = (center[0] + ox, center[1] + oy)
                return dist, correction, original_center

        return None, 1.0, None
