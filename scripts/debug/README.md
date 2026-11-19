# Smarty Diagnostic & Hardware Verification Suite

This directory contains standalone diagnostics, hardware verification scripts, and developer debugging utilities for Smarty subsystems.

## Scripts Overview

### Voice & Multilingual
- `test_multilingual_speech.py`: Tests Smarty's Edge-TTS voice routing across multiple languages (English, Hindi, Hinglish, Spanish, French, German, Japanese, Russian, Turkish).
- `test_speech.py`: Quick test of baseline speech synthesis.

### Vision & Face Authentication
- `test_face_rec.py`: Tests MediaPipe face detection, landmark extraction, and cosine similarity scoring.
- `hand_gesture_test.py`: Interactive OpenCV webcam test for real-time hand gesture tracking.
- `test_vision.py`: Tests OpenRouter/Nemotron vision multimodal capabilities.

### 3D CAD & Printer Diagnostics
- `verify_cad.py`: Tests build123d CAD agent generation of STL primitives.
- `verify_iteration_mock.py`: Tests iterative CAD refinement loop with mocked visual feedback.
- `test_cad_install.py`: Verifies build123d, cadquery, and OpenCascade dependencies.
- `debug_printer_connection.py`: Tests direct HTTP / REST connection to 3D printers (Moonraker / OctoPrint).
- `debug_mdns.py`: Probes local network for mDNS / Zeroconf advertised printers and IoT devices.

### System & AI
- `test_openrouter.py`: Tests OpenRouter API client connectivity and tool calling.
- `check_cuda.py`: Verifies PyTorch GPU / CUDA acceleration availability.
- `test_imports.py`: Verifies all required backend Python libraries can be imported cleanly.
