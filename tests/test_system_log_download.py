"""系统日志查看与下载接口的权限和打包行为测试。"""

import asyncio
import io
import threading
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.responses import Response

from app.api.endpoints import system as system_endpoint
from app.core.config import settings


def test_logging_routes_use_superuser_dependency():
    """日志查看和下载路由都必须绑定管理员依赖，避免普通登录用户读取敏感日志。"""
    routes = {route.path: route for route in system_endpoint.router.routes}

    logging_dependencies = {dependency.call for dependency in routes["/logging"].dependant.dependencies}
    download_dependencies = {dependency.call for dependency in routes["/logging/download/{name}"].dependant.dependencies}

    assert system_endpoint._verify_log_resource_superuser in logging_dependencies
    assert system_endpoint._verify_log_resource_superuser in download_dependencies


def test_log_resource_dependency_rejects_normal_user():
    """日志资源依赖必须拒绝非管理员 resource token。"""
    with pytest.raises(HTTPException) as exc_info:
        system_endpoint._verify_log_resource_superuser(
            SimpleNamespace(super_user=False),
        )

    assert exc_info.value.status_code == 403


@pytest.fixture(name="isolated_log_path")
def fixture_isolated_log_path(monkeypatch, tmp_path: Path) -> Path:
    """将日志目录隔离到临时目录，避免测试读取或打包真实运行日志。"""
    config_path = tmp_path / "config"
    log_path = config_path / "logs"
    log_path.mkdir(parents=True)
    monkeypatch.setattr(settings, "CONFIG_DIR", str(config_path))
    return log_path


def test_logging_requires_superuser_dependency(monkeypatch, isolated_log_path):
    """实时日志查看接口必须通过管理员依赖，普通资源令牌不能直接读取日志。"""
    (isolated_log_path / "moviepilot.log").write_text("hello\n", encoding="utf-8")
    response = asyncio.run(
        system_endpoint.get_logging(
            request=SimpleNamespace(is_disconnected=lambda: False),
            length=-1,
            logfile="moviepilot.log",
            _=SimpleNamespace(id=1, name="admin", is_superuser=True),
        )
    )

    assert isinstance(response, Response)


def test_logging_rejects_legacy_plugin_log_name(isolated_log_path):
    """实时日志接口只允许主程序日志，不再暴露历史插件日志文件。"""
    (isolated_log_path / "example.log").write_text("legacy\n", encoding="utf-8")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            system_endpoint.get_logging(
                request=SimpleNamespace(is_disconnected=lambda: False),
                length=-1,
                logfile="example.log",
                _=SimpleNamespace(id=1, name="admin", is_superuser=True),
            )
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_logging_sse_drains_burst_lines(monkeypatch, isolated_log_path):
    """实时日志 SSE 必须完整消费一次追加的多行内容，不能按轮询周期丢行。"""
    log_file = isolated_log_path / "moviepilot.log"
    log_file.write_text("seed\n", encoding="utf-8")
    original_sleep = asyncio.sleep

    async def fast_sleep(delay):
        """压缩 endpoint 内部轮询等待，避免测试依赖真实秒级时钟。"""
        await original_sleep(min(delay, 0.01))

    async def is_disconnected():
        """测试期间保持 SSE 客户端连接。"""
        return False

    monkeypatch.setattr(asyncio, "sleep", fast_sleep)
    response = await system_endpoint.get_logging(
        request=SimpleNamespace(is_disconnected=is_disconnected),
        length=10,
        logfile="moviepilot.log",
        _=SimpleNamespace(id=1, name="admin", is_superuser=True),
    )
    stream = response.body_iterator

    async def read_frame() -> str:
        """有界读取下一帧，防止生成器静默停顿时测试挂死。"""
        return await asyncio.wait_for(stream.__anext__(), 1)

    def append_lines(text: str) -> None:
        """模拟运行日志的一次连续追加写入。"""
        with log_file.open("a", encoding="utf-8") as file:
            file.write(text)

    try:
        assert await read_frame() == "data: seed\n\n"
        await original_sleep(0.1)

        append_lines("probe\n")
        assert await read_frame() == "data: probe\n\n"

        append_lines("burst-1\nburst-2\nburst-3\n")
        assert await read_frame() == "data: burst-1\n\n"
        assert await read_frame() == "data: burst-2\n\n"
        assert await read_frame() == "data: burst-3\n\n"
    finally:
        await stream.aclose()


