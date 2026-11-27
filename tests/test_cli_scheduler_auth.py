"""CLI 调度命令认证头契约测试。"""

from unittest.mock import patch

from click.testing import CliRunner

from tests.test_cli_auto_update import load_cli_module


def test_api_token_headers_use_api_key_header():
    """CLI 必须使用后端支持的 X-API-KEY，而不是 JWT 专用 Bearer 头。"""
    module = load_cli_module()
    module.settings.API_TOKEN = "test-api-token-16"

    assert module._api_token_headers() == {"X-API-KEY": "test-api-token-16"}


def test_api_token_headers_empty_when_token_missing():
    """未配置 API_TOKEN 时 CLI 不构造空认证头。"""
    module = load_cli_module()
    module.settings.API_TOKEN = ""

    assert module._api_token_headers() == {}


def test_scheduler_list_uses_v2_uniform_response_api():
    """调度列表使用 v2 统一响应信封，避免把 v1 原始数组误当错误。"""
    module = load_cli_module()
    module.settings.API_TOKEN = "test-api-token-16"
    captured = {}

    def fake_http_request(method, path, **kwargs):
        captured["method"] = method
        captured["path"] = path
        captured["headers"] = kwargs.get("headers")
        return {
            "status": 200,
            "json": {
                "success": True,
                "message": "",
                "data": [
                    {
                        "id": "transfer",
                        "state": "waiting",
                        "next_run": "2026-11-26 16:10:00",
                        "name": "下载文件整理",
                    }
                ],
            },
        }

    with patch.object(module, "_http_request", side_effect=fake_http_request):
        result = CliRunner().invoke(module.scheduler_list, [])

    assert result.exit_code == 0, result.output
    assert "transfer" in result.output
    assert captured == {
        "method": "GET",
        "path": "/api/v2/dashboard/schedule",
        "headers": {"X-API-KEY": "test-api-token-16"},
    }


def test_scheduler_run_uses_v2_uniform_response_api():
    """调度执行使用 v2 统一响应接口和 API_KEY 认证头。"""
    module = load_cli_module()
    module.settings.API_TOKEN = "test-api-token-16"
    captured = {}

    def fake_http_request(method, path, **kwargs):
        captured["method"] = method
        captured["path"] = path
        captured["params"] = kwargs.get("params")
        captured["headers"] = kwargs.get("headers")
        return {"status": 200, "json": {"success": True, "message": "", "data": {}}}

    with patch.object(module, "_http_request", side_effect=fake_http_request):
        result = CliRunner().invoke(module.scheduler_run, ["transfer"])

    assert result.exit_code == 0, result.output
    assert "已触发调度任务：transfer" in result.output
    assert captured == {
        "method": "GET",
        "path": "/api/v2/system/runscheduler",
        "params": {"jobid": "transfer"},
        "headers": {"X-API-KEY": "test-api-token-16"},
    }


def test_scheduler_run_prefers_runtime_token_over_changed_config():
    """服务运行期间配置被修改时，CLI 仍应使用运行中服务实际持有的 token。"""
    module = load_cli_module()
    module.settings.API_TOKEN = "new-config-token"
    captured = {}

    def fake_http_request(method, path, **kwargs):
        captured["headers"] = kwargs.get("headers")
        return {"status": 200, "json": {"success": True, "message": "", "data": {}}}

    with patch.object(module, "_backend_runtime", return_value={"api_token": "running-service-token"}):
        with patch.object(module, "_http_request", side_effect=fake_http_request):
            result = CliRunner().invoke(module.scheduler_run, ["transfer"])

    assert result.exit_code == 0, result.output
    assert captured["headers"] == {"X-API-KEY": "running-service-token"}
