"""Model registry: importing this package guarantees all mappers register."""
from app.models import evaluation, market, ml_registry, request, source, live  # noqa: F401
