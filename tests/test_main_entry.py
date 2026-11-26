"""后端服务主入口的启动参数边界测试。"""

import runpy
import sys

import pytest
import uvicorn


def test_main_entry_rejects_unexpected_arguments_before_startup(monkeypatch):
    """误把 CLI 子命令传给服务入口时必须 fail-fast，不能启动第二个后端实例。"""
    server_starts = []
    db_starts = []
    monkeypatch.setattr(uvicorn.Server, "run", lambda _self: server_starts.append(True))
    monkeypatch.setattr("app.db.init.init_db", lambda: db_starts.append("init"))
    monkeypatch.setattr("app.db.init.update_db", lambda: db_starts.append("update"))
    monkeypatch.setattr(sys, "argv", ["python -m app.main", "doctor", "--json"])
    monkeypatch.delitem(sys.modules, "app.main", raising=False)

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_module("app.main", run_name="__main__")

    assert exc_info.value.code == 2
    assert server_starts == []
    assert db_starts == []
