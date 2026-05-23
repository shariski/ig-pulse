"""Shared Jinja2 templates instance (separate module to avoid import cycles:
routes import this; main imports routes)."""

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")
