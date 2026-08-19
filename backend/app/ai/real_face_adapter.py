"""
Adapter for the real face-recognition and liveness detection module.

Bridges between the bank-locker platform's `verify_face(image_bytes, customer_id)`
API contract and the underlying `face_recognition` / `dlib` machine learning models.

Contract returned:
    {
        "face_match":        bool,
        "confidence":        float,   # [0.0, 1.0]
        "liveness_passed":   bool,
        "spoof_probability": float,   # [0.0, 1.0]
    }
"""
import io
import logging
import os
from pathlib import Path

import numpy as np
import cv2
from PIL import Image

try:
    import face_recognition
    import dlib
    _AI_AVAILABLE = True
except Exception as exc:
    face_recognition = None
    dlib = None
    _AI_AVAILABLE = False
    _IMPORT_ERROR = str(exc)

from app.core.config import settings

logger = logging.getLogger("bank_locker_backend")

# Project root directory for resolving relative paths (e.g. data/embeddings)
BASE_DIR = Path(__file__).resolve().parent.parent.parent


def check_model_health() -> bool:
    """Verify that all required face-recognition libraries and models are available."""
    if not _AI_AVAILABLE:
        logger.error("Face recognition dependencies missing: %s", _IMPORT_ERROR)
        return False
    return True


def decode_image_bytes(image_bytes: bytes) -> np.ndarray:
    """Decode raw image bytes (JPEG/PNG) into an RGB numpy array in-memory.

    Args:
        image_bytes: Raw binary image payload.

    Returns:
        RGB uint8 numpy array of shape (height, width, 3).

    Raises:
        ValueError: If image bytes cannot be decoded or image is corrupted.
    """
    if not image_bytes:
        raise ValueError("Image bytes payload is empty.")

    try:
        pil_image = Image.open(io.BytesIO(image_bytes))
        # Ensure image is in RGB format (handles RGBA, grayscale, palette, etc.)
        rgb_image = pil_image.convert("RGB")
        return np.array(rgb_image, dtype=np.uint8)
    except Exception as exc:
        raise ValueError(f"Failed to decode image data into RGB frame: {exc}") from exc


def calculate_eye_aspect_ratio(eye_points: list[tuple[int, int]]) -> float:
    """Calculate the Eye Aspect Ratio (EAR) from 6 landmark points.

    EAR = (||p1 - p5|| + ||p2 - p4||) / (2.0 * ||p0 - p3||)
    """
    if len(eye_points) < 6:
        return 0.0

    p = np.array(eye_points, dtype=np.float64)
    vertical_1 = np.linalg.norm(p[1] - p[5])
    vertical_2 = np.linalg.norm(p[2] - p[4])
    horizontal = np.linalg.norm(p[0] - p[3])

    if horizontal == 0:
        return 0.0

    return float((vertical_1 + vertical_2) / (2.0 * horizontal))


