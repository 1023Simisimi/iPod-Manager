"""
iPod Manager — launcher
Opens the browser automatically when the server starts.
"""
import threading
import webbrowser
import time
import sys
import os

# Make sure local packages are found
sys.path.insert(0, os.path.dirname(__file__))

def open_browser():
    time.sleep(2)
    webbrowser.open('http://localhost:5050')

threading.Thread(target=open_browser, daemon=True).start()

from app import app
app.run(port=5050, debug=False)
