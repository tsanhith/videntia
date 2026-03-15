"""Vercel FastAPI entrypoint.

Keep an explicit module-level `app` assignment for platform autodetection.
"""

from api import app as fastapi_app

app = fastapi_app
