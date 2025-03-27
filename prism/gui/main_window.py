from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QPushButton, QLabel, QComboBox, QCheckBox, QSplitter,
    QListWidget, QListWidgetItem, QScrollArea, QStatusBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QImage, QFont, QIcon
import time
import logging

from .webcam_widget import WebcamWidget
from ..utils.gemini_client import GeminiClient
from ..utils.tts_engine import TTSEngine
from ..utils.speech_recognition_engine import SpeechRecognitionEngine

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Prism AI Assistant")
        self.resize(1200, 800)
        
        # Initialize components with error handling
        try:
            logging.info("Initializing GeminiClient")
            self.gemini_client = GeminiClient()
        except Exception as e:
            logging.error(f"Failed to initialize GeminiClient: {e}")
            self.gemini_client = None
            
        try:
            logging.info("Initializing TTSEngine")
            self.tts_engine = TTSEngine()
        except Exception as e:
            logging.error(f"Failed to initialize TTSEngine: {e}")
            self.tts_engine = None
            
        try:
            logging.info("Initializing SpeechRecognitionEngine")
            self.speech_recognition = SpeechRecognitionEngine()
        except Exception as e:
            logging.error(f"Failed to initialize SpeechRecognitionEngine: {e}")
            self.speech_recognition = None
        
        # Set auto-interrupt detection if both components are available
        if self.tts_engine and self.speech_recognition:
            try:
                logging.info("Setting up auto-interrupt detector")
                self.tts_engine.set_auto_interrupt_detector(self.detect_voice_interrupt)
            except Exception as e:
                logging.error(f"Failed to set up auto-interrupt detector: {e}")
        
        try:
            # Set up the main UI
            logging.info("Initializing UI")
            self.init_ui()
            
            # Set up status bar
            self.status_bar = QStatusBar()
            self.setStatusBar(self.status_bar)
            self.status_bar.showMessage("Ready")
            
            # Connect signals after UI is fully set up
            self.connect_signals()
            
            # Start continuous listening by default if speech recognition is available
            if self.speech_recognition:
                logging.info("Starting continuous listening")
                self.continuous_listening_toggle.setChecked(True)
                self.voice_input_button.setChecked(True)
                self.toggle_voice_input(True)
        except Exception as e:
            logging.error(f"Error in UI initialization: {e}")
    
    def init_ui(self):
        # Create central widget and main layout
        central_widget = QWidget()
        main_layout = QHBoxLayout(central_widget)
        
        # Left panel (camera & controls)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # Webcam widget with error handling
        try:
            logging.info("Creating WebcamWidget")
            self.webcam_widget = WebcamWidget()
            self.webcam_widget.setFixedSize(480, 360)
        except Exception as e:
            logging.error(f"Failed to create WebcamWidget: {e}")
            # Create a placeholder instead
            self.webcam_widget = QLabel("Webcam not available")
            self.webcam_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.webcam_widget.setFixedSize(480, 360)
            self.webcam_widget.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc;")
        
        # Camera controls
        camera_controls = QWidget()
        camera_layout = QHBoxLayout(camera_controls)
        
        self.webcam_toggle = QCheckBox("Enable Camera")
        self.webcam_toggle.setChecked(False)
        
        camera_layout.addWidget(self.webcam_toggle)
        camera_layout.addStretch()
        
        # Voice selection - create container widget
        voice_container = QWidget()
        voice_layout = QHBoxLayout(voice_container)
        voice_label = QLabel("Voice:")
        self.voice_selector = QComboBox()
        
        # Add voices from EdgeTTS if available
        if self.tts_engine:
            try:
                voices = self.tts_engine.get_available_voices()
                for voice in voices:
                    self.voice_selector.addItem(voice)
            except Exception as e:
                logging.error(f"Failed to get voices: {e}")
                self.voice_selector.addItem("Default Voice")
        else:
            self.voice_selector.addItem("TTS Not Available")
        
        voice_layout.addWidget(voice_label)
        voice_layout.addWidget(self.voice_selector)
        
        # Voice input controls - create container widget
        voice_input_container = QWidget()
        voice_input_layout = QHBoxLayout(voice_input_container)
        
        self.voice_input_button = QPushButton("Voice Input")
        self.voice_input_button.setCheckable(True)
        
        self.continuous_listening_toggle = QCheckBox("Continuous Listening")
        
        voice_input_layout.addWidget(self.voice_input_button)
        voice_input_layout.addWidget(self.continuous_listening_toggle)
        
        # Add components to left panel
        left_layout.addWidget(self.webcam_widget)
        left_layout.addWidget(camera_controls)
        left_layout.addWidget(voice_container)
        left_layout.addWidget(voice_input_container)
        left_layout.addStretch()
        
        # Right panel (chat)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Chat history
        self.chat_history = QListWidget()
        self.chat_history.setWordWrap(True)
        self.chat_history.setSpacing(10)
        
        # Input area
        input_widget = QWidget()
        input_layout = QHBoxLayout(input_widget)
        
        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText("Type your message here...")
        self.input_text.setMaximumHeight(100)
        
        self.send_button = QPushButton("Send")
        self.send_button.setFixedSize(80, 100)
        
        input_layout.addWidget(self.input_text)
        input_layout.addWidget(self.send_button)
        
        # Add components to right panel
        right_layout.addWidget(self.chat_history)
        right_layout.addWidget(input_widget)
        
        # Add panels to main layout with splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([400, 800])
        
        main_layout.addWidget(splitter)
        
        # Set central widget
        self.setCentralWidget(central_widget)
    
    def connect_signals(self):
        """Connect UI signals to slots with error handling"""
        try:
            logging.info("Connecting UI signals")
            
            # Connect buttons to actions
            if self.send_button:
                self.send_button.clicked.connect(self.send_message)
                
            if self.webcam_toggle and hasattr(self.webcam_widget, 'start_webcam'):
                self.webcam_toggle.toggled.connect(self.toggle_webcam)
                
            if self.voice_selector and self.tts_engine:
                self.voice_selector.currentTextChanged.connect(self.change_voice)
                
            # Voice input signals
            if self.voice_input_button and self.speech_recognition:
                self.voice_input_button.toggled.connect(self.toggle_voice_input)
                self.speech_recognition.speech_recognized.connect(self.on_speech_recognized)
                self.speech_recognition.status_changed.connect(self.update_status)
                
            # For TTS events
            if self.tts_engine:
                self.tts_engine.speech_started.connect(self.on_speech_started)
                self.tts_engine.speech_ended.connect(self.on_speech_ended)
                
                # Pause speech recognition during TTS playback to avoid feedback loops
                if self.speech_recognition:
                    self.tts_engine.speech_started.connect(self.pause_speech_recognition)
                    self.tts_engine.speech_ended.connect(self.resume_speech_recognition)
                    
        except Exception as e:
            logging.error(f"Error connecting signals: {e}")
            if self.status_bar:
                self.status_bar.showMessage(f"Error initializing some components. See log for details.")
    
    def detect_voice_interrupt(self):
        """Function used to detect when user is speaking to interrupt the assistant"""
        # If speech recognition is active and detects voice above threshold,
        # we consider it an interruption
        if not hasattr(self, 'speech_recognition') or not self.speech_recognition:
            return False
            
        try:
            # Check if the speech recognition engine is currently hearing something
            # We use the energy level from the recognizer
            if hasattr(self.speech_recognition, 'recognizer') and self.speech_recognition.recognizer:
                # If we recently stopped TTS, don't trigger interruption immediately
                # This gives time for the TTS end detection to complete
                current_time = time.time()
                if hasattr(self.speech_recognition, 'last_tts_end_time'):
                    if current_time - self.speech_recognition.last_tts_end_time < 1.0:
                        return False
                
                # If the voice input is active and we detect audio
                if (self.voice_input_button.isChecked() and
                        hasattr(self.speech_recognition, 'is_hearing_audio') and
                        self.speech_recognition.is_hearing_audio):
                    return True
        except Exception as e:
            logging.error(f"Error in voice interrupt detection: {e}")
                
        return False
    
    def toggle_webcam(self, enabled):
        """Toggle webcam on/off with error handling"""
        if not hasattr(self, 'webcam_widget') or not hasattr(self.webcam_widget, 'start_webcam'):
            logging.error("Cannot toggle webcam - webcam widget not properly initialized")
            return
            
        try:
            if enabled:
                self.webcam_widget.start_webcam()
            else:
                self.webcam_widget.stop_webcam()
        except Exception as e:
            logging.error(f"Error toggling webcam: {e}")
            if self.status_bar:
                self.status_bar.showMessage(f"Error toggling webcam: {e}")
    
    def change_voice(self, voice):
        """Change TTS voice with error handling"""
        if not hasattr(self, 'tts_engine') or not self.tts_engine:
            logging.error("Cannot change voice - TTS engine not initialized")
            return
            
        try:
            self.tts_engine.set_voice(voice)
        except Exception as e:
            logging.error(f"Error changing voice: {e}")
    
    def toggle_voice_input(self, enabled):
        """Toggle voice input with error handling"""
        if not hasattr(self, 'speech_recognition') or not self.speech_recognition:
            logging.error("Cannot toggle voice input - speech recognition not initialized")
            if self.status_bar:
                self.status_bar.showMessage("Voice input not available")
            return
            
        try:
            if enabled:
                # Start voice recognition
                continuous = self.continuous_listening_toggle.isChecked()
                self.speech_recognition.start_listening(continuous=continuous)
                self.voice_input_button.setText("Voice Input ON")
                self.voice_input_button.setStyleSheet("background-color: #8cf1b4;")
            else:
                # Stop voice recognition
                self.speech_recognition.stop_listening()
                self.voice_input_button.setText("Voice Input OFF")
                self.voice_input_button.setStyleSheet("")
        except Exception as e:
            logging.error(f"Error toggling voice input: {e}")
            if self.status_bar:
                self.status_bar.showMessage(f"Error with voice input: {e}")
    
    def on_speech_recognized(self, text):
        """Handle recognized speech with error handling"""
        try:
            if text:
                # Set the text in the input field
                self.input_text.setText(text)
                
                # If in continuous mode, automatically send the message
                if self.continuous_listening_toggle.isChecked():
                    self.send_message()
        except Exception as e:
            logging.error(f"Error handling recognized speech: {e}")
    
    def update_status(self, status_message):
        """Update status bar with recognition status"""
        try:
            if status_message == "Listening...":
                # Don't show "Listening..." messages to keep the UI clean
                return
                
            if hasattr(self, 'status_bar') and self.status_bar:
                self.status_bar.showMessage(status_message)
        except Exception as e:
            logging.error(f"Error updating status: {e}")
    
    def on_speech_started(self):
        """When speech starts"""
        pass
    
    def on_speech_ended(self):
        """When speech ends"""
        pass
    
    def send_message(self):
        """Send a message to the AI with error handling"""
        try:
            # Get user input
            user_text = self.input_text.toPlainText().strip()
            if not user_text:
                return
            
            # Clear input field
            self.input_text.clear()
            
            # Add user message to chat
            self.add_message_to_chat("You", user_text)
            
            # Check if Gemini client is available
            if not hasattr(self, 'gemini_client') or not self.gemini_client:
                error_msg = "AI service is not available"
                logging.error(error_msg)
                self.add_message_to_chat("Prism", f"Error: {error_msg}")
                return
            
            # Get webcam image if enabled
            image = None
            if hasattr(self, 'webcam_toggle') and self.webcam_toggle.isChecked():
                if hasattr(self.webcam_widget, 'get_current_frame'):
                    image = self.webcam_widget.get_current_frame()
            
            # Process with Gemini (in a separate thread)
            self.process_thread = ResponseThread(
                self.gemini_client,
                user_text,
                image
            )
            self.process_thread.response_ready.connect(self.handle_response)
            self.process_thread.start()
        except Exception as e:
            error_msg = f"Error sending message: {e}"
            logging.error(error_msg)
            self.add_message_to_chat("Prism", f"Error: {error_msg}")
    
    def handle_response(self, response):
        """Handle AI response with error handling"""
        try:
            # Add AI response to chat
            self.add_message_to_chat("Prism", response)
            
            # Speak the response if TTS is available
            if hasattr(self, 'tts_engine') and self.tts_engine:
                self.tts_engine.speak(response)
        except Exception as e:
            logging.error(f"Error handling response: {e}")
            
    def add_message_to_chat(self, sender, message):
        """Add a message to the chat history with error handling"""
        try:
            # Print to console for clean display
            print(f"{sender}: {message}", flush=True)
            
            item = QListWidgetItem()
            
            # Create message widget
            message_widget = QWidget()
            message_layout = QVBoxLayout(message_widget)
            
            # Sender label with appropriate styling
            sender_label = QLabel(f"{sender}:")
            font = QFont()
            font.setBold(True)
            sender_label.setFont(font)
            
            if sender == "You":
                sender_label.setStyleSheet("color: #1e88e5;")  # Blue for user
            else:
                sender_label.setStyleSheet("color: #7cb342;")  # Green for Prism
            
            # Message label
            message_label = QLabel(message)
            message_label.setWordWrap(True)
            message_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            
            message_layout.addWidget(sender_label)
            message_layout.addWidget(message_label)
            message_layout.addStretch()
            
            # Set the custom widget for the item
            item.setSizeHint(message_widget.sizeHint())
            self.chat_history.addItem(item)
            self.chat_history.setItemWidget(item, message_widget)
            
            # Scroll to the bottom
            self.chat_history.scrollToBottom()
        except Exception as e:
            logging.error(f"Error adding message to chat: {e}")
    
    def pause_speech_recognition(self):
        """Pause speech recognition during TTS output to avoid feedback loops"""
        if not hasattr(self, 'speech_recognition') or not self.speech_recognition:
            return
            
        try:
            # Store the current state to restore it later
            self.was_listening = False
            
            # Check if we're currently listening
            if self.speech_recognition.is_listening:
                self.was_listening = True
                # Temporarily pause without changing button state
                self.speech_recognition.stop_listening()
        except Exception as e:
            logging.error(f"Error pausing speech recognition: {e}")
    
    def resume_speech_recognition(self):
        """Resume speech recognition if it was active before TTS started"""
        if not hasattr(self, 'speech_recognition') or not self.speech_recognition:
            return
            
        try:
            # Only resume if we were listening before
            if hasattr(self, 'was_listening') and self.was_listening:
                # Update the last TTS time in the speech recognition engine
                self.speech_recognition.set_last_tts_time()
                    
                # If the button is still in "on" state, restart listening
                if hasattr(self, 'voice_input_button') and self.voice_input_button.isChecked():
                    # Add a small delay before resuming to prevent feedback
                    time.sleep(0.5)
                    continuous = self.continuous_listening_toggle.isChecked()
                    self.speech_recognition.start_listening(continuous=continuous)
                
                # Reset the flag
                self.was_listening = False
        except Exception as e:
            logging.error(f"Error resuming speech recognition: {e}")
    
    def closeEvent(self, event):
        """Handle window close event to ensure proper cleanup"""
        logging.info("Window close event triggered, cleaning up resources")
        
        try:
            # Stop speech recognition if active
            if hasattr(self, 'speech_recognition') and self.speech_recognition:
                logging.info("Stopping speech recognition")
                self.speech_recognition.stop_listening()
            
            # Stop TTS playback if active
            if hasattr(self, 'tts_engine') and self.tts_engine:
                logging.info("Stopping TTS engine")
                self.tts_engine.stop()
            
            # Stop webcam if active
            if hasattr(self, 'webcam_widget') and hasattr(self.webcam_widget, 'stop_webcam'):
                logging.info("Stopping webcam")
                self.webcam_widget.stop_webcam()
                
            logging.info("All resources cleaned up")
        except Exception as e:
            logging.error(f"Error during cleanup: {e}")
        
        # Accept the close event
        event.accept()


class ResponseThread(QThread):
    response_ready = pyqtSignal(str)
    
    def __init__(self, gemini_client, message, image=None):
        super().__init__()
        self.gemini_client = gemini_client
        self.message = message
        self.image = image
    
    def run(self):
        # Process the request through Gemini
        response = self.gemini_client.generate_response(self.message, self.image)
        self.response_ready.emit(response) 