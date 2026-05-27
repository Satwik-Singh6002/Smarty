"""
Wake Word Listener for Smarty
Listens for "Hey Smarty" wake word to activate the assistant.
Uses openwakeword for efficient, offline wake word detection.
"""
import asyncio
import os
import numpy as np
from typing import Optional, Callable

# Try to import audio libraries (pyaudio or sounddevice)
try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False
    print("[WakeWord] pyaudio not available, trying sounddevice...")

try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    SOUNDDEVICE_AVAILABLE = False
    print("[WakeWord] sounddevice not available")

# Try to import openwakeword, provide helpful error if not installed
try:
    from openwakeword.model import Model
    OPENWAKEWORD_AVAILABLE = True
except ImportError:
    OPENWAKEWORD_AVAILABLE = False
    print("[WakeWord] openwakeword not installed. Run: pip install openwakeword")


# Audio configuration
FORMAT = pyaudio.paInt16
CHANNELS = 1
SAMPLE_RATE = 16000
CHUNK_SIZE = 1280  # 80ms chunks for openwakeword


class WakeWordListener:
    """
    Listens for "Hey Smarty" wake word and triggers a callback when detected.
    """
    
    def __init__(
        self,
        on_wake_word: Optional[Callable[[], None]] = None,
        threshold: float = 0.5,
        input_device_index: Optional[int] = None
    ):
        """
        Initialize the wake word listener.
        
        Args:
            on_wake_word: Callback function called when wake word is detected
            threshold: Detection threshold (0-1), higher = more strict
            input_device_index: Microphone device index (None for default)
        """
        self.on_wake_word = on_wake_word
        self.threshold = threshold
        self.input_device_index = input_device_index
        
        self.running = False
        self.paused = False
        self._audio = None
        self._stream = None
        self._model = None
        
        # Cooldown to prevent multiple triggers
        self._last_detection_time = 0
        self._cooldown_seconds = 3.0
        
        print(f"[WakeWord] Initialized with threshold={threshold}")
    
    def _init_model(self):
        """Initialize the wake word model."""
        if not OPENWAKEWORD_AVAILABLE:
            raise RuntimeError("openwakeword is not installed")
        
        # openwakeword comes with pre-trained models
        # We'll use a custom approach: detect "hey" followed by any word
        # For best results, you can train a custom model for "Hey Smarty"
        
        # Using the built-in models that are closest
        self._model = Model(
            wakeword_models=["hey_smarty"],  # Use hey_smarty as base (similar pattern)
            inference_framework="onnx"
        )
        print("[WakeWord] Model loaded successfully")
    
    async def start(self):
        """Start listening for the wake word."""
        if self.running:
            print("[WakeWord] Already running")
            return
        
        if not OPENWAKEWORD_AVAILABLE:
            print("[WakeWord] Cannot start - openwakeword not installed")
            return
        
        try:
            # Initialize model
            self._init_model()
            
            # Initialize audio
            self._audio = pyaudio.PyAudio()
            
            # Get device info
            if self.input_device_index is None:
                device_info = self._audio.get_default_input_device_info()
                self.input_device_index = device_info['index']
            
            self._stream = self._audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=SAMPLE_RATE,
                input=True,
                input_device_index=self.input_device_index,
                frames_per_buffer=CHUNK_SIZE
            )
            
            self.running = True
            print("[WakeWord] Listening for 'Hey Smarty'...")
            
            # Start listening loop
            await self._listen_loop()
            
        except Exception as e:
            print(f"[WakeWord] Error starting: {e}")
            self.stop()
    
    async def _listen_loop(self):
        """Main listening loop."""
        import time
        
        while self.running:
            if self.paused:
                await asyncio.sleep(0.1)
                continue
            
            try:
                # Read audio chunk
                audio_data = await asyncio.to_thread(
                    self._stream.read, CHUNK_SIZE, exception_on_overflow=False
                )
                
                # Convert to numpy array
                audio_array = np.frombuffer(audio_data, dtype=np.int16)
                
                # Run prediction
                prediction = self._model.predict(audio_array)
                
                # Check for wake word detection
                # The model returns scores for each wake word
                for model_name, score in prediction.items():
                    if score > self.threshold:
                        current_time = time.time()
                        
                        # Check cooldown
                        if current_time - self._last_detection_time > self._cooldown_seconds:
                            self._last_detection_time = current_time
                            print(f"[WakeWord] 🎤 Wake word detected! (score: {score:.2f})")
                            
                            # Trigger callback
                            if self.on_wake_word:
                                if asyncio.iscoroutinefunction(self.on_wake_word):
                                    await self.on_wake_word()
                                else:
                                    self.on_wake_word()
                
            except Exception as e:
                print(f"[WakeWord] Error in listen loop: {e}")
                await asyncio.sleep(0.1)
    
    def pause(self):
        """Pause listening (e.g., while Smarty is talking)."""
        self.paused = True
        print("[WakeWord] Paused")
    
    def resume(self):
        """Resume listening."""
        self.paused = False
        print("[WakeWord] Resumed")
    
    def stop(self):
        """Stop listening and clean up resources."""
        self.running = False
        
        if self._stream:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except:
                pass
            self._stream = None
        
        if self._audio:
            try:
                self._audio.terminate()
            except:
                pass
            self._audio = None
        
        print("[WakeWord] Stopped")


