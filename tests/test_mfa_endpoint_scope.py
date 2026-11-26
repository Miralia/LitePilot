"""MFA 端点范围回归测试。"""

from app.api.endpoints import mfa as mfa_endpoint


def test_mfa_status_by_username_endpoint_is_not_exposed():
    """未认证客户端不能按用户名探测 OTP 开启状态。"""
    routes = {route.path for route in mfa_endpoint.router.routes}
    assert not hasattr(mfa_endpoint, "mfa_status")
    assert "/status/{username}" not in routes


def test_otp_management_endpoints_remain_available():
    """OTP 绑定、验证和关闭能力仍然保留。"""
    assert hasattr(mfa_endpoint, "otp_generate")
    assert hasattr(mfa_endpoint, "otp_verify")
    assert hasattr(mfa_endpoint, "otp_disable")
