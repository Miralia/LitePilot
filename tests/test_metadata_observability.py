"""元数据客户端日志边界测试。"""

import ast
from pathlib import Path


def test_metadata_clients_do_not_print_errors_to_stdout() -> None:
    """元数据客户端异常应进入统一日志系统，不能绕过日志直接输出stdout。"""
    for filename in (
        "app/modules/bangumi/bangumi.py",
        "app/modules/themoviedb/tmdbapi.py",
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
