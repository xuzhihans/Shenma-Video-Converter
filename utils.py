import sys
import os

def get_base_path():
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return base_path

def get_ffmpeg_path():
    """ Get path to ffmpeg executable """
    base_path = get_base_path()
    
    # Check for ffmpeg.exe in the base path (for packed exe) or current dir
    ffmpeg_path = os.path.join(base_path, "ffmpeg.exe")
    
    if os.path.exists(ffmpeg_path):
        return ffmpeg_path
    
    # Fallback to system PATH if not found in bundle
    # Just return "ffmpeg" and let subprocess find it in PATH
    return "ffmpeg"
