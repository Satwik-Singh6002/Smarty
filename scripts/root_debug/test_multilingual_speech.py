import sys
import os
import time

# Ensure UTF-8 stdout on Windows
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Add backend to path
sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))

from system_tools import speak_text

print("Testing Smarty Multilingual Voice Routing...")
print("=" * 60)

test_cases = [
    ("English", "Hello, I am Smarty. How can I help you today?"),
    ("Hindi", "नमस्ते, मैं आपकी क्या सहायता कर सकता हूँ?"),
    ("Spanish", "Hola, soy Smarty. ¿En qué puedo ayudarte hoy?"),
    ("French", "Bonjour, je suis Smarty. Comment puis-je vous aider aujourd'hui?"),
    ("German", "Hallo, ich bin Smarty. Wie kann ich Ihnen heute helfen?"),
    ("Japanese", "こんにちは、私はスマーティです。本日はどのようなご用件でしょうか？"),
    ("Turkish", "Merhaba, ben Smarty. Bugün size nasıl yardımcı olabilirim?"),
    ("Russian", "Здравствуйте, я Смарти. Чем я могу помочь вам сегодня?"),
]

for lang, text in test_cases:
    print(f"\n[Testing {lang}] -> Text: {text}")
    result = speak_text(text, wait=True)
    print(f"  Result: {result}")
    time.sleep(1)

print("\n" + "=" * 60)
print("Multilingual voice routing test complete.")
