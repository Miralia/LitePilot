import threading
import time
import traceback
from typing import Any, Optional, Union, Tuple, List

import qbittorrentapi
from qbittorrentapi import TorrentDictionary, TorrentFilesList
from qbittorrentapi.client import Client
from qbittorrentapi.transfer import TransferInfoDictionary

from app.log import logger
from app.utils.string import StringUtils


class Qbittorrent:
    """
    qbittorrent下载器
    """
    def __init__(self, host: Optional[str] = None, port: int = None,
                 username: Optional[str] = None, password: Optional[str] = None,
                 apikey: Optional[str] = None,
                 incomplete_files_ext: Optional[bool] = True,
                 **kwargs):
        """
        若不设置参数，则创建配置文件设置的下载器
        """
        self._client_lock = threading.RLock()
        self._client_ready = threading.Event()
        self._client_thread: Optional[threading.Thread] = None
        self._qbc: Optional[Client] = None
        self._client_generation = 0
        self._close_requested = False
        if host and port:
            self._host, self._port = host, port
        elif host:
            self._host, self._port = StringUtils.get_domain_address(address=host, prefix=True)
        else:
            logger.error("Qbittorrent配置不完整！")
            self._client_ready.set()
            return
        self._username = username
        self._password = password
        self._apikey = str(apikey or "").strip() or None
        self._incomplete_files_ext = incomplete_files_ext
        self._client_generation = 1
        initial_generation = self._client_generation
        self._client_thread = threading.Thread(
            target=self._bootstrap_client,
            args=(initial_generation,),
            daemon=True,
        )
        self._client_thread.start()

    @property
    def qbc(self) -> Optional[Client]:
        """
        qbittorrent 客户端
        """
        self._client_ready.wait()
        return self._qbc

    @qbc.setter
    def qbc(self, value: Optional[Client]):
        self._qbc = value

    @staticmethod
    def __close_client(client: Optional[Client]):
        """
        关闭 qbittorrent 客户端持有的本地 HTTP session
        """
        if not client:
            return
        try:
            # SDK 未提供公开的本地 close；该重置入口只关闭已建 session，不会发起网络请求
            close_session = getattr(client, "_trigger_session_initialization", None)
            if callable(close_session):
                close_session()
        except Exception as err:
            logger.debug(f"关闭 qbittorrent HTTP session 失败：{err}")

    def _finish_connect(self, generation: int, client: Optional[Client]):
        """
        安装或回收一次连接结果
        """
        clients_to_close = []
        with self._client_lock:
            if self._close_requested or generation != self._client_generation:
                clients_to_close.append(client)
            else:
                if self._qbc is not client:
                    clients_to_close.append(self._qbc)
                self._qbc = client
            if generation == self._client_generation or self._close_requested:
                self._client_ready.set()
        for client_to_close in clients_to_close:
            self.__close_client(client_to_close)

    def _connect_and_install(self, generation: int):
        """
        执行一次连接并按代际安装结果
        """
        with self._client_lock:
            if self._close_requested or generation != self._client_generation:
                return
        client = None
        try:
            client = self.__login_qbittorrent()
        except Exception as err:
            logger.error(f"初始化 qbittorrent 连接出错：{err}")
        self._finish_connect(generation, client)

    def _bootstrap_client(self, generation: int):
        """
        后台初始化下载器连接，避免外部服务缓慢时阻塞应用启动
        """
        self._connect_and_install(generation)

    def close(self):
        """
        关闭下载器连接，迟到完成的登录结果会被立即回收
        """
        with self._client_lock:
            self._close_requested = True
            client = self._qbc
            self._qbc = None
            self._client_ready.set()
        self.__close_client(client)

    def __use_api_key_auth(self) -> bool:
        return bool(self._apikey)

    @staticmethod
    def __sync_incomplete_file_suffix(qbt: Client, enabled: bool) -> None:
        """
        同步未完成文件后缀开关，避免监控流程提前整理仍在下载的媒体文件。
        """
        try:
            preferences = qbt.app_preferences() or {}
            if isinstance(preferences, dict) and preferences.get("incomplete_files_ext") is enabled:
                return
            qbt.app_set_preferences({"incomplete_files_ext": enabled})
            action = "开启" if enabled else "关闭"
            logger.info(f"已{action} qbittorrent 未完成文件追加 .!qB 后缀")
        except Exception as err:
            logger.warning(f"同步 qbittorrent 未完成文件后缀失败：{str(err)}")

    def is_inactive(self) -> bool:
        """
        判断是否需要重连
        """
        if not self._host or not self._port:
            return False
        return True if not self.qbc else False

    def reconnect(self):
        """
        重连
        """
        with self._client_lock:
            if self._close_requested:
                return
            self._client_generation += 1
            generation = self._client_generation
            self._client_ready.clear()
        self._connect_and_install(generation)

    def __login_qbittorrent(self) -> Optional[Client]:
        """
        连接qbittorrent
        :return: qbittorrent对象
        """
        if not self._host or not self._port:
            return None
        try:
            # 登录
            logger.info(f"正在连接 qbittorrent：{self._host}:{self._port}")
            qbt = qbittorrentapi.Client(host=self._host,
                                        port=self._port,
                                        username=self._username,
                                        password=self._password,
                                        EXTRA_HEADERS={"Authorization": f"Bearer {self._apikey}"}
                                        if self.__use_api_key_auth() else None,
                                        VERIFY_WEBUI_CERTIFICATE=False,
                                        REQUESTS_ARGS={'timeout': (15, 60)})
            try:
                if self.__use_api_key_auth():
                    qbt.app_version()
                else:
                    qbt.auth_log_in()
            except Exception as e:
                if e.__class__.__name__ in {"LoginFailed", "Forbidden403Error", "Unauthorized401Error"}:
                    error_hint = "请检查 API Key 是否正确" if self.__use_api_key_auth() else "请检查用户名和密码是否正确"
                    logger.error(f"qbittorrent 登录失败：{str(e).strip() or error_hint}")
                    return None
                stack_trace = "".join(traceback.format_exception(None, e, e.__traceback__))[:2000]
                logger.error(f"qbittorrent 登录失败：{str(e)}\n{stack_trace}")
                return None
            self.__sync_incomplete_file_suffix(qbt, enabled=bool(self._incomplete_files_ext))
            return qbt
        except Exception as err:
            logger.error(f"qbittorrent 连接出错：{str(err)}")
            return None

    def get_torrents(self, ids: Optional[Union[str, list]] = None,
                     status: Optional[str] = None,
                     tags: Optional[Union[str, list]] = None) -> Tuple[List[TorrentDictionary], bool]:
        """
        获取种子列表
        return: 种子列表, 是否发生异常
        """
        if not self.qbc:
            return [], True
        try:
            torrents = self.qbc.torrents_info(torrent_hashes=ids,
                                              status_filter=status)
            if tags:
                results = []
                if not isinstance(tags, list):
                    tags = tags.split(',')
                try:
                    for torrent in torrents:
                        torrent_tags = [str(tag).strip() for tag in torrent.get("tags").split(',')]
                        if set(tags).issubset(set(torrent_tags)):
                            results.append(torrent)
                finally:
                    torrents.clear()
                    del torrents
                return results, False
            return torrents or [], False
        except Exception as err:
            logger.error(f"获取种子列表出错：{str(err)}")
            return [], True

    def get_completed_torrents(self, ids: Union[str, list] = None,
                               tags: Union[str, list] = None) -> Optional[List[TorrentDictionary]]:
        """
        获取已完成的种子
        return: 种子列表, 如发生异常则返回None
        """
        if not self.qbc:
            return None
        torrents, error = self.get_torrents(status="completed", ids=ids, tags=tags)
        if error:
            return None
        ret_torrents = []
        for torrent in torrents or []:
            state = str(torrent.get("state") or "").strip().lower()
            progress = torrent.get("progress") or 0
            amount_left = torrent.get("amount_left") or 0
            if (
                    progress >= 1
                    and amount_left <= 0
                    and state not in {
                        "allocating",
                        "checkingdl",
                        "checkingup",
                        "downloading",
                        "error",
                        "forceddl",
                        "missingfiles",
                        "metadl",
                        "moving",
                        "queueddl",
                        "stalleddl",
                        "unknown",
                    }
            ):
                ret_torrents.append(torrent)
        return ret_torrents

    def get_downloading_torrents(self, ids: Union[str, list] = None,
                                 tags: Union[str, list] = None) -> Optional[List[TorrentDictionary]]:
        """
        获取正在下载的种子
        return: 种子列表, 如发生异常则返回None
        """
        if not self.qbc:
            return None
        torrents, error = self.get_torrents(ids=ids,
                                            status="downloading",
                                            tags=tags)
        return None if error else torrents or []

    def set_torrents_tag(self, ids: Union[str, list], tags: list):
        """
        设置种子状态为已整理，以及是否强制做种
        """
        if not self.qbc:
            return
        try:
            # 打标签
            self.qbc.torrents_add_tags(tags=tags, torrent_hashes=ids)
        except Exception as err:
            logger.error(f"设置种子Tag出错：{str(err)}")

    def stop_torrents(self, ids: Union[str, list]) -> bool:
        """
        暂停种子
        """
        if not self.qbc:
            return False
        try:
            self.qbc.torrents_pause(torrent_hashes=ids)
            return True
        except Exception as err:
            logger.error(f"暂停种子出错：{str(err)}")
            return False

    def delete_torrents(self, delete_file: bool, ids: Union[str, list]) -> bool:
        """
        删除种子
        """
        if not self.qbc:
            return False
        if not ids:
            return False
        try:
            self.qbc.torrents_delete(delete_files=delete_file, torrent_hashes=ids)
            return True
        except Exception as err:
            logger.error(f"删除种子出错：{str(err)}")
            return False

    def get_files(self, tid: str, retry: int = 1, interval: float = 0) -> Optional[TorrentFilesList]:
        """
        获取种子文件清单
        :param tid: 种子Hash
        :param retry: 最多尝试次数
        :param interval: 重试间隔，单位秒
        :return: 种子文件清单
        """
        if not self.qbc:
            return None
        last_error = None
        retry_times = max(retry, 1)
        for index in range(retry_times):
            try:
                torrent_files = self.qbc.torrents_files(torrent_hash=tid)
                if torrent_files:
                    return torrent_files
            except Exception as err:
                last_error = err
            if index < retry_times - 1 and interval:
                time.sleep(interval)
        if last_error:
            logger.error(f"获取种子文件列表出错：{str(last_error)}")
        return None


    def transfer_info(self) -> Optional[TransferInfoDictionary]:
        """
        获取传输信息
        """
        if not self.qbc:
            return None
        try:
            return self.qbc.transfer_info()
        except Exception as err:
            logger.error(f"获取传输信息出错：{str(err)}")
            return None
