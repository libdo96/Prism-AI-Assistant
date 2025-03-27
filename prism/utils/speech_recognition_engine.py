import speech_recognition as sr
import time
import logging
from PyQt6.QtCore import QObject, pyqtSignal
import numpy as np
import threading
import traceback

class SpeechRecognitionEngine(QObject):
    """Speech recognition engine for voice input capabilities"""
    
    # Signal for when speech is recognized
    speech_recognized = pyqtSignal(str)
    
    # Signal for speech recognition status
    status_changed = pyqtSignal(str)
    
    # Signal for interrupt detection
    interrupt_detected = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        
        # Initialize the recognizer
        self.recognizer = sr.Recognizer()
        
        # Flag to control listening
        self.is_listening = False
        
        # Flag to track if we're in continuous mode
        self.continuous_mode = False
        
        # Debounce timer to avoid processing too quickly after TTS
        self.last_tts_end_time = 0
        self.debounce_time = 0.1
        
        # For voice level detection
        self.is_hearing_audio = False
        
        # TTS interrupt detection
        self.is_tts_playing = False
        
        # Adjust recognition sensitivity - VERY sensitive settings
        self.recognizer.energy_threshold = 100  # Lower threshold for better sensitivity
        self.recognizer.dynamic_energy_threshold = False  # Turn OFF dynamic threshold
        self.recognizer.pause_threshold = 0.3  # Shorter pause threshold
        self.recognizer.phrase_threshold = 0.1  # More sensitive phrase detection
        self.recognizer.non_speaking_duration = 0.2  # Quicker end of phrase detection
        
        # Thread management
        self.listen_thread = None
        self.monitor_thread = None
        self.interrupt_thread = None
        
    def start_listening(self, continuous=False):
        """Start listening for voice input"""
        if self.is_listening:
            return
        
        self.continuous_mode = continuous
        self.is_listening = True
        
        # Start listening in a separate thread
        self.listen_thread = threading.Thread(target=self._listen_loop)
        self.listen_thread.daemon = True
        self.listen_thread.start()
        
        self.status_changed.emit("Listening...")
        logging.info("Started listening for voice input")
    
    def stop_listening(self):
        """Stop listening for voice input"""
        self.is_listening = False
        
        # Wait for threads to finish
        if hasattr(self, 'listen_thread') and self.listen_thread and self.listen_thread.is_alive():
            self.listen_thread.join(timeout=0.1)
        
        self.status_changed.emit("Not listening")
        logging.info("Stopped listening for voice input")
    
    def _listen_loop(self):
        """Main listening loop - simplified reliable approach"""
        while self.is_listening:
            # Apply debounce after TTS
            if time.time() - self.last_tts_end_time < self.debounce_time:
                time.sleep(0.02)
                continue
            
            try:
                self.status_changed.emit("Listening for command...")
                
                # Create a new microphone source each time for reliability
                with sr.Microphone() as source:
                    # Short adjustment for ambient noise
                    logging.info("Adjusting for ambient noise...")
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.2)
                    logging.info(f"Energy threshold set to: {self.recognizer.energy_threshold}")
                    
                    logging.info("Listening for speech...")
                    audio = self.recognizer.listen(source, timeout=None, phrase_time_limit=5.0)
                    logging.info("Speech detected, processing...")
                    
                    if not self.is_listening:
                        return
                    
                    self.status_changed.emit("Processing speech...")
                    
                    # Convert speech to text
                    text = self.recognizer.recognize_google(audio)
                    logging.info(f"Recognized text: {text}")
                    
                    if text:
                        self.last_tts_end_time = time.time()
                        self.speech_recognized.emit(text)
                        logging.info("Speech recognized and emitted")
                        
                        if not self.continuous_mode:
                            self.is_listening = False
                            self.status_changed.emit("Not listening")
                            return
            
            except sr.WaitTimeoutError:
                logging.info("No speech detected (timeout)")
            except sr.UnknownValueError:
                logging.info("Speech was not understood")
            except Exception as e:
                logging.error(f"Error in speech recognition: {e}")
                logging.error(traceback.format_exc())
                time.sleep(0.5)  # Wait a bit before retrying on error
    
    def _get_audio_energy(self, audio_data):
        """Calculate the energy level of an audio sample"""
        try:
            if audio_data and hasattr(audio_data, "get_raw_data"):
                raw_data = audio_data.get_raw_data()
                arr = np.frombuffer(raw_data, dtype=np.int16)
                if len(arr) > 0:
                    energy = np.sqrt(np.mean(np.square(arr.astype(np.float32))))
                    return energy
            return 0
        except Exception as e:
            logging.error(f"Error calculating audio energy: {e}")
            return 0
    
    def set_last_tts_time(self):
        """Update the last TTS end time for debouncing"""
        self.last_tts_end_time = time.time()
    
    def start_interrupt_detection(self):
        """Start monitoring for interruptions during TTS playback"""
        self.is_tts_playing = True
        
        # Start monitoring in a separate thread
        self.interrupt_thread = threading.Thread(target=self._monitor_interrupts)
        self.interrupt_thread.daemon = True
        self.interrupt_thread.start()
        
        logging.info("Started interrupt detection")
    
    def stop_interrupt_detection(self):
        """Stop monitoring for interruptions"""
        self.is_tts_playing = False
        logging.info("Stopped interrupt detection")
    
    def _monitor_interrupts(self):
        """Monitor for voice interruptions during TTS playback"""
        while self.is_tts_playing:
            try:
                # Use a short-lived microphone instance for instant sampling
                with sr.Microphone() as source:
                    # Very quick adjust for ambient noise (50ms)
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.05)
                    
                    try:
                        # Listen with a very short timeout for interruptions
                        audio = self.recognizer.listen(source, timeout=0.1, phrase_time_limit=0.1)
                        energy = self._get_audio_energy(audio)
                        
                        # Lower threshold for interruption detection
                        if energy > self.recognizer.energy_threshold * 0.4:
                            logging.info(f"Interrupt detected with energy: {energy}")
                            self.interrupt_detected.emit()
                            return
                    except sr.WaitTimeoutError:
                        pass
                    except Exception as e:
                        logging.debug(f"Minor error in interrupt monitoring: {e}")
            
            except Exception as e:
                logging.error(f"Error in interrupt detection: {e}")
            
            # Short sleep to reduce CPU usage
            time.sleep(0.05) 