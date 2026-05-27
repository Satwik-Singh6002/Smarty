import cv2
import os
import sys
import asyncio

# Add backend dir to path to import authenticator
backend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
sys.path.append(backend_dir)
from authenticator import FaceAuthenticator

def main():
    print("==============================================")
    print("[CAMERA] Smarty Face Registration Utility")
    print("==============================================")
    print("Make sure A.D.A or any other camera app is closed before running this.")
    print("Press SPACE to capture your face photo.")
    print("Press ESC to cancel.")
    print("----------------------------------------------")

    # Initialize video capture
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        cap = cv2.VideoCapture(1)
    
    if not cap.isOpened():
        print("[ERROR] Could not open webcam. Make sure it is connected and not in use by another app.")
        input("Press Enter to exit...")
        return

    cv2.namedWindow("Smarty Face Registration", cv2.WINDOW_AUTOSIZE)

    captured = False
    frame_to_save = None

    while True:
        ret, frame = cap.read()
        if not ret:
            print("[ERROR] Failed to read from webcam.")
            break

        # Display instructions on screen
        display_frame = frame.copy()
        cv2.putText(display_frame, "Look here and press SPACE to capture", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(display_frame, "Press ESC to cancel", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2, cv2.LINE_AA)

        cv2.imshow("Smarty Face Registration", display_frame)

        key = cv2.waitKey(1) & 0xFF
        if key == 27: # ESC
            print("Registration cancelled.")
            break
        elif key == 32: # SPACE
            frame_to_save = frame
            captured = True
            break

    cap.release()
    cv2.destroyAllWindows()

    if captured and frame_to_save is not None:
        # backend_dir is already resolved at the top
        temp_path = os.path.join(backend_dir, "temp_reg.jpg")
        ref_path = os.path.join(backend_dir, "reference.jpg")

        # Save temporarily to run verification
        cv2.imwrite(temp_path, frame_to_save)
        print("Verifying face quality...")

        # Initialize authenticator temporarily to verify the face
        try:
            # Create a mock on_status_change callback
            async def mock_callback(status):
                pass
            
            auth = FaceAuthenticator(reference_image_path=temp_path, on_status_change=mock_callback)
            
            # Since reference_landmarks is set if a face is found
            if auth.reference_landmarks is not None:
                # Rename temp_reg.jpg to reference.jpg
                if os.path.exists(ref_path):
                    os.remove(ref_path)
                os.rename(temp_path, ref_path)
                print("[SUCCESS] Face registered successfully as reference.jpg!")
                
                # Enable face authentication in settings.json
                settings_path = os.path.join(backend_dir, "settings.json")
                if os.path.exists(settings_path):
                    import json
                    with open(settings_path, 'r') as f:
                        settings = json.load(f)
                    settings["face_auth_enabled"] = True
                    with open(settings_path, 'w') as f:
                        json.dump(settings, f, indent=4)
                    print("[OK] Face unlock has been enabled in settings.json.")
                else:
                    print("[WARN] settings.json not found in backend directory.")
            else:
                print("[ERROR] Face could not be detected clearly. Please try again in a well-lit area.")
                if os.path.exists(temp_path):
                    os.remove(temp_path)
        except Exception as e:
            print(f"[ERROR] Verification failed: {e}")
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
    print("\nRegistration process complete.")
    input("Press Enter to exit...")

if __name__ == "__main__":
    main()
