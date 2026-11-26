"""认证响应缓存隔离边界。"""

from fastapi import FastAPI, Response
from fastapi.testclient import TestClient

from app.core.security_middleware import AuthorizationVaryMiddleware
from app.factory import create_app


def build_test_app() -> TestClient:
    """构造不访问真实网络的认证缓存测试应用。"""
    app = FastAPI()
    app.add_middleware(AuthorizationVaryMiddleware)

    @app.get("/items")
    def get_items() -> dict:
        """返回测试数据。"""
        return {"items": []}

    @app.get("/varied")
    def get_varied(response: Response) -> dict:
        """返回已有 Vary 的测试数据。"""
        response.headers["Vary"] = "Accept-Encoding"
        return {"items": []}

    return TestClient(app)


def test_authorization_request_adds_vary_header():
    """带 Authorization 的响应必须按凭证隔离缓存。"""
    client = build_test_app()

    response = client.get("/items", headers={"Authorization": "Bearer token"})

    assert response.status_code == 200
    assert "authorization" in response.headers["vary"].lower()


def test_anonymous_request_does_not_add_vary_header():
    """匿名响应不应被无意义地降低缓存共享能力。"""
    client = build_test_app()

    response = client.get("/items")

    assert response.status_code == 200
    assert "vary" not in response.headers


def test_existing_vary_is_preserved_without_duplicate_values():
    """已有 Vary 必须保留，Authorization 只补充一次。"""
    client = build_test_app()

    response = client.get("/varied", headers={"Authorization": "Bearer token"})

    values = [value.strip().lower() for value in response.headers["vary"].split(",")]
    assert "accept-encoding" in values
    assert values.count("authorization") == 1


def test_factory_registers_authorization_vary_middleware():
    """真实应用必须注册认证缓存隔离中间件。"""
    app = create_app()

    assert any(middleware.cls is AuthorizationVaryMiddleware for middleware in app.user_middleware)
