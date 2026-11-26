from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class AuthorizationVaryMiddleware(BaseHTTPMiddleware):
    """
    为认证请求补充 Vary 头，避免共享缓存按 URL 跨凭证复用响应。
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """
        在带 Authorization 的请求响应中合并 Authorization Vary 值。
        """
        response = await call_next(request)
        if not request.headers.get("authorization"):
            return response

        vary = response.headers.get("vary")
        if not vary:
            response.headers["vary"] = "Authorization"
            return response

        vary_values = {value.strip().lower() for value in vary.split(",") if value.strip()}
        if "*" in vary_values or "authorization" in vary_values:
            return response
        response.headers["vary"] = f"{vary}, Authorization"
        return response
