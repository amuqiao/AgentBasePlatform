"""
Application entry point.
Usage: uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""

from src.main import app  # noqa: F401
