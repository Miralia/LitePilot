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
    AUTO_UPDATE_ENABLED_VALUES = {"release", "dev"}
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
    __one_shot_update_flag_file = settings.TEMP_PATH / "moviepilot.pending_update"

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
    def can_restart() -> bool:
        """
        判断是否可以内部重启
        """
        return SystemHelper._is_local_cli_managed()

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
    def is_auto_update_enabled(mode: Optional[str] = None) -> bool:
        """
        判断给定模式或当前配置是否启用了启动时自动升级。
        """
        effective_mode = (
            SystemHelper.get_auto_update_mode()
            if mode is None
            else SystemHelper.normalize_auto_update_mode(mode)
        )
        return effective_mode in SystemHelper.AUTO_UPDATE_ENABLED_VALUES

    @staticmethod
    def queue_one_shot_update(mode: str = "release") -> Tuple[bool, str]:
        """
        写入一次性升级标记，供重启后的启动流程消费。
        """
        effective_mode = SystemHelper.normalize_auto_update_mode(mode)
        if effective_mode not in SystemHelper.AUTO_UPDATE_ENABLED_VALUES:
            return False, "升级模式仅支持 release 或 dev"

        try:
            SystemHelper.__one_shot_update_flag_file.parent.mkdir(
                parents=True, exist_ok=True
            )
            SystemHelper.__one_shot_update_flag_file.write_text(
                effective_mode, encoding="utf-8"
            )
            logger.info(f"已写入一次性升级标记，模式: {effective_mode}")
            return True, ""
        except OSError as err:
            logger.error(f"写入一次性升级标记失败: {err}")
            return False, f"写入一次性升级标记失败：{err}"

    @staticmethod
    def consume_one_shot_update_mode() -> Optional[str]:
        """
        读取并清除一次性升级标记，避免后续启动重复执行。
        """
        path = SystemHelper.__one_shot_update_flag_file
        if not path.exists():
            return None

        try:
            raw_mode = path.read_text(encoding="utf-8", errors="replace")
        except OSError as err:
            logger.warning(f"读取一次性升级标记失败: {err}")
            raw_mode = ""

        try:
            path.unlink(missing_ok=True)
        except OSError as err:
            logger.warning(f"删除一次性升级标记失败: {err}")

        effective_mode = SystemHelper.normalize_auto_update_mode(raw_mode)
        if effective_mode not in SystemHelper.AUTO_UPDATE_ENABLED_VALUES:
            if raw_mode:
                logger.warning(f"忽略无效的一次性升级模式: {raw_mode}")
            return None

        logger.info(f"检测到一次性升级标记，模式: {effective_mode}")
        return effective_mode

    @staticmethod
    def clear_one_shot_update_flag() -> None:
        """
        删除一次性升级标记。
        """
        try:
            SystemHelper.__one_shot_update_flag_file.unlink(missing_ok=True)
        except OSError as err:
            logger.warning(f"删除一次性升级标记失败: {err}")

    @staticmethod
    def _spawn_local_restart_helper() -> None:
        helper_code = (
            "import os, subprocess, sys, time;"
            "time.sleep(1.0);"
            "cmd=[sys.executable, '-m', 'app.cli', 'restart', '--force', '--stop-timeout', '30', '--start-timeout', '60'];"
            "subprocess.run(cmd, cwd=os.environ.get('MOVIEPILOT_ROOT'), env=os.environ.copy(), check=False)"
        )
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
        logger.info(f"已创建本地 CLI 重启任务，辅助进程 PID: {process.pid}")

    @staticmethod
    def restart() -> Tuple[bool, str]:
        """
        执行本地 CLI 管理实例的重启操作。
        """
        if not SystemHelper._is_local_cli_managed():
            return False, "当前实例不是由 moviepilot CLI 启动，请使用 systemd 或外部进程管理器重启！"
        try:
            SystemHelper._spawn_local_restart_helper()
            os.kill(os.getpid(), signal.SIGTERM)
            return True, ""
        except Exception as err:
            logger.error(f"本地 CLI 重启失败: {str(err)}")
            return False, f"本地 CLI 重启失败：{str(err)}"

    @staticmethod
    def upgrade(mode: str = "release") -> Tuple[bool, str]:
        """
        触发升级并重启。

        - 已开启自动升级时，直接重启，沿用当前配置。
        - 未开启自动升级时，写入一次性升级标记，供下次启动时执行升级。
        """
        current_mode = SystemHelper.get_auto_update_mode()
        if SystemHelper.is_auto_update_enabled(current_mode):
            ret, msg = SystemHelper.restart()
            if not ret:
                return ret, msg
            if current_mode == "dev":
                return True, "已检测到自动升级模式 dev，正在重启并执行升级"
            return True, "已检测到自动升级已开启，正在重启并执行升级"

        queued, message = SystemHelper.queue_one_shot_update(mode)
        if not queued:
            return False, message

        ret, msg = SystemHelper.restart()
        if not ret:
            SystemHelper.clear_one_shot_update_flag()
            return ret, msg
        effective_mode = SystemHelper.normalize_auto_update_mode(mode)
        return True, f"已安排一次性 {effective_mode} 升级并重启"
