import sys
import os

# Add src/ to path so imports like `app.main`, `utils.config` etc. work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app.main import app