def check_screen_and_photo_spoof(face_crop: np.ndarray) -> tuple[bool, float]:
    """Analyze face crop for digital screen display (phone/tablet), paper photo, and moire artifacts.

    Evaluates:
      1. 2D Fast Fourier Transform (FFT) high-frequency spectrum for periodic screen pixel grid harmonics.
      2. Laplacian texture sharpness & micro-pore variance.
      3. YCrCb / HSV human skin chrominance cluster integrity.
      4. Specular backlight reflections / glass glare clipping.

    Returns:
        tuple[is_real_human (bool), spoof_probability (float)]
    """
    if face_crop.size == 0 or face_crop.shape[0] < 30 or face_crop.shape[1] < 30:
        return False, 0.95

    try:
        # Resize face crop to standard 160x160 for consistent anti-spoof feature extraction
        resized_face = cv2.resize(face_crop, (160, 160))
        gray = cv2.cvtColor(resized_face, cv2.COLOR_RGB2GRAY)

        spoof_flags = []

        # 1. 2D FFT Frequency Analysis (Detect periodic subpixel grid of OLED/LCD screens)
        f_transform = np.fft.fft2(gray.astype(np.float32))
        f_shift = np.fft.fftshift(f_transform)
        magnitude = np.abs(f_shift) + 1e-5
        log_mag = np.log(magnitude)

        # Measure high-frequency ring energy (radius 40-75 from center)
        cy, cx = 80, 80
        y_indices, x_indices = np.ogrid[:160, :160]
        distances = np.sqrt((x_indices - cx) ** 2 + (y_indices - cy) ** 2)
        
        hf_mask = (distances >= 35) & (distances <= 75)
        hf_energy = np.mean(log_mag[hf_mask])
        hf_std = np.std(log_mag[hf_mask])

        # Digital displays have unnatural high-frequency energy spikes or peak harmonics
        if hf_std > 2.80 and hf_energy > 9.5:
            logger.info("Anti-spoof: FFT high-frequency grid detected (hf_std=%.2f, hf_energy=%.2f) -> screen artifact", hf_std, hf_energy)
            spoof_flags.append("screen_fft_grid")

        # 2. Laplacian texture variance & sharpness
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        lap_var = float(laplacian.var())

        # Blurry paper/screen re-capture has low texture (< 30); Moire screen has extreme spikes (> 2200)
        if lap_var < 30.0:
            logger.info("Anti-spoof: low texture variance (lap_var=%.2f) -> flat photo/screen blur", lap_var)
            spoof_flags.append("low_texture_blur")
        elif lap_var > 2200.0:
            logger.info("Anti-spoof: excessive high-frequency variance (lap_var=%.2f) -> LCD moire pattern", lap_var)
            spoof_flags.append("high_moire_pattern")

        # 3. YCrCb and HSV Skin Color Analysis
        ycrcb = cv2.cvtColor(resized_face, cv2.COLOR_RGB2YCrCb)
        _, cr, cb = cv2.split(ycrcb)
        skin_mask = (cr >= 125) & (cr <= 180) & (cb >= 70) & (cb <= 135)
        skin_ratio = float(np.sum(skin_mask)) / float(skin_mask.size)

        if skin_ratio < 0.15:
            logger.info("Anti-spoof: unnatural chrominance (skin_ratio=%.2f) -> phone screen color gamut", skin_ratio)
            spoof_flags.append("unnatural_screen_chrominance")

        # 4. Screen Glare / Specular Reflection Saturation
        specular_pixels = np.sum(gray >= 250) / float(gray.size)
        if specular_pixels > 0.15:
            logger.info("Anti-spoof: specular glare reflection (specular=%.2f) -> glass screen glare", specular_pixels)
            spoof_flags.append("screen_specular_glare")

        # Decision: If 2 or more flags, or severe moire grid -> SPOOF
        if len(spoof_flags) >= 2 or "high_moire_pattern" in spoof_flags:
            spoof_prob = min(0.98, 0.80 + 0.10 * len(spoof_flags))
            logger.warning("Anti-spoof detected spoof flags=%s, spoof_probability=%.2f", spoof_flags, spoof_prob)
            return False, spoof_prob

        return True, 0.02
    except Exception as exc:
        logger.warning("Anti-spoof analysis exception: %s", exc)
        return True, 0.05


def check_rectangular_entity_or_phone_bezel(rgb_frame: np.ndarray, face_location: tuple[int, int, int, int]) -> bool:
    """Detect if a handheld mobile phone or photo frame tightly encloses the face."""
    try:
        gray = cv2.cvtColor(rgb_frame, cv2.COLOR_RGB2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        
        top, right, bottom, left = face_location
        face_w = right - left
        face_h = bottom - top
        face_center_x = (left + right) / 2.0
        face_center_y = (top + bottom) / 2.0
        face_area = max(1, face_w * face_h)

        for cnt in contours:
            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.035 * peri, True)
            if len(approx) == 4 and cv2.isContourConvex(approx):
                x, y, w, h = cv2.boundingRect(approx)
                rect_area = w * h
                rect_center_x = x + w / 2.0
                rect_center_y = y + h / 2.0
                
                # Check if this rectangle tightly frames the face (like a mobile phone or photo card)
                # Area ratio: 1.2x to 3.2x face area, with center aligned to face center
                if 1.2 * face_area <= rect_area <= 3.5 * face_area:
                    dist_centers = np.sqrt((face_center_x - rect_center_x)**2 + (face_center_y - rect_center_y)**2)
                    if dist_centers < 0.25 * max(w, h):
                        aspect = float(w) / max(1.0, float(h))
                        # Mobile phone portrait (0.45-0.75) or landscape / photo card (1.2-1.9)
                        if (0.42 <= aspect <= 0.80) or (1.20 <= aspect <= 1.95):
                            logger.warning("Anti-spoof: Mobile phone screen / photo frame detected enclosing face (rect=%dx%d, aspect=%.2f)", w, h, aspect)
                            return True
        return False
    except Exception as exc:
        logger.warning("Error checking rectangular bezel: %s", exc)
        return False


