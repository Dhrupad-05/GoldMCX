"""Structured JSON logging with request/run IDs; never logs secrets."""
import json
import logging
import sys
import time
import uuid
from contextlib import contextmanager

_context: dict[str, str] = {}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if _context.get("request_id"):
            payload["request_id"] = _context["request_id"]
        if _context.get("run_id"):
            payload["run_id"] = _context["run_id"]
        if record.exc_info and record.exc_info[0] is not None:
            payload["exception"] = record.exc_info[0].__name__
        return json.dumps(payload, default=str)


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)


def new_request_id() -> str:
    rid = uuid.uuid4().hex[:12]
    _context["request_id"] = rid
    return rid


@contextmanager
def run_id(run: str):
    """Bind an ingestion/backtest run id to log lines."""
    _context["run_id"] = run
    try:
        yield
    finally:
        _context.pop("run_id", None)


logger = logging.getLogger("mcx")
