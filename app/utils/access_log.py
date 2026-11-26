"""Uvicorn 访问日志的敏感信息脱敏工具。"""

import logging
from copy import copy, deepcopy
from typing import Any

from uvicorn.config import LOGGING_CONFIG
from uvicorn.logging import AccessFormatter

from app.utils.security import SecurityUtils


class RedactingAccessFormatter(AccessFormatter):
    """在格式化访问日志前脱敏请求路径中的可重放凭据。"""

    def formatMessage(self, record: logging.LogRecord) -> str:
        """复制日志记录后脱敏路径，避免影响同一记录的其他消费者。"""
        recordcopy = copy(record)
        args = recordcopy.args
        if isinstance(args, tuple) and len(args) >= 3:
            redacted_args = list(args)
            redacted_args[2] = SecurityUtils.redact_sensitive_url_params(str(redacted_args[2]))
            recordcopy.args = tuple(redacted_args)
        return super().formatMessage(recordcopy)


def build_uvicorn_log_config() -> dict[str, Any]:
    """构造使用脱敏 access formatter 的 Uvicorn 日志配置。"""
    config = deepcopy(LOGGING_CONFIG)
    config["formatters"]["access"]["()"] = "app.utils.access_log.RedactingAccessFormatter"
    return config
