import json
import re
import shutil
from pathlib import Path
from typing import Union, Optional

from app.chain import ChainBase
from app.core.config import settings
from app.helper.system import SystemHelper
from app.log import logger
from app.schemas import Notification, MessageChannel
from app.utils.http import RequestUtils
from version import APP_VERSION


class SystemChain(ChainBase):
    """
    系统级处理链
    """

    _restart_file = "__system_restart__"

    def remote_clear_cache(self, channel: MessageChannel, userid: Union[int, str], source: Optional[str] = None):
        """
        清理系统缓存
        """
        self.clear_cache()
        self.post_message(Notification(
            channel=channel,
            source=source,
            title=f"缓存清理完成！",
            userid=userid,
            save_history=False))

    def restart(self, channel: MessageChannel, userid: Union[int, str], source: Optional[str] = None):
        """
        重启系统
        """
        if not SystemHelper.can_restart():
            if channel and userid:
                self.post_message(Notification(
                    channel=channel,
                    source=source,
                    title="当前运行环境不支持内建重启，请使用 systemd 或外部进程管理器重启！",
                    userid=userid,
                    save_history=False))
            return
        if channel and userid:
            self.post_message(Notification(
                channel=channel,
                source=source,
                title="系统正在重启，请耐心等候！",
                userid=userid,
                save_history=False))
            # 保存重启信息
            self.save_cache({
                "channel": channel.value,
                "userid": userid
            }, self._restart_file)
        # 重启
        success, message = SystemHelper.restart()
        if not success and channel and userid:
            self.remove_cache(self._restart_file)
            self.post_message(Notification(
                channel=channel,
                source=source,
                title=f"系统重启失败：{message or '请检查运行环境与日志'}",
                userid=userid,
                save_history=False))



    def __get_version_message(self) -> str:
        """
        获取版本信息文本（仅本地版本，不再查询远程发布）
        """
        server_local_version = self.get_server_local_version()
        front_local_version = self.get_frontend_version()
        return (
            f"当前后端版本：{server_local_version}\n"
            f"当前前端版本：{front_local_version}"
        )

    def version(self, channel: MessageChannel, userid: Union[int, str], source: Optional[str] = None):
        """
        查看当前版本
        """
        self.post_message(Notification(
            channel=channel,
            source=source,
            title=self.__get_version_message(),
            userid=userid,
            save_history=False))

    def restart_finish(self):
        """
        如通过交互命令重启，
        重启完发送msg
        """
        # 重启消息
        restart_channel = self.load_cache(self._restart_file)
        if restart_channel is None:
            return
        if not isinstance(restart_channel, dict):
            try:
                restart_channel = json.loads(restart_channel)
            except (TypeError, json.JSONDecodeError):
                restart_channel = None
        if isinstance(restart_channel, dict):
            channel = next(
                (channel for channel in MessageChannel.__members__.values() if
                 channel.value == restart_channel.get('channel')), None)
            userid = restart_channel.get('userid')
        else:
            channel = None
            userid = None
        valid_userid = (
            isinstance(userid, str) and bool(userid)
        ) or (
            isinstance(userid, int) and not isinstance(userid, bool)
        )
        if channel is None or not valid_userid:
            logger.warning("重启完成通知缓存无效，已清理")
            self.remove_cache(self._restart_file)
            return

        # 发送重启完成msg
        title = self.__get_version_message()
        try:
            self.post_message(Notification(
                channel=channel,
                title=f"系统已重启完成！\n{title}",
                userid=userid,
                save_history=False))
        except Exception as err:
            logger.error(f"发送重启完成通知失败：{err}")
            return
        self.remove_cache(self._restart_file)

    @staticmethod
    def get_server_local_version():
        """
        查看当前版本
        """
        return APP_VERSION

    @staticmethod
    def get_frontend_version():
        """
        获取前端版本
        """
        version_file = Path(settings.FRONTEND_PATH) / "version.txt"
        if version_file.exists():
            try:
                with open(version_file, 'r', encoding='utf-8', errors='replace') as f:
                    version = str(f.read()).strip()
                return version
            except Exception as err:
                logger.debug(f"加载版本文件 {version_file} 出错：{str(err)}")
        return APP_VERSION
