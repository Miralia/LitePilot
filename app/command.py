import copy
import threading
import traceback
from typing import Any, Union, Dict, Optional

from app.chain import ChainBase
from app.chain.download import DownloadChain
from app.chain.system import SystemChain
from app.chain.transfer import TransferChain
from app.core.event import Event as ManagerEvent, eventmanager
from app.helper.message import MessageHelper
from app.helper.thread import ThreadHelper
from app.log import logger
from app.scheduler import Scheduler
from app.schemas import Notification
from app.schemas.types import EventType, MessageChannel
from app.utils.object import ObjectUtils
from app.utils.singleton import Singleton


class CommandChain(ChainBase):
    pass


def _finish_command_processing_status(status: Optional[dict], user_id: Optional[str] = None) -> None:
    """
    命令执行完成后通过消息模块收口渠道处理状态。
    """
    if not status:
        return
    CommandChain().finish_message_processing_status(
        status=status,
        userid=user_id,
    )


class Command(metaclass=Singleton):
    """
    全局命令管理，消费事件
    """

    def __init__(self):
        super().__init__()
        # 注册的命令集合
        self._registered_commands = {}
        # 所有命令集合
        self._commands = {}
        # 内建命令集合
        self._preset_commands = {
            "/mediaserver_sync": {
                "id": "mediaserver_sync",
                "type": "scheduler",
                "description": "同步媒体服务器",
                "category": "管理",
            },
            "/downloading": {
                "func": DownloadChain().remote_downloading,
                "description": "正在下载",
                "category": "管理",
                "data": {},
            },
            "/transfer": {
                "id": "transfer",
                "type": "scheduler",
                "description": "下载文件整理",
                "category": "管理",
            },
            "/redo": {
                "func": TransferChain().remote_transfer,
                "description": "手动整理",
                "data": {},
            },
            "/clear_cache": {
                "func": SystemChain().remote_clear_cache,
                "description": "清理缓存",
                "category": "管理",
                "data": {},
            },
            "/restart": {
                "func": SystemChain().restart,
                "description": "重启系统",
                "category": "管理",
                "data": {},
            },
            "/version": {
                "func": SystemChain().version,
                "description": "当前版本",
                "category": "管理",
                "data": {},
            },
        }
        # 初始化锁
        self._rlock = threading.RLock()
        # 定时服务管理
        self.scheduler = Scheduler()
        # 消息管理器
        self.messagehelper = MessageHelper()
        # 初始化命令
        self.init_commands()

    def init_commands(self) -> None:
        """
        初始化菜单命令
        """
        # 使用线程池提交后台任务，避免引起阻塞
        ThreadHelper().submit(self.__init_commands_background)

    def __init_commands_background(self) -> None:
        """
        后台初始化菜单命令
        """
        try:
            with self._rlock:
                logger.debug("Acquired lock for initializing commands in background.")
                self._commands = dict(self._preset_commands)

                initial_commands = self.__build_register_commands()
                logger.debug(f"Registering initial command count: {len(initial_commands)}")

                if not initial_commands:
                    logger.debug("Commands are empty, skipping registration.")
                    return

                # 对比调整后的命令与当前命令
                if initial_commands != self._registered_commands:
                    self._registered_commands = initial_commands
                    CommandChain().register_commands(commands=initial_commands)
                else:
                    logger.debug("Command set unchanged, skipping broadcast registration.")
        except Exception as e:
            logger.error(
                f"Error occurred during command initialization in background: {e}",
                exc_info=True,
            )

    def __build_register_commands(self) -> dict:
        """
        构建需要注册到消息渠道的菜单命令。
        """

        def add_commands(source, command_type):
            """
            添加命令集合
            """
            for cmd, command in source.items():
                if not command.get("show", True):
                    continue

                command_data = {
                    "type": command_type,
                    "description": command.get("description"),
                    "category": command.get("category"),
                }
                commands[cmd] = command_data

        # 初始化命令字典
        commands: Dict[str, dict] = {}
        add_commands(self._preset_commands, "preset")

        return commands


    def __run_command(
        self,
        command: Dict[str, any],
        data_str: Optional[str] = "",
        channel: MessageChannel = None,
        source: Optional[str] = None,
        userid: Union[str, int] = None,
    ):
        """
        运行定时服务
        """
        if command.get("type") == "scheduler":
            # 定时服务
            if userid:
                CommandChain().post_message(
                    Notification(
                        channel=channel,
                        source=source,
                        title=f"开始执行 {command.get('description')} ...",
                        userid=userid,
                    )
                )

            # 执行定时任务
            self.scheduler.start(job_id=command.get("id"))

            if userid:
                CommandChain().post_message(
                    Notification(
                        channel=channel,
                        source=source,
                        title=f"{command.get('description')} 执行完成",
                        userid=userid,
                    )
                )
        else:
            # 命令
            cmd_data = copy.deepcopy(command["data"]) if command.get("data") else {}
            args_num = ObjectUtils.arguments(command["func"])
            if args_num > 0:
                if cmd_data:
                    # 有内置参数直接使用内置参数
                    data = cmd_data.get("data") or {}
                    data["channel"] = channel
                    data["source"] = source
                    data["user"] = userid
                    if data_str:
                        data["arg_str"] = data_str
                    cmd_data["data"] = data
                    command["func"](**cmd_data)
                elif args_num == 3:
                    # 没有输入参数，只输入渠道来源、用户ID和消息来源
                    command["func"](channel, userid, source)
                elif args_num > 3:
                    # 多个输入参数：用户输入、用户ID
                    command["func"](data_str, channel, userid, source)
            else:
                # 没有参数
                command["func"]()

    def get_commands(self):
        """
        获取命令列表
        """
        if not self._commands:
            with self._rlock:
                if not self._commands:
                    self._commands = dict(self._preset_commands)
        return self._commands

    def get(self, cmd: str) -> Any:
        """
        获取命令
        """
        return self._commands.get(cmd, {})

    def execute(
        self,
        cmd: str,
        data_str: Optional[str] = "",
        channel: MessageChannel = None,
        source: Optional[str] = None,
        userid: Union[str, int] = None,
    ) -> None:
        """
        执行命令
        """
        command = self.get(cmd)
        if command:
            try:
                if userid:
                    logger.info(
                        f"用户 {userid} 开始执行：{command.get('description')} ..."
                    )
                else:
                    logger.info(f"开始执行：{command.get('description')} ...")

                # 执行命令
                self.__run_command(
                    command,
                    data_str=data_str,
                    channel=channel,
                    source=source,
                    userid=userid,
                )

                if userid:
                    logger.info(f"用户 {userid} {command.get('description')} 执行完成")
                else:
                    logger.info(f"{command.get('description')} 执行完成")
            except Exception as err:
                logger.error(
                    f"执行命令 {cmd} 出错：{str(err)} - {traceback.format_exc()}"
                )
                self.messagehelper.put(
                    title=f"执行命令 {cmd} 出错", message=str(err)
                )

    @eventmanager.register(EventType.CommandExcute)
    def command_event(self, event: ManagerEvent) -> None:
        """
        注册命令执行事件
        event_data: {
            "cmd": "/xxx args"
        }
        """
        # 命令参数
        event_str = event.event_data.get("cmd")
        # 消息渠道
        event_channel = event.event_data.get("channel")
        # 消息来源
        event_source = event.event_data.get("source")
        # 消息用户
        event_user = event.event_data.get("user")
        try:
            if event_str:
                cmd = event_str.split()[0]
                args = " ".join(event_str.split()[1:])
                if self.get(cmd):
                    self.execute(
                        cmd=cmd,
                        data_str=args,
                        channel=event_channel,
                        source=event_source,
                        userid=event_user,
                    )
        finally:
            _finish_command_processing_status(
                event.event_data.get("processing_status"),
                user_id=event_user,
            )

    @eventmanager.register(EventType.ModuleReload)
    def module_reload_event(self, _: ManagerEvent) -> None:
        """
        注册模块重载事件
        """
        # 发生模块重载时，重新注册命令
        self.init_commands()
