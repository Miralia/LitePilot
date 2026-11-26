"""运行时组件日志边界测试。"""

import ast
from pathlib import Path

from app.utils.otp import OtpUtils


def test_runtime_components_do_not_print_to_stdout() -> None:
    """运行时组件异常应进入统一日志或静默降级，不能绕过日志输出stdout。"""
    for filename in (
        "app/helper/image.py",
        "app/db/__init__.py",
        "app/utils/otp.py",
    ):
        tree = ast.parse(Path(filename).read_text())
        print_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "print"
        ]
        assert not print_calls, f"{filename} 仍包含 print 调用"


def test_invalid_otp_uri_does_not_write_stdout(capsys) -> None:
    """非法 OTP URI 只应判定失败，不能把认证配置细节写入stdout。"""
    assert OtpUtils.is_legal("not-a-uri", "123456") is False
    captured = capsys.readouterr()
    assert captured.out == ""
