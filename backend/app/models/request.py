"""API-level idempotency records for mutating operations.

Scope: each record is unique per (route, idempotency_key, request_hash body).
Two concurrent identical requests with the same key perform the effect once;
a different payload under the same key is a 409 conflict, never a re-execution.
"""
from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ApiIdempotency(Base):
    __tablename__ = "api_idempotency"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    route: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="committed")
    # pending | committed | failed
    result_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    response_body: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "route", "idempotency_key", name="uq_idempotency_route_key",
        ),
    )
