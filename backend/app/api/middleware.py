"""Cross-cutting HTTP concerns: metrics, security headers and a simple rate limiter."""

import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.observability import HTTP_LATENCY, HTTP_REQUESTS


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        started = time.perf_counter()
        response = await call_next(request)
        route = request.scope.get("route")
        # Label by route template (/runs/{run_id}), never the raw path, to bound cardinality.
        path = getattr(route, "path", "unmatched")
        HTTP_REQUESTS.labels(request.method, path, str(response.status_code)).inc()
        HTTP_LATENCY.labels(request.method, path).observe(time.perf_counter() - started)
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window limit per client IP on /api routes.

    In-process only: good enough for a single API container. Behind several replicas,
    move this to the reverse proxy or a shared store.
    """

    def __init__(self, app: ASGIApp, per_minute: int) -> None:
        super().__init__(app)
        self.per_minute = per_minute
        self.hits: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if self.per_minute <= 0 or not request.url.path.startswith("/api/"):
            return await call_next(request)
        # Key by client IP only. Keying by the X-API-Key header would let an attacker
        # bypass the limit by sending a different made-up key on every request.
        client = request.client.host if request.client else "unknown"
        now = time.monotonic()
        window = self.hits[client]
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= self.per_minute:
            return JSONResponse(
                {"detail": "rate limit exceeded"}, status_code=429, headers={"Retry-After": "60"}
            )
        window.append(now)
        return await call_next(request)


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject oversized requests from Content-Length before the body is read or parsed.

    The upload endpoint checks the file size too, but multipart parsing would already have
    buffered the whole body by then. Requests without Content-Length (chunked) are capped by
    the reverse proxy (nginx client_max_body_size).
    """

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > self.max_bytes:
            return JSONResponse({"detail": "request body too large"}, status_code=413)
        return await call_next(request)
