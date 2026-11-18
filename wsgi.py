"""WSGI entry point for gunicorn.

Equivalent to ``gunicorn server:app``; provided so hosts configured with
``gunicorn wsgi:app`` also resolve the application.
"""
from server import app, application  # noqa: F401
