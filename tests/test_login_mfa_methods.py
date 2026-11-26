import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import Response

from app.api.endpoints import login as login_endpoint
from app.chain.user import AuthCredentials, MfaRequired, PASSWORD_INVALID_CREDENTIALS_MESSAGE, UserChain


@pytest.fixture(autouse=True)
def reset_login_throttle_state():
    """每个登录测试都从空的限流状态开始，避免用例间相互污染。"""
    with login_endpoint._login_throttle_lock:
        login_endpoint._login_throttle_states.clear()
    yield
    with login_endpoint._login_throttle_lock:
        login_endpoint._login_throttle_states.clear()


def _request() -> Request:
    """构造登录接口所需的最小请求。"""
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/login/access-token",
            "headers": [(b"host", b"testserver")],
            "scheme": "http",
            "server": ("testserver", 80),
            "client": ("testclient", 123),
        }
    )


def _form() -> SimpleNamespace:
    """构造密码登录表单契约。"""
    return SimpleNamespace(username="user", password="password")


def test_verify_mfa_requires_otp_when_enabled():
    """密码通过后应返回账号已启用的 OTP 二次验证方式。"""
    user = SimpleNamespace(id=1, name="user", is_otp=True, otp_secret="")

    result = UserChain._verify_mfa(user=user, mfa_code=None)

    assert isinstance(result, MfaRequired)
    assert result.methods == ("otp",)


def test_verify_mfa_ignores_passkeys_when_otp_is_disabled():
    """Passkey 独立登录能力不应改变密码登录结果。"""
    user = SimpleNamespace(id=1, name="user", is_otp=False, otp_secret="")

    assert UserChain._verify_mfa(user=user, mfa_code=None) is True


def test_login_mfa_response_contains_methods_after_password_verification(monkeypatch):
    """MFA 响应应保持旧标记并补充结构化方法列表。"""

    class FakeUserChain:
        """返回已通过密码校验的 MFA 要求。"""

        def user_authenticate(self, username, password, mfa_code=None):
            """模拟账号启用了 OTP。"""
            return False, MfaRequired(methods=("otp",))

    monkeypatch.setattr(login_endpoint, "UserChain", FakeUserChain)

    response = login_endpoint.login_access_token(
        request=_request(),
        response=Response(),
        form_data=_form(),
    )

    assert response.status_code == 401
    assert response.headers["x-mfa-required"] == "true"
    assert json.loads(response.body) == {
        "detail": "需要二次验证",
        "mfa_methods": ["otp"],
    }


def test_login_invalid_password_does_not_expose_mfa_methods(monkeypatch):
    """密码未通过时不得返回账号的 MFA 能力。"""

    class FakeUserChain:
        """返回普通认证失败。"""

        def user_authenticate(self, username, password, mfa_code=None):
            """模拟错误密码。"""
            return False, "用户名、密码或验证码错误"

    monkeypatch.setattr(login_endpoint, "UserChain", FakeUserChain)

    with pytest.raises(HTTPException) as exc_info:
        login_endpoint.login_access_token(
            request=_request(),
            response=Response(),
            form_data=_form(),
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "用户名或密码错误"
    assert "X-MFA-Required" not in (exc_info.value.headers or {})


def test_login_throttles_repeated_failures_before_authentication(monkeypatch):
    """同一来源与账号连续认证失败后必须限流，避免无界在线暴力破解。"""
    calls: list[tuple[str, str]] = []

    class FakeUserChain:
        """始终返回密码失败并记录触达次数。"""

        def user_authenticate(self, username, password, mfa_code=None):
            """记录一次实际认证调用。"""
            calls.append((username, password))
            return False, "用户名、密码或验证码错误"

    monkeypatch.setattr(login_endpoint, "UserChain", FakeUserChain)
    form = SimpleNamespace(username="throttle-red-user", password="wrong")

    for _ in range(5):
        with pytest.raises(HTTPException) as exc_info:
            login_endpoint.login_access_token(
                request=_request(),
                response=Response(),
                form_data=form,
            )
        assert exc_info.value.status_code == 401

    with pytest.raises(HTTPException) as exc_info:
        login_endpoint.login_access_token(
            request=_request(),
            response=Response(),
            form_data=form,
        )

    assert exc_info.value.status_code == 429
    assert exc_info.value.headers and int(exc_info.value.headers["Retry-After"]) > 0
    assert len(calls) == 5


def test_mfa_challenge_does_not_count_as_password_failure(monkeypatch):
    """密码通过后的 OTP 挑战响应不是暴力破解失败，不应触发账号限流。"""
    calls = 0

    class FakeUserChain:
        """始终要求 OTP。"""

        def user_authenticate(self, username, password, mfa_code=None):
            """记录一次认证调用。"""
            nonlocal calls
            calls += 1
            return False, MfaRequired(methods=("otp",))

    monkeypatch.setattr(login_endpoint, "UserChain", FakeUserChain)
    form = SimpleNamespace(username="mfa-throttle-user", password="correct")

    for _ in range(8):
        response = login_endpoint.login_access_token(
            request=_request(),
            response=Response(),
            form_data=form,
        )
        assert response.status_code == 401

    assert calls == 8


def test_login_throttles_source_ip_across_rotated_usernames(monkeypatch):
    """轮换账号的同一来源也不能无界尝试，IP 级阈值应独立生效。"""
    calls = 0

    class FakeUserChain:
        """始终返回认证失败。"""

        def user_authenticate(self, username, password, mfa_code=None):
            """记录一次认证调用。"""
            nonlocal calls
            calls += 1
            return False, "用户名、密码或验证码错误"

    monkeypatch.setattr(login_endpoint, "UserChain", FakeUserChain)

    for index in range(30):
        form = SimpleNamespace(username=f"rotated-user-{index}", password="wrong")
        with pytest.raises(HTTPException) as exc_info:
            login_endpoint.login_access_token(
                request=_request(),
                response=Response(),
                form_data=form,
            )
        assert exc_info.value.status_code == 401

    form = SimpleNamespace(username="rotated-user-final", password="wrong")
    with pytest.raises(HTTPException) as exc_info:
        login_endpoint.login_access_token(
            request=_request(),
            response=Response(),
            form_data=form,
        )

    assert exc_info.value.status_code == 429
    assert calls == 30


def test_missing_user_still_pays_password_verification_cost(monkeypatch):
    """查无用户时也要执行一次 bcrypt 校验，避免用响应时间枚举有效账号。"""
    calls: list[tuple[str, str]] = []

    class MissingUserSync:
        """模拟非 swizzin 环境，避免触碰宿主机账号。"""

        def available(self):
            """返回当前环境不由 swizzin 托管。"""
            return False

    class MissingUserOper:
        """模拟用户不存在。"""

        def get_by_name(self, name):
            """返回查无用户。"""
            return None

    def fake_verify_password(password, hashed_password):
        """记录执行的恒定时间密码校验。"""
        calls.append((password, hashed_password))
        return False

    monkeypatch.setattr("app.chain.user.SwizzinUserSync", MissingUserSync)
    monkeypatch.setattr("app.chain.user.UserOper", MissingUserOper)
    monkeypatch.setattr("app.chain.user.verify_password", fake_verify_password)

    success, message = UserChain.password_authenticate(
        AuthCredentials(username="missing-user", password="wrong")
    )

    assert success is False
    assert message == PASSWORD_INVALID_CREDENTIALS_MESSAGE
    assert len(calls) == 1
    assert calls[0][0] == "wrong"
    assert calls[0][1].startswith("$2")
