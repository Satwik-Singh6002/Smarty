import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))

from system_tools import speak_text

print("🤖 Testing Smarty Voice (Edge TTS - en-GB-RyanNeural)...")
print("=" * 50)

# Classic Smarty lines
test_lines = [
    "Good evening, Sir. All systems are online and functioning normally.",
    "I've run a complete diagnostic. Everything appears to be in order.",
    "Shall I prepare the project, Sir?",
]

for i, line in enumerate(test_lines, 1):
    print(f"\n[Test {i}] {line}")
    result = speak_text(line)
    print(f"  Result: {result}")
    
    # Wait for playback to finish before next line
    import time
    time.sleep(5)

print("\n" + "=" * 50)
print("✅ Smarty voice test complete.")
