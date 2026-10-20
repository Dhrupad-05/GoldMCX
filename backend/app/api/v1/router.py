"""Aggregated v1 API router. /health/* lives at the service root, not here."""
from fastapi import APIRouter

api_router = APIRouter()


def _include_all() -> None:
    from app.api.v1.routes import (
        backtests,
        comparisons,
        contracts,
        dashboard,
        events,
        ingestion,
        model,
        signals,
    )

    api_router.include_router(backtests.router)
    api_router.include_router(comparisons.router)
    api_router.include_router(contracts.router)
    api_router.include_router(signals.router)
    api_router.include_router(model.router)
    api_router.include_router(events.router)
    api_router.include_router(ingestion.router)
    api_router.include_router(dashboard.router)


_include_all()
