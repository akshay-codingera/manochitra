"""Vercel Serverless Function entrypoint for Manochitra science diagram maker."""

import sys
from pathlib import Path

# Add backend directory to sys.path so app modules can be imported
ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.main import app
