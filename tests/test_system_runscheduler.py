"""运行定时服务 API 的提交结果语义测试。"""

from app.api.endpoints import system as system_endpoint


def test_run_scheduler_returns_failure_when_job_is_not_accepted(monkeypatch):
    """定时服务不存在或运行中时，API 不得误报提交成功。"""

    class FakeScheduler:
        """拒绝本次执行的调度器测试替身。"""

        def start(self, job_id):
            """拒绝所有任务。"""
            return False

    monkeypatch.setattr(system_endpoint, "Scheduler", FakeScheduler)

    result = system_endpoint.run_scheduler(jobid="missing", _=None)

    assert result.success is False
    assert result.message == "定时服务不存在或正在运行！"


def test_run_scheduler_returns_success_when_job_is_accepted(monkeypatch):
    """定时服务接受执行请求后，API 才返回提交成功。"""

    class FakeScheduler:
        """接受本次执行的调度器测试替身。"""

        def start(self, job_id):
            """接受所有任务。"""
            return True

    monkeypatch.setattr(system_endpoint, "Scheduler", FakeScheduler)

    result = system_endpoint.run_scheduler(jobid="download_file_sync", _=None)

    assert result.success is True
