"""FastAPI application factory: CORS, logging, errors, routers, health."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.errors import AppError, app_error_handler, unexpected_error_handler
from app.core.logging_config import setup_logging
from app.api.v1.router import api_router
from app.api.v1.routes.health import router as health_router

VERSION = "1.0.0"


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level)
    app = FastAPI(
        title="MCX Gold Intelligence API",
        version=VERSION,
        description=(
            "Backend for MCX Gold Intelligence (Hack in Hills '26, PS-03). "
            "Contract-aware relative-value analytics with data provenance. "
            "Derived results are provisional unless marked VERIFIED; nothing here "
            "is investment advice."
        ),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)
    app.include_router(api_router, prefix=settings.api_prefix)
    app.include_router(health_router)  # /health/live and /health/ready at root
    return app


app = create_app()
