import sys
import os

# Add backend/src to path so `app.*` and `utils.*` imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend", "src"))

from app.main import app
