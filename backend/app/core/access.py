"""Production request limits, origin checks and optional gateway authentication."""

import hmac

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import Settings


class ProductionAccessMiddleware:
    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self.app = app
        self.settings = settings
        self.active_requests = 0

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not self.settings.production:
            await self.app(scope, receive, send)
            return
        request = Request(scope, receive)
        if request.url.path == "/health" and request.method in {"GET", "HEAD"}:
            await self.app(scope, receive, send)
            return

        async def reject(status: int, code: str, message: str) -> None:
            response = JSONResponse(
                {"error": {"code": code, "message": message}},
                status_code=status,
                headers={"Cache-Control": "no-store"},
            )
            await response(scope, receive, send)

        if self.settings.deployment_mode == "gateway":
            expected = self.settings.access_proxy_token.get_secret_value()
            supplied = request.headers.get("x-insightforge-proxy-token", "")
            if not hmac.compare_digest(supplied.encode(), expected.encode()):
                await reject(
                    401, "authentication_required", "Sign in through the application gateway"
                )
                return
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            if (
                origin is not None and origin not in self.settings.allowed_origins
            ) or request.headers.get("x-requested-with") != "InsightForge":
                await reject(403, "request_origin_rejected", "The request origin is not allowed")
                return
            body = bytearray()
            while True:
                event = await receive()
                if event["type"] == "http.disconnect":
                    return
                body.extend(event.get("body", b""))
                if len(body) > self.settings.max_request_bytes:
                    await reject(413, "request_too_large", "The request body is too large")
                    return
                if not event.get("more_body", False):
                    break
            sent = False

            async def replay_body() -> dict:
                nonlocal sent
                if not sent:
                    sent = True
                    return {"type": "http.request", "body": bytes(body), "more_body": False}
                return await receive()

            downstream_receive = replay_body
        else:
            downstream_receive = receive
        if self.active_requests >= self.settings.max_concurrent_requests:
            await reject(429, "server_busy", "The server is busy. Please try again shortly")
            return

        async def private_response(event: dict) -> None:
            if event["type"] == "http.response.start":
                headers = [
                    (key, value)
                    for key, value in event.get("headers", [])
                    if key.lower()
                    not in {
                        b"x-content-type-options",
                        b"referrer-policy",
                        b"content-security-policy",
                        b"strict-transport-security",
                        b"permissions-policy",
                    }
                    and (key.lower() != b"cache-control" or not request.url.path.startswith("/api"))
                ]
                if request.url.path.startswith("/api"):
                    headers.append((b"cache-control", b"no-store"))
                headers.extend(
                    [
                        (b"x-content-type-options", b"nosniff"),
                        (b"referrer-policy", b"no-referrer"),
                        (b"strict-transport-security", b"max-age=31536000"),
                        (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
                        (
                            b"content-security-policy",
                            b"default-src 'self'; script-src 'self'; "
                            b"style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
                            b"font-src 'self'; "
                            b"connect-src 'self'; object-src 'none'; base-uri 'self'; "
                            b"frame-ancestors 'none'; form-action 'self'",
                        ),
                    ]
                )
                event["headers"] = headers
            await send(event)

        self.active_requests += 1
        try:
            await self.app(scope, downstream_receive, private_response)
        finally:
            self.active_requests -= 1
