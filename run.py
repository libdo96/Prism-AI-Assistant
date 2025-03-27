#!/usr/bin/env python3
import sys
import os
import logging
from dotenv import load_dotenv
from PyQt6.QtWidgets import QApplication
from prism.gui.main_window import MainWindow

def setup_logging():
    """Set up logging configuration"""
    # Create logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/prism.log'),
            logging.FileHandler('logs/stdout.log'),
            logging.FileHandler('logs/stderr.log')
        ]
    )

def main():
    """Main entry point for the application"""
    # Load environment variables from .env file
    load_dotenv()
    
    # Set up logging
    setup_logging()
    
    # Check for API key
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("Error: GEMINI_API_KEY not found in environment variables")
        print("Please make sure you have created a .env file with your API key")
        print("Example: GEMINI_API_KEY=your_api_key_here")
        return
    
    # Create the application
    app = QApplication(sys.argv)
    
    # Create and show the main window
    window = MainWindow()
    window.show()
    
    # Run the application
    sys.exit(app.exec())

if __name__ == '__main__':
    main() 