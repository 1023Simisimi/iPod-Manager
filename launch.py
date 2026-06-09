import threading
import webbrowser
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def open_browser():
    time.sleep(1.5)
    webbrowser.open_new('http://localhost:5050')

t = threading.Thread(target=open_browser, daemon=True)
t.start()

from app import app
app.run(port=5050, debug=False, use_reloader=False)
