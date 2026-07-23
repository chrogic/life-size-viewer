# Universal Life-Size Viewer

Universal Life-Size Viewer is a Python application for displaying portrait images at life size on a monitor. It uses MediaPipe face detection to estimate pupillary distance (PD) and optionally tracks the viewer's distance with a webcam.

## Features

- **Automatic detection:** Estimates PD when an image is loaded, then displays it at life size based on the target PD (for example, 64 mm) and the monitor PPI.
- **Robust face detection:** If whole-image detection fails, retries with four overlapping image regions.
- **Monitor detection:** Detects connected monitors at startup and supports multi-monitor setups.
- **Manual mode:** Lets you click the pupils to set PD when automatic detection is unavailable.
- **Distance tracking (Dolly Zoom):** Uses a webcam to keep the subject's apparent size consistent as the viewer moves closer to or farther from the screen.
- **Additional tools:**
  - Full-screen mode (`F` to toggle and `Esc` to exit)
  - 10 mm grid overlay
  - Save resized images with the grid applied
  - Persistent settings between launches

## Setup and run

### Prerequisites

- Python 3.10 or later
- For accurate life-size display: a monitor that reports its physical dimensions, or a correctly configured PPI value
- A webcam, only if you want to use distance tracking

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Add the model file

Download MediaPipe's `face_landmarker.task` model and place it in the project root, alongside `main.py`. Face detection requires this file.

Download the model from the [official MediaPipe documentation](https://developers.google.com/mediapipe/solutions/vision/face_landmarker/index#models).

### 3. Run the app

```bash
python main.py
```

## Privacy and camera use

- The webcam is used only when distance tracking is enabled.
- Camera frames and face landmarks are processed temporarily on the local device to calculate a distance ratio. This application's code does not send them externally.
- The application does not record or save camera frames. Stop distance tracking or close the application when you are finished.

## Important notes

- Displayed dimensions depend on monitor physical-size information, the PPI setting, face-detection results, and the operating environment. Accuracy is not guaranteed.
- Do not use this application for medical, body-measurement, diagnostic, legal-evidence, or other accuracy-critical purposes.
- Obtain input images and MediaPipe model files only from trusted sources.

## License

MIT License. This software is provided **without warranty**; see [LICENSE](LICENSE) for details.
