import sys
import os

# Add backend/src to path so module imports work on Vercel.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend", "src"))

from main import app
