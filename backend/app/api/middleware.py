"""Request context middleware: request ids, access logging, and last-resort error handling."""

import logging
import re
import secrets
import time

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.errors import error_response
from app.core.logging import request_id_var
from app.schemas.errors import ErrorCode

logger = logging.getLogger("app.request")

# Only well-formed inbound ids are trusted; anything else is replaced (prevents log injection).
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
_QUIET_PATHS = frozenset({"/health"})  # polled by Docker health checks; log at DEBUG


class RequestContextMiddleware:
    """Pure ASGI middleware.

    - Assigns an `X-Request-ID` to every response and to every log line of the request.
    - Logs one access line per request.
    - Converts any unhandled exception into the standard 500 envelope. Doing it here (inside
      the CORS middleware) keeps CORS headers on 500 responses, so browsers can read them.
      Stack traces are logged server-side and never returned.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = Headers(scope=scope).get("x-request-id")
        request_id = incoming if incoming and _REQUEST_ID_PATTERN.match(incoming) else None
        request_id = request_id or secrets.token_hex(8)
        token = request_id_var.set(request_id)

        started_at = time.perf_counter()
        status_code = 500
        response_started = False

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
                MutableHeaders(scope=message)["X-Request-ID"] = request_id
            await send(message)

        method = scope["method"]
        path = scope["path"]
        try:
            # Buffer only a small bounded JSON request before application parsing.
            # Applies to chunked bodies too, not merely Content-Length.
            if method == "POST":
                chunks = bytearray()
                disconnected = False
                while True:
                    event = await receive()
                    if event["type"] == "http.disconnect":
                        disconnected = True
                        break
                    chunks.extend(event.get("body", b""))
                    if len(chunks) > 16384:
                        response = error_response(
                            422, ErrorCode.VALIDATION_ERROR, "Request body exceeds 16 KiB."
                        )
                        await response(scope, receive, send_with_request_id)
                        return
                    if not event.get("more_body", False):
                        break
                if disconnected:
                    return
                delivered = False

                async def bounded_receive() -> Message:
                    nonlocal delivered
                    if not delivered:
                        delivered = True
                        return {"type": "http.request", "body": bytes(chunks), "more_body": False}
                    return await receive()

                await self.app(scope, bounded_receive, send_with_request_id)
            else:
                await self.app(scope, receive, send_with_request_id)
        except Exception:
            logger.exception(
                "unhandled_exception", extra={"http_method": method, "http_path": path}
            )
            if not response_started:
                response = error_response(
                    500, ErrorCode.INTERNAL_ERROR, "An unexpected error occurred."
                )
                await response(scope, receive, send_with_request_id)
        finally:
            logger.log(
                logging.DEBUG if path in _QUIET_PATHS else logging.INFO,
                "request_completed",
                extra={
                    "http_method": method,
                    "http_path": path,
                    "http_status": status_code,
                    "duration_ms": round((time.perf_counter() - started_at) * 1000, 1),
                },
            )
            request_id_var.reset(token)