class SimpleWakeWordListener:
    """
    A simpler wake word listener using speech recognition.
    Falls back to this if openwakeword is not available.
    """
    
    def __init__(
        self,
        wake_phrase: str = "hey smarty",
        on_wake_word: Optional[Callable[[], None]] = None,
        input_device_index: Optional[int] = None
    ):
        self.wake_phrase = wake_phrase.lower()
        self.on_wake_word = on_wake_word
        self.input_device_index = input_device_index
        
        self.running = False
        self.paused = False
        self._audio = None
        self._stream = None
        
        # Cooldown
        self._last_detection_time = 0
        self._cooldown_seconds = 2.0
        
        # Try to import speech recognition
        try:
            import speech_recognition as sr
            self._recognizer = sr.Recognizer()
            self._sr_available = True
        except ImportError:
            self._sr_available = False
            print("[WakeWord] speech_recognition not available")
        
        print(f"[WakeWord] Simple listener initialized for '{wake_phrase}'")
    
    async def start(self):
        """Start listening."""
        if not self._sr_available:
            print("[WakeWord] Cannot start - speech_recognition not installed")
            print("[WakeWord] Run: pip install SpeechRecognition")
            return
        
        import speech_recognition as sr
        
        self.running = True
        print(f"[WakeWord] Listening for '{self.wake_phrase}'...")
        
        mic = sr.Microphone(device_index=self.input_device_index)
        
        with mic as source:
            self._recognizer.adjust_for_ambient_noise(source, duration=1)
        
        # Use background listening
        import time
        
        while self.running:
            if self.paused:
                await asyncio.sleep(0.1)
                continue
            
            try:
                with mic as source:
                    # Listen for a short phrase
                    audio = await asyncio.to_thread(
                        self._recognizer.listen,
                        source,
                        timeout=2,
                        phrase_time_limit=3
                    )
                
                # Try to recognize
                try:
                    text = await asyncio.to_thread(
                        self._recognizer.recognize_google,
                        audio
                    )
                    text = text.lower()
                    
                    # Check for wake phrase
                    if self.wake_phrase in text or "smarty" in text:
                        current_time = time.time()
                        
                        if current_time - self._last_detection_time > self._cooldown_seconds:
                            self._last_detection_time = current_time
                            print(f"[WakeWord] 🎤 Wake word detected! Heard: '{text}'")
                            
                            if self.on_wake_word:
                                if asyncio.iscoroutinefunction(self.on_wake_word):
                                    await self.on_wake_word()
                                else:
                                    self.on_wake_word()
                                    
                except sr.UnknownValueError:
                    pass  # Couldn't understand audio
                except sr.RequestError as e:
                    print(f"[WakeWord] Recognition error: {e}")
                    
            except Exception as e:
                if "timed out" not in str(e).lower():
                    print(f"[WakeWord] Error: {e}")
                await asyncio.sleep(0.1)
    
    def pause(self):
        self.paused = True
    
    def resume(self):
        self.paused = False
    
    def stop(self):
        self.running = False
        print("[WakeWord] Stopped")


def get_wake_word_listener(
    on_wake_word: Optional[Callable[[], None]] = None,
    threshold: float = 0.5,
    input_device_index: Optional[int] = None
):
    """
    Get the appropriate wake word listener based on available libraries.
    """
    if OPENWAKEWORD_AVAILABLE:
        return WakeWordListener(
            on_wake_word=on_wake_word,
            threshold=threshold,
            input_device_index=input_device_index
        )
    else:
        return SimpleWakeWordListener(
            wake_phrase="hey smarty",
            on_wake_word=on_wake_word,
            input_device_index=input_device_index
        )


# Test
if __name__ == "__main__":
    async def on_detected():
        print("🎉 WAKE WORD DETECTED!")
    
    async def main():
        listener = get_wake_word_listener(on_wake_word=on_detected)
        await listener.start()
    
    asyncio.run(main())
