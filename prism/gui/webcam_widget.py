import cv2
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
import numpy as np

class WebcamWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Initialize webcam variables
        self.cap = None
        self.camera_id = 0
        self.frame = None
        
        # Create layout
        layout = QVBoxLayout(self)
        
        # Create image label
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setText("Camera Off")
        
        # Add to layout
        layout.addWidget(self.image_label)
        
        # Create timer for updating webcam feed
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
    
    def start_webcam(self):
        """Start listening for voice input"""
        if self.cap is None:
            self.cap = cv2.VideoCapture(self.camera_id)
            
            if not self.cap.isOpened():
                self.image_label.setText("Error: Could not open webcam")
                self.cap = None
                return False
            
            # Start the timer
            self.timer.start(30)  # Update every 30ms (approx. 33 fps)
            return True
        return False
    
    def stop_webcam(self):
        """Stop the timer and release the webcam"""
        self.timer.stop()
        
        if self.cap is not None:
            self.cap.release()
            self.cap = None
            self.image_label.setText("Camera Off")
            self.frame = None
    
    def update_frame(self):
        """Background thread for continuous listening"""
        # Check if webcam is opened
        if self.cap is None or not self.cap.isOpened():
            return
        
        # Read a frame
        ret, frame = self.cap.read()
        
        if not ret:
            self.image_label.setText("Error: Could not read frame")
            return
        
        # Store the current frame
        self.frame = frame
        
        # Convert to RGB (from BGR)
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Convert to QImage
        h, w, ch = frame_rgb.shape
        bytes_per_line = ch * w
        qt_image = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        
        # Resize maintaining aspect ratio
        scaled_pixmap = QPixmap.fromImage(qt_image).scaled(
            self.image_label.width(), 
            self.image_label.height(),
            Qt.AspectRatioMode.KeepAspectRatio
        )
        
        # Display the image
        self.image_label.setPixmap(scaled_pixmap)
    
    def get_current_frame(self):
        """Returns the current frame in RGB format (now returning numpy array directly)"""
        if self.frame is None:
            return None
        
        try:
            # Convert OpenCV BGR to RGB color format
            rgb_frame = cv2.cvtColor(self.frame, cv2.COLOR_BGR2RGB)
            return rgb_frame
        except Exception as e:
            print(f"Error converting frame to RGB: {e}")
            return None 