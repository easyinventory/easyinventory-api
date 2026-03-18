"""Request/response logging middleware.

Provides:
- Correlation IDs (X-Request-ID header) for tracing requests
- Structured JSON request/response logging
- Sensitive field sanitisation (passwords, tokens, etc.)
- Request + response body logging on errors (4xx/5xx) for debugging
"""

import json
import logging
import time
import uuid
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import StreamingResponse

logger = logging.getLogger("api")

# ── Fields whose values are replaced with "***" before logging ──
SENSITIVE_FIELDS = {
    "password",
    "new_password",
    "access_token",
    "refresh_token",
    "id_token",
    "authorization",
    "secret",
    "aws_secret_access_key",
}

# Cap how much of a body we'll log to avoid flooding stdout
_MAX_BODY_LOG = 2_000  # characters


# ── Helpers ──────────────────────────────────────────────────────


def sanitize(data: Any) -> Any:
    """Recursively redact values of sensitive keys."""
    if isinstance(data, dict):
        return {
            k: ("***" if k.lower() in SENSITIVE_FIELDS else sanitize(v))
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [sanitize(item) for item in data]
    return data


def _parse_body(raw: bytes) -> Any:
    """Try to parse as JSON; fall back to truncated string."""
    try:
        return json.loads(raw.decode())
    except Exception:
        return raw.decode(errors="ignore")[:_MAX_BODY_LOG]


# ── JSON log formatter (CloudWatch-friendly) ────────────────────


class JsonFormatter(logging.Formatter):
    """Emit each log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "time": self.formatTime(record),
        }
        # If the message is already a dict (structured log), merge it in
        msg = record.msg
        if isinstance(msg, dict):
            log_obj.update(msg)
        else:
            log_obj["message"] = record.getMessage()
        return json.dumps(log_obj, default=str)


# ── Middleware ───────────────────────────────────────────────────


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # ── Correlation ID ──
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        start = time.perf_counter()

        # Always read the body so it's available for error logging
        body = await request.body()

        # ── Log request summary ──
        log_payload: dict[str, Any] = {
            "type": "request",
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "query": str(request.query_params) or None,
        }
        logger.info(log_payload)

        # ── Call the actual endpoint ──
        try:
            response = await call_next(request)
        except Exception as exc:
            # Unhandled exceptions (500s) never produce a response object,
            # so we log them here with the request body for debugging.
            duration_ms = (time.perf_counter() - start) * 1_000
            error_log: dict[str, Any] = {
                "type": "response",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": 500,
                "duration_ms": round(duration_ms, 1),
                "error": f"{type(exc).__name__}: {exc}",
            }
            if body:
                parsed_req = _parse_body(body)
                error_log["request_body"] = (
                    sanitize(parsed_req) if isinstance(parsed_req, dict) else parsed_req
                )
            logger.error(error_log)
            raise  # re-raise so FastAPI/Starlette still returns the 500

        duration_ms = (time.perf_counter() - start) * 1_000
        is_error = response.status_code >= 400

        # ── Read response body on errors for logging ──
        resp_body_raw: bytes | None = None
        if is_error and isinstance(response, StreamingResponse):
            chunks: list[bytes] = []
            async for chunk in response.body_iterator:
                if isinstance(chunk, bytes):
                    chunks.append(chunk)
                elif isinstance(chunk, str):
                    chunks.append(chunk.encode())
                else:
                    chunks.append(bytes(chunk))
            resp_body_raw = b"".join(chunks)
            response = Response(
                content=resp_body_raw,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

        # ── Log response ──
        resp_log: dict[str, Any] = {
            "type": "response",
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 1),
        }

        if is_error:
            # Attach request body on errors so we can reproduce the issue
            if body:
                parsed_req = _parse_body(body)
                resp_log["request_body"] = (
                    sanitize(parsed_req) if isinstance(parsed_req, dict) else parsed_req
                )
            # Attach response body
            if resp_body_raw:
                parsed_resp = _parse_body(resp_body_raw)
                resp_log["body"] = (
                    sanitize(parsed_resp)
                    if isinstance(parsed_resp, dict)
                    else parsed_resp
                )

        log_fn = logger.warning if is_error else logger.info
        log_fn(resp_log)

        # ── Echo correlation ID back to the client ──
        response.headers["X-Request-ID"] = request_id
        return response
