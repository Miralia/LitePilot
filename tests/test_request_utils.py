import requests

from app.utils.http import RequestUtils


class _FakeSession:
    """
    测试用 requests.Session 替身，记录请求次数与连接池关闭行为。
    """

    def __init__(self, side_effects):
        """
        初始化请求结果序列。

        :param side_effects: 每次 request 调用要返回或抛出的对象
        """
        self.side_effects = list(side_effects)
        self.calls = []
        self.close_count = 0

    def request(self, method, url, **kwargs):
        """
        模拟 requests.Session.request。
        """
        self.calls.append((method, url, kwargs))
        effect = self.side_effects.pop(0)
        if isinstance(effect, Exception):
            raise effect
        return effect

    def close(self):
        """
        模拟清空 session 连接池。
        """
        self.close_count += 1


def _make_response(status_code: int = 200) -> requests.Response:
    response = requests.Response()
    response.status_code = status_code
    return response


def test_request_utils_retries_idempotent_session_connection_error():
    """
    同步幂等请求遇到失效 session 连接时应清理连接池并重试一次。
    """
    response = _make_response()
    session = _FakeSession(
        [
            requests.exceptions.ConnectionError("stale keep-alive"),
            response,
        ]
    )
    request_utils = RequestUtils(session=session)

    result = request_utils.get_res("https://example.com/data")

    assert result is response
    assert len(session.calls) == 2
    assert session.close_count == 1


def test_request_utils_does_not_retry_non_idempotent_connection_error():
    """
    非幂等请求连接异常时不应自动重试，避免重复提交副作用。
    """
    session = _FakeSession(
        [
            requests.exceptions.ConnectionError("connection failed"),
            _make_response(),
        ]
    )
    request_utils = RequestUtils(session=session)

    result = request_utils.post_res("https://example.com/data", data={"name": "demo"})

    assert result is None
    assert len(session.calls) == 1
    assert session.close_count == 0


def test_request_utils_raises_retry_error_when_retry_still_fails():
    """
    开启 raise_exception 后，重试仍失败时应抛出重试阶段的异常。
    """
    first_error = requests.exceptions.ConnectionError("stale keep-alive")
    retry_error = requests.exceptions.ConnectionError("proxy still unavailable")
    session = _FakeSession([first_error, retry_error])
    request_utils = RequestUtils(session=session)

    try:
        request_utils.get_res("https://example.com/data", raise_exception=True)
    except requests.exceptions.ConnectionError as err:
        assert err is retry_error
    else:
        raise AssertionError("请求重试失败时应抛出异常")

    assert len(session.calls) == 2
    assert session.close_count == 1


def test_request_utils_error_log_redacts_sensitive_query_params(monkeypatch):
    """同步请求异常日志不得泄露 URL query 中的媒体服务器或 API 凭据。"""
    error = requests.exceptions.ConnectionError(
        "Max retries exceeded with url: /Items/1?api_key=emby-secret&access_token=token-secret"
    )
    session = _FakeSession([error])
    messages = []
    monkeypatch.setattr("app.utils.http.logger.debug", lambda message: messages.append(message))

    result = RequestUtils(session=session).post_res("https://emby.local/Items/1", data={})

    assert result is None
    assert messages
    joined = "\n".join(messages)
    assert "emby-secret" not in joined
    assert "token-secret" not in joined
    assert "api_key=<redacted>" in joined
    assert "access_token=<redacted>" in joined


def test_request_utils_empty_error_log_redacts_fallback_url(monkeypatch):
    """异常对象没有消息时，兜底拼接的请求 URL 也必须先脱敏。"""
    session = _FakeSession([requests.exceptions.RequestException()])
    messages = []
    monkeypatch.setattr("app.utils.http.logger.debug", lambda message: messages.append(message))

    result = RequestUtils(session=session).post_res(
        "https://emby.local/Items/1?api_key=fallback-secret", data={}
    )

    assert result is None
    joined = "\n".join(messages)
    assert "fallback-secret" not in joined
    assert "api_key=<redacted>" in joined
