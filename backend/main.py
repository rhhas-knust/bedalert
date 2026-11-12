# Entry point kept at backend/main.py so `uvicorn main:app` keeps working.
from app.main import app  # noqa: F401
