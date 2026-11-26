import json
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple

import psutil

from app.core.config import settings
from app.log import logger
from app.utils.mixins import ConfigReloadMixin


class SystemHelper(ConfigReloadMixin):
    """
    系统工具类，提供系统相关的操作和判断
    """
    CONFIG_WATCH = {
        "DEBUG",
        "LOG_LEVEL",
        "LOG_MAX_FILE_SIZE",
        "LOG_BACKUP_COUNT",
        "LOG_FILE_FORMAT",
        "LOG_CONSOLE_FORMAT",
    }

    __local_backend_runtime_file = settings.TEMP_PATH / "moviepilot.runtime.json"
    __local_restart_log_file = settings.LOG_PATH / "moviepilot.restart.stdout.log"

    def on_config_changed(self):
        """
        配置变更后刷新日志处理器。
        """
        logger.update_loggers()

    def get_reload_name(self):
        """
        返回支持热重载的配置名称。
        """
        return "日志设置"

    @staticmethod
    def _parse_systemd_unit_name(cgroup: str) -> Optional[str]:
        """
        从 cgroup 路径中解析当前进程所属的 systemd service 单元名。
        """
        for line in cgroup.splitlines():
            cgroup_path = line.split(":", 2)[-1].strip()
            for segment in reversed(cgroup_path.split("/")):
                if segment.endswith(".service") and len(segment) > len(".service"):
                    return segment
        return None

    @staticmethod
    def _systemd_unit_name() -> Optional[str]:
        """
        读取当前进程的 systemd service 单元名。
        """
        if os.name == "nt":
            return None
        try:
            cgroup = Path("/proc/self/cgroup").read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        return SystemHelper._parse_systemd_unit_name(cgroup)

    @staticmethod
    def can_restart() -> bool:
        """
        判断是否可以内部重启
        """
        return SystemHelper._is_local_cli_managed() or SystemHelper._systemd_unit_name() is not None

    @staticmethod
    def _load_runtime_file(path: Path) -> Optional[dict]:
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _is_local_cli_managed() -> bool:
        runtime = SystemHelper._load_runtime_file(SystemHelper.__local_backend_runtime_file)
        if not runtime:
            return False

        pid = runtime.get("pid")
        create_time = runtime.get("create_time")
        if not pid:
            return False

        try:
            pid = int(pid)
        except (TypeError, ValueError):
            return False

        if pid != os.getpid():
            return False

        if create_time is None:
            return True

        try:
            current_process = psutil.Process(os.getpid())
            return abs(current_process.create_time() - float(create_time)) <= 2
        except (psutil.Error, TypeError, ValueError):
            return False

    @staticmethod
    def normalize_auto_update_mode(mode: Optional[str]) -> str:
        """
        统一自动升级模式值，兼容历史 true 表示 release。
        """
        normalized = str(mode or "").strip().lower()
        return "release" if normalized == "true" else normalized

    @staticmethod
    def get_auto_update_mode() -> str:
        """
        获取当前配置中的自动升级模式。
        """
        return SystemHelper.normalize_auto_update_mode(
            settings.MOVIEPILOT_AUTO_UPDATE
        )

    @staticmethod
    def _spawn_restart_helper_process(helper_code: str, description: str) -> None:
        """
        以独立会话启动延迟重启辅助进程，并把输出写入重启日志。
        """
        env = os.environ.copy()
        env["MOVIEPILOT_ROOT"] = str(settings.ROOT_PATH)
        env["PYTHONUNBUFFERED"] = "1"

        SystemHelper.__local_restart_log_file.parent.mkdir(parents=True, exist_ok=True)
        with SystemHelper.__local_restart_log_file.open("a", encoding="utf-8") as log_handle:
            kwargs = {
                "cwd": str(settings.ROOT_PATH),
                "stdout": log_handle,
                "stderr": subprocess.STDOUT,
                "stdin": subprocess.DEVNULL,
                "close_fds": True,
                "env": env,
            }
            if os.name == "nt":
                kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
            else:
                kwargs["start_new_session"] = True
            process = subprocess.Popen([sys.executable, "-c", helper_code], **kwargs)
        logger.info(f"已创建{description}，辅助进程 PID: {process.pid}")

    @staticmethod
    def _spawn_local_restart_helper() -> None:
        """
        启动本地 CLI 重启辅助进程。
        """
        helper_code = (
            "import os, subprocess, sys, time;"
            "time.sleep(1.0);"
            "cmd=[sys.executable, '-m', 'app.cli', 'restart', '--force', '--stop-timeout', '30', '--start-timeout', '60'];"
            "subprocess.run(cmd, cwd=os.environ.get('MOVIEPILOT_ROOT'), env=os.environ.copy(), check=False)"
        )
        SystemHelper._spawn_restart_helper_process(helper_code, "本地 CLI 重启任务")

    @staticmethod
    def _spawn_systemd_restart_helper(unit_name: str) -> None:
        """
        启动 systemd 重启辅助进程，延迟排队以避免当前响应被提前终止。
        """
        unit_literal = json.dumps(unit_name)
        helper_code = (
            "import subprocess, time;"
            "time.sleep(1.0);"
            f"subprocess.run(['systemctl', '--no-block', 'restart', {unit_literal}], check=False)"
        )
        SystemHelper._spawn_restart_helper_process(helper_code, "systemd 重启任务")

    @staticmethod
    def restart() -> Tuple[bool, str]:
        """
        执行本地 CLI 或 systemd 管理实例的重启操作。
        """
        try:
            if SystemHelper._is_local_cli_managed():
                SystemHelper._spawn_local_restart_helper()
                os.kill(os.getpid(), signal.SIGTERM)
                return True, ""

            unit_name = SystemHelper._systemd_unit_name()
            if unit_name:
                SystemHelper._spawn_systemd_restart_helper(unit_name)
                return True, ""
            return False, "当前实例不是由 moviepilot CLI 或 systemd 管理，请使用外部进程管理器重启！"
        except Exception as err:
            logger.error(f"系统重启失败: {str(err)}")
            return False, f"系统重启失败：{str(err)}"
