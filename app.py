"""Vercel FastAPI entrypoint.

Exposes `app` at a conventional module path (`app.py`) so platforms that
auto-detect ASGI apps can import `app:app` reliably.
"""

from api import app
