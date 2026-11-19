import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision
import cv2
import asyncio
import os
import sys
import time
import base64
import threading
import numpy as np
import urllib.request

class FaceAuthenticator:
    """
    Enterprise-grade biometric face authenticator using Google MediaPipe Face Landmarker.
    Provides progressive multi-sample enrollment, quality assessment, and high-accuracy owner recognition.
    """
    MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
    MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "face_landmarker.task")
    
    # Biometric match calibration
    MATCH_SIMILARITY_THRESHOLD = 0.932       # Calibrated threshold for normalized 3D landmarks
    HIGH_CONFIDENCE_THRESHOLD = 0.958        # Instant single-frame unlock threshold
    REQUIRED_CONSECUTIVE_MATCHES = 2         # Frames required at standard threshold (anti-jitter, ~80ms)
    ENROLLMENT_SAMPLE_TARGET = 5             # High-quality samples for composite master profile
    
    def __init__(self, reference_image_path="reference.jpg", on_status_change=None, on_frame=None, on_enroll_progress=None):
        self.reference_image_path = os.path.abspath(reference_image_path)
        base, _ = os.path.splitext(self.reference_image_path)
        self.landmarks_file_path = f"{base}_landmarks.npy"
        
        self.on_status_change = on_status_change
        self.on_frame = on_frame
        self.on_enroll_progress = on_enroll_progress
        
        self.authenticated = False
        self.running = False
        self.reference_landmarks = None
        self.reference_ensemble = []
        self.landmarker = None
        
        # Thread safety & lifecycle
        self._lock = threading.Lock()
        self._cv_thread = None
        self._stop_event = threading.Event()
        
        # Registration & enrollment state
        self.registration_mode = False
        self.enrollment_active = False
        self.enrollment_samples = []          # List of (landmarks_vec, frame_copy, sharpness)
        self._latest_frame = None
        self._consecutive_matches = 0
        
        self._ensure_model()
        self._init_landmarker()
        self._load_reference()

    def _ensure_model(self):
        """Download the MediaPipe Face Landmarker model if not present."""
        if not os.path.exists(self.MODEL_PATH):
            print(f"[AUTH] Downloading Face Landmarker model to {self.MODEL_PATH}...")
            try:
                urllib.request.urlretrieve(self.MODEL_URL, self.MODEL_PATH)
                print(f"[AUTH] [OK] Model downloaded successfully.")
            except Exception as e:
                print(f"[AUTH] [ERR] Failed to download model: {e}")

    def _init_landmarker(self):
        """Initialize the MediaPipe Face Landmarker detector."""
        if not os.path.exists(self.MODEL_PATH):
            print("[AUTH] [ERR] Face Landmarker model file missing.")
            return
        
        try:
            base_options = mp_python.BaseOptions(model_asset_path=self.MODEL_PATH)
            options = vision.FaceLandmarkerOptions(
                base_options=base_options,
                output_face_blendshapes=False,
                output_facial_transformation_matrixes=False,
                num_faces=1
            )
            self.landmarker = vision.FaceLandmarker.create_from_options(options)
            print("[AUTH] [OK] MediaPipe Face Landmarker initialized.")
        except Exception as e:
            print(f"[AUTH] [ERR] Failed to initialize Face Landmarker: {e}")

    def _extract_landmarks(self, image_rgb):
        """
        Extract centered and scale-normalized face landmarks from an RGB image.
        Returns:
            normalized_vec: Flattened numpy array of 1434 floats (478 points * 3D), or None
            raw_coords: (478, 3) raw coordinate array [0..1], or None
        """
        if self.landmarker is None:
            return None, None
        
        try:
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb)
            result = self.landmarker.detect(mp_image)
            
            if result.face_landmarks and len(result.face_landmarks) > 0:
                landmarks = result.face_landmarks[0]
                coords = np.array([[lm.x, lm.y, lm.z] for lm in landmarks], dtype=np.float32)
                
                # Center-normalize (translation invariant)
                mean = np.mean(coords, axis=0)
                centered = coords - mean
                
                # Scale-normalize (scale and distance invariant)
                scale = np.std(centered)
                if scale > 1e-6:
                    normalized = centered / scale
                else:
                    normalized = centered
                    
                # Normalize vector to unit length
                vec = normalized.flatten()
                norm = np.linalg.norm(vec)
                if norm > 0:
                    vec = vec / norm
                    
                return vec, coords
            return None, None
        except Exception as e:
            print(f"[AUTH] [ERR] Landmark extraction exception: {e}")
            return None, None

    def _assess_quality(self, frame_bgr, raw_coords):
        """
        Evaluate face alignment, distance, centering, and frame sharpness.
        Returns (is_acceptable: bool, quality_msg: str, is_centered: bool, is_distance_ok: bool)
        """
        if raw_coords is None:
            return False, "Position your face in the camera view", False, False

        # Calculate bounding box in normalized [0..1] coordinates
        xs = raw_coords[:, 0]
        ys = raw_coords[:, 1]
        min_x, max_x = float(np.min(xs)), float(np.max(xs))
        min_y, max_y = float(np.min(ys)), float(np.max(ys))
        
        center_x = (min_x + max_x) / 2.0
        center_y = (min_y + max_y) / 2.0
        face_height = max_y - min_y
        
        is_centered = (0.28 <= center_x <= 0.72) and (0.20 <= center_y <= 0.80)
        is_distance_ok = (0.22 <= face_height <= 0.85)

        # Check pose symmetry (nose tip vs outer eye corners)
        # Landmark 1: nose tip, 33: left eye outer, 263: right eye outer
        try:
            nose_x = raw_coords[1, 0]
            left_eye_x = raw_coords[33, 0]
            right_eye_x = raw_coords[263, 0]
            eye_dist = abs(right_eye_x - left_eye_x)
            
            if eye_dist > 0.05:
                left_ratio = abs(nose_x - left_eye_x) / eye_dist
                # Ratio should be ~0.5 if looking straight ahead
                is_facing_front = (0.32 <= left_ratio <= 0.68)
            else:
                is_facing_front = True
        except Exception:
            is_facing_front = True

        # Check image sharpness (Laplacian variance)
        try:
            gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
            sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
        except Exception:
            sharpness = 100.0

        if not is_facing_front:
            return False, "Please look directly at the camera", is_centered, is_distance_ok
        if not is_centered:
            return False, "Center your face in the reticle", is_centered, is_distance_ok
        if face_height < 0.22:
            return False, "Move slightly closer to the camera", is_centered, is_distance_ok
        if face_height > 0.85:
            return False, "Move slightly further from the camera", is_centered, is_distance_ok
        if sharpness < 20.0:
            return False, "Hold steady (motion blur detected)", is_centered, is_distance_ok

        return True, "Face aligned! Hold steady", is_centered, is_distance_ok

    def _compare_landmarks(self, ref_landmarks, cur_landmarks):
        """
        Compare current landmarks against reference embedding and ensemble.
        Returns (is_match: bool, similarity: float).
        """
        if ref_landmarks is None or cur_landmarks is None:
            return False, 0.0
        
        # Primary comparison against canonical master profile
        similarity = float(np.dot(ref_landmarks, cur_landmarks))
        
        # Check ensemble variations if available (multi-sample tolerance)
        best_similarity = similarity
        for sample_vec in self.reference_ensemble:
            s = float(np.dot(sample_vec, cur_landmarks))
            if s > best_similarity:
                best_similarity = s
                
        # Use weighted score favoring master profile but allowing nearest valid pose
        final_similarity = 0.7 * similarity + 0.3 * best_similarity
        
        is_match = False
        if final_similarity >= self.HIGH_CONFIDENCE_THRESHOLD:
            is_match = True
        elif final_similarity >= self.MATCH_SIMILARITY_THRESHOLD:
            self._consecutive_matches += 1
            if self._consecutive_matches >= self.REQUIRED_CONSECUTIVE_MATCHES:
                is_match = True
        else:
            self._consecutive_matches = max(0, self._consecutive_matches - 1)
            
        return is_match, final_similarity

    def _load_reference(self):
        """Load stored biometric profile from .npy file or compute from reference.jpg."""
        if os.path.exists(self.landmarks_file_path):
            try:
                data = np.load(self.landmarks_file_path, allow_pickle=True)
                if isinstance(data, dict) or (isinstance(data, np.ndarray) and data.dtype == object):
                    # Loaded dictionary containing master and ensemble
                    profile = data.item() if hasattr(data, 'item') else data
                    self.reference_landmarks = profile.get('master')
                    self.reference_ensemble = profile.get('samples', [])
                else:
                    # Legacy 1D vector
                    self.reference_landmarks = data
                    self.reference_ensemble = [data]
                    
                print(f"[AUTH] [OK] Loaded biometric master profile from {os.path.basename(self.landmarks_file_path)}")
                return
            except Exception as e:
                print(f"[AUTH] [WARN] Could not load .npy landmarks: {e}")

        # Fallback: compute from reference.jpg
        if os.path.exists(self.reference_image_path):
            try:
                img_bgr = cv2.imread(self.reference_image_path)
                if img_bgr is not None:
                    image_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
                    landmarks_vec, _ = self._extract_landmarks(image_rgb)
                    if landmarks_vec is not None:
                        self.reference_landmarks = landmarks_vec
                        self.reference_ensemble = [landmarks_vec]
                        np.save(self.landmarks_file_path, {'master': landmarks_vec, 'samples': [landmarks_vec]})
                        print("[AUTH] [OK] Extracted and cached reference face landmarks successfully.")
                        return
            except Exception as e:
                print(f"[AUTH] [ERR] Error reading reference image: {e}")
                
        self.reference_landmarks = None
        self.reference_ensemble = []
        print(f"[AUTH] [INFO] No reference face enrolled yet.")

    def is_registered(self):
        """Returns True if an owner face is registered."""
        return self.reference_landmarks is not None

    def start_authentication_loop(self):
        """Starts or switches camera to owner authentication mode safely."""
        with self._lock:
            if self.running and self._cv_thread and self._cv_thread.is_alive():
                self.registration_mode = False
                self.enrollment_active = False
                self.authenticated = False
                self._consecutive_matches = 0
                print("[AUTH] Switched camera seamlessly to authentication mode.")
                return True

            if self.reference_landmarks is None:
                self._load_reference()
                if self.reference_landmarks is None:
                    print("[AUTH] [WARN] Cannot start auth loop: No reference face enrolled.")
                    return False

            self.registration_mode = False
            self.enrollment_active = False
            self.authenticated = False
            self.running = True
            self._stop_event.clear()
            self._consecutive_matches = 0
            
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.get_event_loop()

            self._cv_thread = threading.Thread(target=self._run_cv_loop, args=(loop,), daemon=True)
            self._cv_thread.start()
            print("[AUTH] Started camera worker thread for authentication.")
            return True

    def start_registration_loop(self):
        """Starts or switches camera to face enrollment mode safely without hardware restarts."""
        with self._lock:
            if self.running and self._cv_thread and self._cv_thread.is_alive():
                self.registration_mode = True
                self.enrollment_active = False
                self.authenticated = False
                self._consecutive_matches = 0
                print("[AUTH] Switched camera seamlessly to enrollment mode.")
                return True

            self.registration_mode = True
            self.enrollment_active = False
            self.authenticated = False
            self.running = True
            self._stop_event.clear()
            self._consecutive_matches = 0
            
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.get_event_loop()

            self._cv_thread = threading.Thread(target=self._run_cv_loop, args=(loop,), daemon=True)
            self._cv_thread.start()
            print("[AUTH] Started camera worker thread for face enrollment.")
            return True

    def start_enrollment_sequence(self):
        """Triggers the progressive multi-sample biometric enrollment process."""
        self.registration_mode = True
        self.enrollment_samples = []
        self.enrollment_active = True
        print("[AUTH] Initiating 5-sample progressive biometric enrollment...")
        return True

    def stop(self):
        """Requests camera loop to stop."""
        self.running = False
        self._stop_event.set()
        print("[AUTH] Stop requested for biometric camera loop.")

    def _open_camera(self):
        """Open camera safely with fallback backend."""
        device_indices = [0, 1]
        backends = [cv2.CAP_DSHOW, cv2.CAP_ANY] if sys.platform == 'win32' else [cv2.CAP_ANY]
        
        for idx in device_indices:
            for backend in backends:
                try:
                    cap = cv2.VideoCapture(idx, backend)
                    if cap.isOpened():
                        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                        ret, frame = cap.read()
                        if ret and frame is not None and frame.size > 0:
                            print(f"[AUTH] [OK] Successfully opened camera device {idx} (backend {backend}).")
                            return cap
                        cap.release()
                except Exception as e:
                    print(f"[AUTH] Camera open attempt device {idx} backend {backend} failed: {e}")
                    
        return None

    def _run_cv_loop(self, loop):
        """Dedicated background thread capturing frames, assessing quality, and matching."""
        cap = self._open_camera()
        if cap is None:
            print("[AUTH] [ERR] Could not open camera device. Aborting.")
            self.running = False
            return

        process_every_n = 2
        frame_count = 0
        current_similarity = 0.0
        face_detected = False
        quality_msg = "Looking for face..."
        is_centered = False
        is_distance_ok = False

        try:
            while self.running and not self._stop_event.is_set() and not self.authenticated:
                ret, frame = cap.read()
                if not ret or frame is None:
                    time.sleep(0.04)
                    continue

                self._latest_frame = frame.copy()
                frame_count += 1

                if frame_count % process_every_n == 0:
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    landmarks_vec, raw_coords = self._extract_landmarks(rgb_frame)
                    face_detected = (landmarks_vec is not None)

                    if self.registration_mode:
                        # Quality assessment for enrollment
                        is_acceptable, quality_msg, is_centered, is_distance_ok = self._assess_quality(frame, raw_coords)
                        
                        # Handle active progressive multi-sample enrollment
                        if self.enrollment_active and is_acceptable and landmarks_vec is not None:
                            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                            sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
                            
                            # Add sample
                            self.enrollment_samples.append((landmarks_vec, frame.copy(), sharpness))
                            current_count = len(self.enrollment_samples)
                            progress_percent = int((current_count / self.ENROLLMENT_SAMPLE_TARGET) * 100)
                            
                            if self.on_enroll_progress:
                                asyncio.run_coroutine_threadsafe(
                                    self.on_enroll_progress({
                                        'progress': progress_percent,
                                        'samples': current_count,
                                        'total': self.ENROLLMENT_SAMPLE_TARGET,
                                        'message': f"Calibrating facial geometry... ({progress_percent}%)"
                                    }),
                                    loop
                                )
                                
                            # When target reached: finalize composite master profile
                            if current_count >= self.ENROLLMENT_SAMPLE_TARGET:
                                self._finalize_enrollment(loop)
                                break
                    else:
                        # Authentication mode
                        if face_detected and self.reference_landmarks is not None:
                            is_match, current_similarity = self._compare_landmarks(self.reference_landmarks, landmarks_vec)
                            
                            if is_match:
                                self.authenticated = True
                                self.running = False
                                print(f"[AUTH] [OPEN] OWNER FACE VERIFIED! Similarity: {current_similarity:.4f}. Access Granted.")
                                if self.on_status_change:
                                    asyncio.run_coroutine_threadsafe(self.on_status_change(True), loop)
                        else:
                            current_similarity = 0.0
                            self._consecutive_matches = 0

                # Send frame and rich telemetry to frontend
                if self.on_frame:
                    small_frame = cv2.resize(frame, (320, 240), interpolation=cv2.INTER_AREA)
                    _, buffer = cv2.imencode('.jpg', small_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 65])
                    b64_str = base64.b64encode(buffer).decode('utf-8')
                    
                    frame_payload = {
                        'image': b64_str,
                        'face_detected': face_detected,
                        'face_centered': is_centered,
                        'face_distance_ok': is_distance_ok,
                        'quality_msg': quality_msg,
                        'similarity': round(float(current_similarity), 3),
                        'is_registering': self.registration_mode,
                        'enrollment_active': self.enrollment_active,
                        'enrollment_progress': int((len(self.enrollment_samples) / self.ENROLLMENT_SAMPLE_TARGET) * 100) if self.enrollment_active else 0,
                        'authenticated': self.authenticated
                    }
                    asyncio.run_coroutine_threadsafe(self.on_frame(frame_payload), loop)

                time.sleep(0.035)
        finally:
            cap.release()
            self.running = False
            print("[AUTH] Camera device released cleanly.")

    def _finalize_enrollment(self, loop=None):
        """Computes the master composite embedding from captured enrollment samples and saves reference."""
        if not self.enrollment_samples:
            return False, "No enrollment samples available."

        try:
            # 1. Compute canonical mean embedding across all samples
            all_vecs = [s[0] for s in self.enrollment_samples]
            mean_vec = np.mean(all_vecs, axis=0)
            norm = np.linalg.norm(mean_vec)
            if norm > 0:
                master_vec = mean_vec / norm
            else:
                master_vec = mean_vec

            # 2. Select sharpest frame as visual reference photo
            sorted_by_sharpness = sorted(self.enrollment_samples, key=lambda s: s[2], reverse=True)
            best_frame = sorted_by_sharpness[0][1]

            # 3. Save reference files
            cv2.imwrite(self.reference_image_path, best_frame)
            
            profile_data = {
                'master': master_vec,
                'samples': all_vecs
            }
            np.save(self.landmarks_file_path, profile_data)

            # 4. Update in-memory state
            self.reference_landmarks = master_vec
            self.reference_ensemble = all_vecs
            self.registration_mode = False
            self.enrollment_active = False
            self.authenticated = True
            self.running = False
            
            print(f"[AUTH] [OK] Master composite profile created from {len(all_vecs)} samples and saved!")
            if self.on_status_change and loop:
                asyncio.run_coroutine_threadsafe(self.on_status_change(True), loop)
            return True, "Master biometric profile enrolled successfully!"
        except Exception as e:
            print(f"[AUTH] [ERR] Error finalizing enrollment: {e}")
            return False, f"Enrollment finalization failed: {e}"

    def register_current_face(self, frame_b64=None):
        """Manual single-frame enrollment fallback."""
        frame = None
        if frame_b64:
            try:
                if ',' in frame_b64:
                    frame_b64 = frame_b64.split(',', 1)[1]
                img_bytes = base64.b64decode(frame_b64)
                nparr = np.frombuffer(img_bytes, np.uint8)
                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            except Exception as e:
                print(f"[AUTH] [ERR] Failed decoding base64 image: {e}")

        if frame is None and self._latest_frame is not None:
            frame = self._latest_frame.copy()

        if frame is None:
            return False, "No camera frame available. Please ensure camera is active."

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        landmarks_vec, _ = self._extract_landmarks(rgb_frame)

        if landmarks_vec is None:
            return False, "No face detected. Please position face clearly in good lighting."

        try:
            cv2.imwrite(self.reference_image_path, frame)
            profile_data = {'master': landmarks_vec, 'samples': [landmarks_vec]}
            np.save(self.landmarks_file_path, profile_data)
            
            self.reference_landmarks = landmarks_vec
            self.reference_ensemble = [landmarks_vec]
            self.registration_mode = False
            self.enrollment_active = False
            self.running = False
            self.authenticated = True
            print(f"[AUTH] [OK] Single-frame biometric profile saved.")
            return True, "Owner face enrolled successfully."
        except Exception as e:
            return False, f"Failed saving face profile: {str(e)}"

    def delete_registration(self):
        """Deletes enrolled face reference and clears memory."""
        for path in [self.reference_image_path, self.landmarks_file_path]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                    print(f"[AUTH] Deleted {path}")
                except Exception as e:
                    print(f"[AUTH] [ERR] Could not delete {path}: {e}")
                    
        self.reference_landmarks = None
        self.reference_ensemble = []
        self.authenticated = False
        self.registration_mode = False
        self.enrollment_active = False
        self.enrollment_samples = []
        self._consecutive_matches = 0
        print("[AUTH] Enrolled face data cleared.")
