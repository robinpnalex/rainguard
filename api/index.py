"""
Vercel Python entry point.

Vercel routes every /api/* request here. The real application lives in
backend/main.py; this file only adjusts the import path and mounts it under
the /api prefix so FastAPI's own routes ("/hazards", "/health", ...) line up
with the URLs the browser requests ("/api/hazards", "/api/health").

Locally you do not need this file at all -- run `uvicorn main:app --reload`
from inside backend/ as before.
"""
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from fastapi import FastAPI  # noqa: E402

from main import app as rainguard_app  # noqa: E402

app = FastAPI()
# Mount strips the /api prefix before the inner app sees the path.
app.mount("/api", rainguard_app)
