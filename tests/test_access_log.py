"""Uvicorn access log 的敏感信息脱敏测试。"""

import logging


def test_access_log_formatter_redacts_sensitive_query_params():
    """访问日志不得记录 API token，但应保留普通 query 便于诊断。"""
    from app.utils.access_log import RedactingAccessFormatter

    formatter = RedactingAccessFormatter(
        fmt='%(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s'
    )
    record = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="%s - \"%s %s HTTP/%s\" %d",
        args=("127.0.0.1:5000", "GET", "/api/v1/system/global?token=access-secret&safe=1", "1.1", 200),
        exc_info=None,
    )

    output = formatter.format(record)

    assert "access-secret" not in output
    assert "token=<redacted>" in output
    assert "safe=1" in output
