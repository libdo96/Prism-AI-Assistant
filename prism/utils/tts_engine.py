import asyncio
import edge_tts
import tempfile
import os
import threading
import re
import logging
import time
from PyQt6.QtCore import QUrl, pyqtSignal, QObject
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
import pyttsx3
import traceback

class TTSEngine(QObject):
    """Text-to-speech engine using edge-tts and Qt"""
    
    # Signal when playback finishes
    playback_finished = pyqtSignal()
    
    # Signal when playback starts
    playback_started = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        
        # Initialize Qt media player
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(1.0)
        
        # Connect signals
        self.player.mediaStatusChanged.connect(self._on_media_status_changed)
        
        # Temporary file for TTS audio
        self.temp_file = None
        
        # Current state
        self.is_speaking = False
        
        # Default voice
        self.voice = "en-US-SteffanNeural"
        
        # Store voices 
        self.voices = self._get_voice_list()
        
        # For auto-interruption system
        self.interrupt_detector = None
    
    def _get_voice_list(self):
        """Get a list of available voices"""
        # Run the async function to get voices
        return asyncio.run(self._async_get_voices())
    
    async def _async_get_voices(self):
        """Asynchronously get the list of available voices"""
        voices = []
        try:
            all_voices = await edge_tts.list_voices()
            # Get English voices only (for simplicity)
            en_voices = [v["Name"] for v in all_voices 
                         if v["Locale"].startswith("en")]
            voices = sorted(en_voices)
        except Exception as e:
            logging.error(f"Error getting voices: {e}")
            # Add some default voices as fallback
            voices = [
                "en-US-SteffanNeural",
                "en-US-JennyNeural",
                "en-US-GuyNeural",
                "en-GB-SoniaNeural",
                "en-GB-RyanNeural"
            ]
        return voices
    
    def get_available_voices(self):
        """Return the list of available voices"""
        return self.voices
    
    def set_voice(self, voice):
        """Change the voice"""
        self.voice = voice
    
    def set_auto_interrupt_detector(self, detector):
        """Set the function that will be polled to check for interruption"""
        self.interrupt_detector = detector
    
    def speak(self, text):
        """Speak the given text"""
        if not text:
            return
        
        # Clean text for speech
        clean_text = self._clean_text_for_speech(text)
        
        # Stop any current speech
        if self.is_speaking:
            self.stop_speaking()
        
        # Start speaking in a thread to not block UI
        self.is_speaking = True
        self.playback_started.emit()
        
        # Start in separate thread
        thread = threading.Thread(target=self._speak_in_thread, args=(clean_text,))
        thread.daemon = True
        thread.start()
        
        logging.info(f"TTS started for: {text[:50]}...")
    
    def stop_speaking(self):
        """Stop current TTS playback"""
        if self.is_speaking:
            self.is_speaking = False
            self.player.stop()
            self._cleanup_temp_file()
            self.playback_finished.emit()
            logging.info("TTS playback stopped by request")
    
    def _on_media_status_changed(self, status):
        """Handle media status changes"""
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.is_speaking = False
            self._cleanup_temp_file()
            self.playback_finished.emit()
            logging.info("TTS playback finished naturally")
    
    def _cleanup_temp_file(self):
        """Clean up temporary file"""
        if self.temp_file and os.path.exists(self.temp_file):
            try:
                os.remove(self.temp_file)
                self.temp_file = None
            except Exception as e:
                logging.error(f"Error cleaning up temp file: {e}")
                logging.error(traceback.format_exc())
    
    def _clean_text_for_speech(self, text):
        """Filter and clean text for speech output"""
        # Remove URLs
        text = re.sub(r'https?://\S+|www\.\S+', ' URL omitted ', text)
        
        # Replace special characters with spaces
        text = re.sub(r'[^\w\s.,?!-]', ' ', text)
        
        # Fix spacing
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Replace technical symbols
        replacements = {
            '+': ' plus ',
            '=': ' equals ',
            '*': ' times ',
            '/': ' divided by ',
            '<': ' less than ',
            '>': ' greater than ',
            '@': ' at ',
            '#': ' hashtag ',
            '$': ' dollar ',
            '%': ' percent ',
            '&': ' and ',
            '|': ' or ',
            '_': ' underscore ',
        }
        
        for char, replacement in replacements.items():
            text = text.replace(char, replacement)
        
        return text
    
    def _check_for_interruption(self):
        """Check if we should auto-interrupt based on detector"""
        if self.interrupt_detector and callable(self.interrupt_detector):
            try:
                if self.interrupt_detector():
                    logging.info("Voice interruption detected - stopping speech")
                    return True
            except Exception as e:
                logging.error(f"Error in interrupt detection: {e}")
        return False
    
    def _speak_in_thread(self, text):
        """Generate speech in a separate thread"""
        try:
            # Create a temporary file for the audio
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_file:
                temp_filename = temp_file.name
                self.temp_file = temp_filename
            
            # Generate speech using asyncio
            asyncio.run(self._generate_speech(text, temp_filename))
            
            # If stopped during generation, don't play
            if not self.is_speaking:
                if os.path.exists(temp_filename):
                    os.unlink(temp_filename)
                return
            
            # Play the generated speech
            logging.info(f"Playing speech from {temp_filename}")
            self.player.setSource(QUrl.fromLocalFile(temp_filename))
            self.player.play()
            
            # Start interruption detection thread
            if self.interrupt_detector:
                self._start_interrupt_detection()
            
        except Exception as e:
            logging.error(f"Error in TTS thread: {e}")
            logging.error(traceback.format_exc())
            self.is_speaking = False
            self.playback_finished.emit()
    
    def _start_interrupt_detection(self):
        """Start a thread to monitor for voice interruption"""
        def monitor_interruption():
            check_interval = 0.05  # Check every 50ms for faster response
            while self.is_speaking:
                if self._check_for_interruption():
                    logging.info("Voice interrupt detected - stopping speech")
                    self.stop_speaking()
                    break
                time.sleep(check_interval)
                
        interrupt_thread = threading.Thread(target=monitor_interruption)
        interrupt_thread.daemon = True
        interrupt_thread.start()
    
    async def _generate_speech(self, text, output_file):
        """Generate speech asynchronously"""
        try:
            logging.info(f"Generating speech with voice {self.voice} for text: {text[:50]}...")
            communicate = edge_tts.Communicate(text, self.voice)
            await communicate.save(output_file)
            logging.info(f"Speech successfully generated to {output_file}")
        except Exception as e:
            logging.error(f"Error generating speech: {e}")
            logging.error(traceback.format_exc()) 