@pytest.mark.asyncio
async def test_logging_sse_follows_rotated_log_file(monkeypatch, isolated_log_path):
    """实时日志 SSE 必须在滚动后继续读取新文件，不能无限跟随已重命名的旧 inode。"""
    log_file = isolated_log_path / "moviepilot.log"
    log_file.write_text("seed\n", encoding="utf-8")
    original_sleep = asyncio.sleep

    async def fast_sleep(delay):
        """压缩 endpoint 内部轮询等待，避免测试依赖真实秒级时钟。"""
        await original_sleep(min(delay, 0.01))

    async def is_disconnected():
        """测试期间保持 SSE 客户端连接。"""
        return False

    monkeypatch.setattr(asyncio, "sleep", fast_sleep)
    response = await system_endpoint.get_logging(
        request=SimpleNamespace(is_disconnected=is_disconnected),
        length=10,
        logfile="moviepilot.log",
        _=SimpleNamespace(id=1, name="admin", is_superuser=True),
    )
    stream = response.body_iterator

    async def read_frame() -> str:
        """有界读取下一帧，防止生成器静默停顿时测试挂死。"""
        return await asyncio.wait_for(stream.__anext__(), 1)

    try:
        assert await read_frame() == "data: seed\n\n"
        await original_sleep(0.1)

        log_file.rename(isolated_log_path / "moviepilot.log.1")
        log_file.write_text("rotated\n", encoding="utf-8")

        assert await read_frame() == "data: rotated\n\n"
    finally:
        await stream.aclose()


def test_download_moviepilot_logs_packages_latest_ten_log_files(isolated_log_path):
    """传入 moviepilot 时下载主程序滚动日志，最多打包 10 个文件。"""
    for index in range(12):
        (isolated_log_path / f"moviepilot.log.{index}").write_text(f"old-{index}", encoding="utf-8")
    (isolated_log_path / "moviepilot.log").write_text("current", encoding="utf-8")
    (isolated_log_path / "moviepilot.txt").write_text("ignored", encoding="utf-8")

    response = asyncio.run(system_endpoint.download_logging(name="moviepilot", _=SimpleNamespace()))
    body = asyncio.run(_read_streaming_body(response))

    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        names = archive.namelist()

    moviepilot_zip_root = response.headers["Content-Disposition"].split('filename="', 1)[1].removesuffix('.zip"')
    assert response.media_type == "application/zip"
    assert 'filename="moviepilot-logs-' in response.headers["Content-Disposition"]
    assert "moviepilot-moviepilot-logs" not in response.headers["Content-Disposition"]
    assert len(names) == 10
    assert f"{moviepilot_zip_root}/moviepilot.log" in names
    assert "moviepilot.log" not in names
    assert "moviepilot.txt" not in names




def test_download_log_zip_generation_runs_outside_event_loop_thread(monkeypatch, isolated_log_path):
    """日志压缩 I/O 必须离开事件循环线程执行，避免大日志下载阻塞其他请求。"""
    (isolated_log_path / "moviepilot.log").write_text("current", encoding="utf-8")
    event_loop_thread = threading.current_thread().name
    write_threads = []
    original_write = zipfile.ZipFile.write

    def capture_write_thread(self, filename, arcname=None, compress_type=None, compresslevel=None):
        """记录实际 zip 写入线程，并保持原始 ZipFile.write 行为。"""
        write_threads.append(threading.current_thread().name)
        return original_write(
            self,
            filename,
            arcname=arcname,
            compress_type=compress_type,
            compresslevel=compresslevel,
        )

    monkeypatch.setattr(zipfile.ZipFile, "write", capture_write_thread)

    response = asyncio.run(system_endpoint.download_logging(name="moviepilot", _=SimpleNamespace()))
    body = asyncio.run(_read_streaming_body(response))

    assert body
    assert write_threads
    assert all(thread_name != event_loop_thread for thread_name in write_threads)


async def _read_streaming_body(response) -> bytes:
    """读取 StreamingResponse 内容，便于断言 zip 文件条目。"""
    return b"".join([chunk async for chunk in response.body_iterator])
