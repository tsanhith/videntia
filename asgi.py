"""Alternate ASGI entrypoint for deployment autodetection."""

from api import app as fastapi_app

app = fastapi_app