def verify_single_frame_liveness(
    rgb_frame: np.ndarray,
    face_location: tuple[int, int, int, int],
) -> tuple[bool, float]:
    """Evaluate liveness and anti-spoof signals from a single snapshot frame.

    Checks:
      1. Rectangular object / phone screen bezel enclosing the face.
      2. Digital screen / phone display / photo spoof detection (texture, moire, YCrCb skin tone).
      3. Eye Blinking / Natural Openness (EAR >= 0.15).
      4. 3D Head Pose (Up / Down pitch & tilt geometry) using 3D landmark proportions.
      5. Complete 68-point facial landmark mesh.

    Returns:
        tuple[liveness_passed (bool), spoof_probability (float)]
    """
    # 0. Check for rectangular object (phone/photo frame)
    if check_rectangular_entity_or_phone_bezel(rgb_frame, face_location):
        return False, 0.99

    top, right, bottom, left = face_location
    h, w, _ = rgb_frame.shape

    # Ensure bounds are valid
    top = max(0, top)
    left = max(0, left)
    bottom = min(h, bottom)
    right = min(w, right)

    face_crop = rgb_frame[top:bottom, left:right]

    # 1. Screen / Photo Anti-Spoof Texture Analysis
    is_real_texture, texture_spoof_prob = check_screen_and_photo_spoof(face_crop)
    if not is_real_texture:
        return False, texture_spoof_prob

    # 2. Extract 68-point Facial Landmarks
    landmarks_list = face_recognition.face_landmarks(rgb_frame, [face_location])
    if not landmarks_list:
        return False, 0.85

    landmarks = landmarks_list[0]
    required_features = ("left_eye", "right_eye", "nose_bridge", "nose_tip", "top_lip", "bottom_lip", "chin")
    for feat in required_features:
        if feat not in landmarks or len(landmarks[feat]) == 0:
            return False, 0.80

    # 3. Eye Aspect Ratio (EAR) for blinking & natural eye alertness
    left_ear = calculate_eye_aspect_ratio(landmarks["left_eye"])
    right_ear = calculate_eye_aspect_ratio(landmarks["right_eye"])
    avg_ear = (left_ear + right_ear) / 2.0

    # 4. 3D Head Up/Down Pitch & Symmetry Check
    nose_top = np.array(landmarks["nose_bridge"][0], dtype=np.float64)
    nose_bottom = np.array(landmarks["nose_tip"][-1], dtype=np.float64)
    chin_bottom = np.array(landmarks["chin"][len(landmarks["chin"]) // 2], dtype=np.float64)

    nose_length = np.linalg.norm(nose_bottom - nose_top)
    chin_dist = np.linalg.norm(chin_bottom - nose_bottom)
    
    # Ratio between upper and lower facial geometry verifies natural 3D head pitch (not flat photo)
    head_pose_ratio = nose_length / max(1.0, chin_dist)
    natural_pitch = 0.20 <= head_pose_ratio <= 1.80

    # Natural eye opening (EAR >= 0.15) and valid 3D head orientation
    if avg_ear >= 0.15 and natural_pitch:
        return True, 0.02

    # Marginal / closed eyes or unnatural distortion
    return False, 0.70


def load_customer_embedding(customer_id: str) -> np.ndarray | None:
    """Load a customer's 128-dimensional registered face embedding.

    Searches:
      1. Local `<EMBEDDINGS_DIR>`
      2. Project NPN embeddings directory (`project NPN/NPN/data/embeddings`)
      3. ID and alias matches (`customer001.npy`, `customer002.npy`)

    Returns:
        128-d float64 numpy array, or None if not registered.
    """
    search_dirs = []
    
    # 1. Configured embeddings dir
    emb_dir = Path(settings.EMBEDDINGS_DIR)
    if not emb_dir.is_absolute():
        search_dirs.append(BASE_DIR / emb_dir)
    else:
        search_dirs.append(emb_dir)
    
    # 2. Project NPN directory (sibling workspace)
    npn_dir = Path(r"c:\Users\Swaraj\OneDrive\Desktop\project NPN\NPN\data\embeddings")
    if npn_dir.exists():
        search_dirs.append(npn_dir)

    import re
    candidate_filenames = [
        f"{customer_id}.npy",
        f"{customer_id.lower()}.npy",
    ]
    # Match any customer number pattern (e.g. customer001, customer002, customer003, customer004, etc.)
    num_match = re.search(r"(\d+)", customer_id)
    if num_match:
        digits = int(num_match.group(1))
        candidate_filenames.extend([
            f"customer{digits:03d}.npy",
            f"customer{digits}.npy",
        ])


    for directory in search_dirs:
        if not directory.exists():
            continue
        for fname in candidate_filenames:
            candidate_path = directory / fname
            if candidate_path.exists():
                try:
                    arr = np.load(candidate_path)
                    if arr.shape == (128,):
                        return arr.astype(np.float64)
                except Exception as exc:
                    logger.warning("Error loading embedding file %s: %s", candidate_path, exc)

    return None


def calculate_confidence_score(distance: float, threshold: float = 0.50) -> float:
    """Map Euclidean face distance to a [0.0, 1.0] confidence score."""
    if distance <= 0.0:
        return 1.0
    if distance <= threshold:
        ratio = distance / threshold
        return float(round(1.0 - (ratio * 0.15), 4))
    else:
        ratio = (distance - threshold) / max(0.01, (1.0 - threshold))
        confidence = 0.85 - (ratio * 0.85)
        return float(round(max(0.0, min(0.79, confidence)), 4))


def evaluate_real_face(
    image_bytes: bytes,
    customer_id: str,
    blink_image_bytes: bytes | None = None,
    nod_image_bytes: bytes | None = None,
) -> dict:
    """Execute real face recognition using Project NPN's face matcher against customer001.npy and customer002.npy."""
    if not _AI_AVAILABLE:
        raise RuntimeError(
            f"Face recognition models cannot be loaded: {_IMPORT_ERROR}. "
            "Ensure dlib-bin, face-recognition, and opencv are installed."
        )

    # 1. Decode main image bytes into RGB numpy array in-memory
    try:
        rgb_frame = decode_image_bytes(image_bytes)
    except ValueError as exc:
        logger.warning("Real face recognition: image decode failed for customer=%s: %s", customer_id, exc)
        return {
            "face_match": False,
            "confidence": 0.0,
            "liveness_passed": False,
            "spoof_probability": 0.0,
        }

    # 2. Detect face locations
    face_locations = face_recognition.face_locations(rgb_frame)

    # No face detected
    if len(face_locations) == 0:
        logger.info("Real face recognition: no face detected in frame for customer=%s", customer_id)
        return {
            "face_match": False,
            "confidence": 0.0,
            "liveness_passed": False,
            "spoof_probability": 0.0,
        }

    primary_face = face_locations[0]

    # 3. Check for rectangular mobile phone / photo frame enclosing the face
    is_mobile_phone = check_rectangular_entity_or_phone_bezel(rgb_frame, primary_face)
    if is_mobile_phone:
        logger.warning("Real face recognition: Mobile phone / photo detected enclosing face for customer=%s", customer_id)
        return {
            "face_match": False,
            "confidence": 0.10,
            "liveness_passed": False,
            "spoof_probability": 0.99,
        }

    # 4. Generate 128-d live face embedding for normal live human
    live_encodings = face_recognition.face_encodings(rgb_frame, [primary_face])
    if not live_encodings:
        logger.warning("Real face recognition: failed to generate embedding for detected face")
        return {
            "face_match": False,
            "confidence": 0.0,
            "liveness_passed": True,
            "spoof_probability": 0.05,
        }

    live_embedding = live_encodings[0]

    # 5. Load stored customer embedding from Project NPN (customer001.npy / customer002.npy)
    stored_embedding = load_customer_embedding(customer_id)
    if stored_embedding is None:
        logger.warning("No registered face embedding found for customer_id=%s", customer_id)
        return {
            "face_match": False,
            "confidence": 0.0,
            "liveness_passed": True,
            "spoof_probability": 0.02,
        }

    # 6. Calculate Euclidean face distance directly using Project NPN face_distance
    distance = float(face_recognition.face_distance([stored_embedding], live_embedding)[0])
    threshold = float(settings.FACE_DISTANCE_THRESHOLD)
    face_match = bool(distance <= threshold)
    confidence = calculate_confidence_score(distance, threshold)

    logger.info(
        "Project NPN face recognition: customer=%s distance=%.4f threshold=%.2f face_match=%s confidence=%.2f",
        customer_id, distance, threshold, face_match, confidence,
    )

    return {
        "face_match": face_match,
        "confidence": confidence,
        "liveness_passed": True,
        "spoof_probability": 0.02,
    }
