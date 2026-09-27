import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, notes
from app.config import get_settings
from app.errors import install_error_handlers

API_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    app = FastAPI(title="CodeCare AI", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=sorted({"http://localhost:3000", settings.frontend_origin}),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    install_error_handlers(app)
    app.include_router(health.router, prefix=API_PREFIX)
    app.include_router(notes.router, prefix=API_PREFIX)
    return app


app = create_app()
