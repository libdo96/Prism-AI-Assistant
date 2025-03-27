#!/usr/bin/env python3
import sys
import os
import logging
import traceback
from dotenv import load_dotenv
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget, QPushButton, QTextEdit
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

# Simple main window as a fallback
class BasicMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Prism AI Assistant (Basic Mode)")
        self.resize(800, 600)
        
        # Create central widget with basic layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Add header
        header = QLabel("Prism AI Assistant - Basic Mode")
        header.setStyleSheet("font-size: 18pt; font-weight: bold; margin-bottom: 20px;")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)
        
        # Add description
        description = QLabel("The full application couldn't start properly. This is a simplified version for troubleshooting.")
        description.setWordWrap(True)
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(description)
        
        # Add input field
        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText("Type your query here...")
        self.input_text.setMaximumHeight(100)
        layout.addWidget(self.input_text)
        
        # Add button
        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.on_send)
        layout.addWidget(self.send_button)
        
        # Add response area
        self.response_area = QLabel("Response will appear here")
        self.response_area.setStyleSheet("background-color: #f0f0f0; padding: 10px; min-height: 200px;")
        self.response_area.setWordWrap(True)
        self.response_area.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.response_area)
        
        # Add error info
        error_info = QLabel("Please check the logs for details on why the main application failed to start")
        error_info.setStyleSheet("color: red;")
        error_info.setWordWrap(True)
        layout.addWidget(error_info)
        
        # Add restart button
        restart_button = QPushButton("Try Restart Full Application")
        restart_button.clicked.connect(self.try_restart)
        layout.addWidget(restart_button)
    
    def on_send(self):
        text = self.input_text.toPlainText().strip()
        if text:
            self.response_area.setText(f"You sent: {text}\n\nThis is a basic mode. The full AI response system is not available.")
            self.input_text.clear()
    
    def try_restart(self):
        self.response_area.setText("Attempting to restart full application.\nCheck console for results.")
        try:
            # Try to import the real MainWindow
            from prism.gui.main_window import MainWindow
            self.hide()
            self.full_window = MainWindow()
            self.full_window.show()
            self.response_area.setText("Success! Full application should be visible now.")
        except Exception as e:
            self.response_area.setText(f"Failed to restart: {str(e)}")
            logging.error(f"Failed to restart full app: {e}", exc_info=True)

def main():
    """Main application entry point"""
    try:
        # Load environment variables
        load_dotenv()
        
        # Check if API key is set
        if not os.getenv("GEMINI_API_KEY"):
            logging.error("GEMINI_API_KEY not found in environment variables.")
            print("Error: GEMINI_API_KEY not found in environment variables.")
            print("Please create a .env file with your API key or set it in your environment.")
            return 1
        
        logging.info("Initializing application")
        
        # Start the application
        app = QApplication(sys.argv)
        app.setApplicationName("Prism AI Assistant")
        
        # First try the basic window to ensure something displays
        logging.info("Starting with basic window first")
        main_window = BasicMainWindow()
        main_window.show()
        
        # Add a reference to keep it from being garbage collected
        app.main_window = main_window
        
        logging.info("Entering application main loop")
        return app.exec()
    
    except Exception as e:
        logging.error(f"Fatal error in main: {e}", exc_info=True)
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 