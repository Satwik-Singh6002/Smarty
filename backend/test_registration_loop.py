import asyncio
import os
from authenticator import FaceAuthenticator

async def main():
    ref_path = "reference.jpg"
    
    # Ensure reference.jpg doesn't exist for test
    if os.path.exists(ref_path):
        try:
            os.remove(ref_path)
        except Exception:
            pass
        
    print("Initializing FaceAuthenticator...")
    auth = FaceAuthenticator(reference_image_path=ref_path)
    
    print("Calling start_registration_loop()...")
    try:
        success = auth.start_registration_loop()
        print("Success:", success)
        
        # Let it run for 2 seconds to see if thread starts
        await asyncio.sleep(2)
        print("Stopping authenticator...")
        auth.stop()
    except Exception as e:
        print("Exception caught:", e)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
