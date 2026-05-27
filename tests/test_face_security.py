import pytest
import os
import numpy as np
import cv2
import mediapipe as mp
from authenticator import FaceAuthenticator

def test_face_security_matching():
    """Verify that similar/translated faces match and different faces are rejected."""
    backend_dir = os.path.dirname(os.path.dirname(__file__))
    ref_path = os.path.join(backend_dir, "backend", "reference.jpg")
    obama_path = os.path.join(backend_dir, "obama.jpg")
    
    if not os.path.exists(ref_path):
        pytest.skip("No reference.jpg found in backend directory to test security.")
    if not os.path.exists(obama_path):
        pytest.skip("No obama.jpg found to test different face rejection.")
        
    auth = FaceAuthenticator(reference_image_path=ref_path)
    
    # Extract reference landmarks
    ref_img_bgr = cv2.imread(ref_path)
    ref_img_rgb = cv2.cvtColor(ref_img_bgr, cv2.COLOR_BGR2RGB)
    ref_landmarks = auth._extract_landmarks(ref_img_rgb)
    
    assert ref_landmarks is not None, "Failed to extract landmarks from reference.jpg"
    
    # Extract Obama landmarks
    obama_img_bgr = cv2.imread(obama_path)
    obama_img_rgb = cv2.cvtColor(obama_img_bgr, cv2.COLOR_BGR2RGB)
    obama_landmarks = auth._extract_landmarks(obama_img_rgb)
    
    assert obama_landmarks is not None, "Failed to extract landmarks from obama.jpg"
    
    # Test 1: Self match
    assert auth._compare_landmarks(ref_landmarks, ref_landmarks) == True, "Self should match"
    
    # Test 2: Obama rejection (different person)
    # Cosine similarity should be below 0.98 (threshold=0.02)
    assert auth._compare_landmarks(ref_landmarks, obama_landmarks) == False, "Obama should be rejected"
    
    # Calculate exact similarity
    l1 = ref_landmarks.flatten()
    l2 = obama_landmarks.flatten()
    sim = np.dot(l1, l2) / (np.linalg.norm(l1) * np.linalg.norm(l2))
    print(f"\nLegitimate owner similarity: {np.dot(l1, l1)/(np.linalg.norm(l1)*np.linalg.norm(l1)):.6f}")
    print(f"Different person similarity (Obama): {sim:.6f}")
    
    # Verify that a translated version of the owner's landmarks still matches perfectly (translation invariance)
    # Re-extract coordinates and translate
    landmarks_list = []
    # reconstruct from flattened array of normalized coordinates
    coords = ref_landmarks.reshape(-1, 3)
    # Apply translation offset in x, y
    translated_coords = coords + np.array([0.15, -0.07, 0.0], dtype=np.float32)
    
    # Center-normalize again should yield identical vectors
    mean = np.mean(translated_coords, axis=0)
    centered = translated_coords - mean
    scale = np.std(centered)
    translated_ref_landmarks = (centered / scale).flatten()
    
    assert auth._compare_landmarks(ref_landmarks, translated_ref_landmarks) == True, "Translated owner should match"
