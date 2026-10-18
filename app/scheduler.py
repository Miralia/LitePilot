import asyncio
import gc
import hashlib
import inspect
import json
import multiprocessing
import threading
import traceback
from datetime import datetime, timedelta
from typing import Callable, Optional, Dict, Any
from typing import List

import pytz
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.base import JobLookupError
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from app import schemas
from app.chain import ChainBase
from app.chain.mediaserver import MediaServerChain
from app.chain.downloadfilesync import DownloadFileSyncChain
from app.chain.mediacover import MediaCoverChain
from app.chain.transfer import TransferChain
from app.core.config import settings, global_vars
from app.core.event import Event, eventmanager
from app.db import SessionFactory
from app.db.models.downloadhistory import DownloadHistory, DownloadFiles
from app.db.models.message import Message
from app.db.models.transferhistory import TransferHistory
from app.db.systemconfig_oper import SystemConfigOper
from app.helper.image import WallpaperHelper
from app.helper.message import MessageHelper
from app.helper.progress import ProgressHelper
from app.helper.service import ServiceConfigHelper
from app.log import logger
from app.schemas import Notification, NotificationType
from app.schemas.types import EventType, SystemConfigKey
from app.utils.gc import get_memory_usage
from app.utils.mixins import ConfigReloadMixin
from app.utils.singleton import SingletonClass
from app.utils.timer import TimerUtils

lock = threading.Lock()
SCHEDULER_PROGRESS_PREFIX = "scheduler"


class SchedulerChain(ChainBase):
    """
    定时任务链，负责执行各类定时任务，包括数据清理等
    """
    # 每批处理的记录数，避免一次性删除过多数据导致性能问题
    DEFAULT_BATCH_SIZE = 500

    def cleanup(
            self,
            batch_size: Optional[int] = None,
            progress_callback: Optional[Callable[..., None]] = None,
    ) -> Dict[str, Any]:
        """
        按配置保留期执行分批清理。
        """
        started_at = datetime.now()
        batch_size = batch_size or self.DEFAULT_BATCH_SIZE
        if batch_size <= 0:
            batch_size = self.DEFAULT_BATCH_SIZE

        report: Dict[str, Any] = {
            "started_at": started_at.strftime("%Y-%m-%d %H:%M:%S"),
            "batch_size": batch_size,
            "enabled": bool(settings.DATA_CLEANUP_ENABLE),
            "tables": {},
            "total_deleted": 0,
        }

        if not settings.DATA_CLEANUP_ENABLE:
            report["skipped_reason"] = "disabled"
            logger.info("数据表清理总开关未开启，跳过执行")
            return report

        errors = []

        plans = self._build_cleanup_plans(started_at=started_at, batch_size=batch_size)
        total_plans = len(plans)
        if progress_callback:
            progress_callback(value=0, text="开始清理数据表 ...")

        with SessionFactory() as db:
            for plan_index, plan in enumerate(plans):
                name = plan["name"]
                retention_days = plan["retention_days"]
                if retention_days <= 0:
                    report["tables"][name] = {
                        "deleted": 0,
                        "batches": 0,
                        "cutoff": None,
                        "retention_days": retention_days,
                        "skipped": True,
                        "reason": "retention_days<=0",
                    }
                    if progress_callback:
                        progress_callback(
                            value=(plan_index + 1) / total_plans * 100,
                            text=f"数据表 {name} 跳过清理",
                        )
                    continue

                try:
                    if progress_callback:
                        progress_callback(
                            value=plan_index / total_plans * 100,
                            text=f"正在清理数据表 {name} ...",
                        )
                    table_report = self._cleanup_in_batches(
                        db=db,
                        table_name=name,
                        delete_batch=plan["handler"],
                    )
                    table_report["cutoff"] = plan["cutoff"]
                    table_report["retention_days"] = retention_days
                    report["tables"][name] = table_report
                    report["total_deleted"] += table_report["deleted"]
                except Exception as err:
                    errors.append(f"{name}: {str(err)}")
                    logger.error(f"数据表 {name} 清理失败：{str(err)}")
                    report["tables"][name] = {
                        "deleted": 0,
                        "batches": 0,
                        "cutoff": plan["cutoff"],
                        "retention_days": retention_days,
                        "error": str(err),
                    }
                finally:
                    if progress_callback:
                        progress_callback(
                            value=(plan_index + 1) / total_plans * 100,
                            text=f"数据表 {name} 清理处理完成",
                        )

        if errors:
            report["errors"] = errors
            logger.error(
                f"数据表清理部分失败：{json.dumps(report, ensure_ascii=False)}"
            )
            raise RuntimeError("；".join(errors))

        logger.info(f"数据表清理完成：{json.dumps(report, ensure_ascii=False)}")
        return report

    @staticmethod
    def _normalize_retention_days(retention_days: Any) -> int:
        try:
            normalized_days = int(retention_days or 0)
        except (TypeError, ValueError):
            return 0
        return max(normalized_days, 0)

    def _build_cleanup_plans(
            self,
            started_at: datetime,
            batch_size: int,
    ) -> List[Dict[str, Any]]:
        message_days = self._normalize_retention_days(settings.DATA_CLEANUP_MESSAGE_DAYS)
        download_history_days = self._normalize_retention_days(
            settings.DATA_CLEANUP_DOWNLOAD_HISTORY_DAYS
        )
        transfer_history_days = self._normalize_retention_days(
            settings.DATA_CLEANUP_TRANSFER_HISTORY_DAYS
        )

        message_cutoff = (
                started_at - timedelta(days=message_days)
        ).strftime("%Y-%m-%d")
        download_history_cutoff = (
                started_at - timedelta(days=download_history_days)
        ).strftime("%Y-%m-%d")
        transfer_history_cutoff = (
                started_at - timedelta(days=transfer_history_days)
        ).strftime("%Y-%m-%d")

        return [
            {
                "name": "message",
                "retention_days": message_days,
                "cutoff": message_cutoff,
                "handler": lambda db: Message.delete_before(
                    db=db,
                    before_time=message_cutoff,
                    limit=batch_size,
                ),
            },
            {
                "name": "downloadhistory",
                "retention_days": download_history_days,
                "cutoff": download_history_cutoff,
                "handler": lambda db: DownloadHistory.delete_before(
                    db=db,
                    before_time=download_history_cutoff,
                    limit=batch_size,
                ),
            },
            {
                "name": "downloadfiles",
                "retention_days": download_history_days,
                "cutoff": "follow-parent-history",
                "handler": lambda db: DownloadFiles.delete_orphans(
                    db=db,
                    limit=batch_size,
                ),
            },
            {
                "name": "transferhistory",
                "retention_days": transfer_history_days,
                "cutoff": transfer_history_cutoff,
                "handler": lambda db: TransferHistory.delete_before(
                    db=db,
                    before_time=transfer_history_cutoff,
                    limit=batch_size,
                ),
            },
        ]

    @staticmethod
    def _cleanup_in_batches(
            db: Session,
            table_name: str,
            delete_batch: Callable[[Session], int],
    ) -> Dict[str, int]:
        """
        循环执行单表分批删除，直到没有可删除数据。
        """
        total_deleted = 0
        batches = 0

        while True:
            deleted = delete_batch(db) or 0
            if deleted <= 0:
                break
            batches += 1
            total_deleted += deleted
            logger.info(
                f"数据表 {table_name} 清理第 {batches} 批完成，删除 {deleted} 条记录"
            )

        return {
            "deleted": total_deleted,
            "batches": batches,
        }


class Scheduler(ConfigReloadMixin, metaclass=SingletonClass):
    """
    定时任务管理
    """

    CONFIG_WATCH = {
        "DEV",
        "MEDIASERVER_SYNC_INTERVAL",
        SystemConfigKey.MediaServers.value,
        SystemConfigKey.DownloadFileSync.value,
        SystemConfigKey.LibraryCoverGenerator.value,
        "DATA_CLEANUP_ENABLE",
        "DATA_CLEANUP_MESSAGE_DAYS",
        "DATA_CLEANUP_DOWNLOAD_HISTORY_DAYS",
        "DATA_CLEANUP_TRANSFER_HISTORY_DAYS",
    }

    def __init__(self):
        # 定时服务
        self._scheduler = None
        # 退出事件
        self._event = threading.Event()
        # 锁
        self._lock = threading.RLock()
        # 各服务的运行状态
        self._jobs = {}
        # 初始化
        self.init()

    def on_config_changed(self) -> None:
        """
        配置变更后重新初始化定时服务。
        """
        self.init()

    def get_reload_name(self) -> str:
        """
        获取配置重载日志中的服务名称。
        """
        return "定时服务"

    @staticmethod
    def _get_mediaserver_sync_interval(
            mediaserver: schemas.MediaServerConf,
            default_interval: Optional[int],
    ) -> Optional[int]:
        """
        获取媒体服务器的有效同步间隔，未设置时回退旧全局配置。
        """
        interval = mediaserver.sync_interval
        if interval is None:
            interval = default_interval
        try:
            interval = int(interval)
        except (TypeError, ValueError):
            return None
        return interval if interval > 0 else None

    @classmethod
    def _build_mediaserver_sync_schedules(
            cls,
            mediaservers: List[schemas.MediaServerConf],
            default_interval: Optional[int],
    ) -> List[dict]:
        """
        构建已启用媒体服务器的独立自动同步任务描述。
        """
        schedules = []
        job_ids = set()
        for mediaserver in mediaservers:
            if not mediaserver or not mediaserver.enabled or not mediaserver.name:
                continue
            interval = cls._get_mediaserver_sync_interval(
                mediaserver=mediaserver,
                default_interval=default_interval,
            )
            if not interval:
                continue
            digest = hashlib.sha256(mediaserver.name.encode("utf-8")).hexdigest()[:12]
            job_id = f"mediaserver_sync_{digest}"
            if job_id in job_ids:
                continue
            job_ids.add(job_id)
            schedules.append(
                {
                    "id": job_id,
                    "name": f"同步媒体服务器 - {mediaserver.name}",
                    "server": mediaserver.name,
                    "interval": interval,
                }
            )
        return schedules

    @staticmethod
    def _get_progress_key(job_id: str) -> str:
        """
        获取定时服务进度缓存键。
        """
        return f"{SCHEDULER_PROGRESS_PREFIX}:{job_id}"

    @staticmethod
    def _format_time(value: Optional[datetime] = None) -> str:
        """
        格式化进度事件时间。
        """
        return (value or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")

    def init(self) -> None:
        """
        初始化定时服务
        """

        # 停止定时服务
        self.stop()

        # 调试模式不启动定时服务
        if settings.DEV:
            return

        with lock:
            # 各服务的运行状态
            mediaserver_chain = MediaServerChain()
            self._jobs = {
                "mediaserver_sync": {
                    "name": "同步媒体服务器",
                    "func": mediaserver_chain.sync,
                    "running": False,
                },
                "transfer": {
                    "name": "下载文件整理",
                    "func": TransferChain().process,
                    "running": False,
                },
                "download_file_sync": {
                    "name": "下载文件同步",
                    "func": DownloadFileSyncChain().process,
                    "running": False,
                },
                "library_cover_generator": {
                    "name": "媒体库封面生成",
                    "func": MediaCoverChain().process,
                    "running": False,
                },
                "clear_cache": {
                    "name": "缓存清理",
                    "func": self.clear_cache,
                    "running": False,
                },
                "data_cleanup": {
                    "name": "数据表清理",
                    "func": SchedulerChain().cleanup,
                    "running": False,
                },
                "scheduler_job": {
                    "name": "公共定时服务",
                    "func": SchedulerChain().scheduler_job,
                    "running": False,
                },
                "random_wallpager": {
                    "name": "壁纸缓存",
                    "func": WallpaperHelper().get_wallpapers,
                    "running": False,
                },
                "full_gc": {
                    "name": "主动内存回收",
                    "func": self.full_gc,
                    "running": False,
                },
            }

            # 创建定时服务
            self._scheduler = BackgroundScheduler(
                timezone=settings.TZ,
                executors={"default": ThreadPoolExecutor(settings.CONF.scheduler)},
            )

            # 按媒体服务器分别注册自动同步任务
            mediaserver_schedules = self._build_mediaserver_sync_schedules(
                mediaservers=ServiceConfigHelper.get_mediaserver_configs(),
                default_interval=settings.MEDIASERVER_SYNC_INTERVAL,
            )
            for mediaserver_schedule in mediaserver_schedules:
                job_id = mediaserver_schedule["id"]
                self._jobs[job_id] = {
                    "name": mediaserver_schedule["name"],
                    "func": mediaserver_chain.sync,
                    "running": False,
                    "kwargs": {"server": mediaserver_schedule["server"]},
                }
                self._scheduler.add_job(
                    self.start,
                    "interval",
                    id=job_id,
                    name=mediaserver_schedule["name"],
                    hours=mediaserver_schedule["interval"],
                    next_run_time=datetime.now(pytz.timezone(settings.TZ)) + timedelta(minutes=10),
                    kwargs={"job_id": job_id},
                )






            # 下载器文件转移（每5分钟）
            self._scheduler.add_job(
                self.start,
                "interval",
                id="transfer",
                name="下载文件整理",
                minutes=5,
                kwargs={"job_id": "transfer"},
            )

            # 后台刷新TMDB壁纸
            self._scheduler.add_job(
                self.start,
                "interval",
                id="random_wallpager",
                name="壁纸缓存",
                minutes=30,
                next_run_time=datetime.now(pytz.timezone(settings.TZ)) + timedelta(seconds=1),
                kwargs={"job_id": "random_wallpager"},
            )

            # 公共定时服务
            self._scheduler.add_job(
                self.start,
                "interval",
                id="scheduler_job",
                name="公共定时服务",
                minutes=10,
                kwargs={"job_id": "scheduler_job"},
            )

            # 数据表清理服务，每天凌晨执行一次
            if settings.DATA_CLEANUP_ENABLE:
                self._scheduler.add_job(
                    self.start,
                    "cron",
                    id="data_cleanup",
                    name="数据表清理",
                    hour=3,
                    minute=30,
                    kwargs={"job_id": "data_cleanup"},
                )




            # 下载文件同步（插件能力内置化）
            self._scheduler.add_job(
                self.start,
                "interval",
                id="download_file_sync",
                name="下载文件同步",
                minutes=5,
                kwargs={"job_id": "download_file_sync"},
            )

            # 媒体库封面生成（插件能力内置化）
            self._scheduler.add_job(
                self.start,
                "cron",
                id="library_cover_generator",
                name="媒体库封面生成",
                hour=4,
                minute=0,
                kwargs={"job_id": "library_cover_generator"},
            )

            # 主动内存回收
            if settings.MEMORY_GC_INTERVAL:
                self._scheduler.add_job(
                    self.start,
                    "interval",
                    id="full_gc",
                    name="主动内存回收",
                    minutes=settings.MEMORY_GC_INTERVAL,
                    kwargs={"job_id": "full_gc"},
                )



            # 启动定时服务
            self._scheduler.start()

    def __prepare_job(self, job_id: str) -> Optional[dict]:
        """
        准备定时任务
        """
        started_at = self._format_time()
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            if job.get("running"):
                logger.warning(f"定时任务 {job_id} - {job.get('name')} 正在运行 ...")
                return None
            self._jobs[job_id]["running"] = True
            self._jobs[job_id]["last_started_at"] = started_at
            self._jobs[job_id]["last_finished_at"] = None
            self._jobs[job_id]["last_error"] = None
        progress = ProgressHelper(self._get_progress_key(job_id))
        progress.start()
        progress.update(
            value=0,
            text=f"{job.get('name') or job_id} 开始执行 ...",
            data={
                "id": job_id,
                "name": job.get("name"),
                "provider": job.get("provider_name", "[系统]"),
                "status": "running",
                "success": None,
                "started_at": started_at,
                "finished_at": None,
                "error": None,
            },
        )
        return job

    def __finish_job(
            self,
            job_id: str,
            success: bool = True,
            error: Optional[str] = None,
    ) -> None:
        """
        完成定时任务
        """
        finished_at = self._format_time()
        job = None
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job["running"] = False
                job["last_finished_at"] = finished_at
                job["last_error"] = error
        job_name = job.get("name") if job else job_id
        progress = ProgressHelper(self._get_progress_key(job_id))
        current_progress = progress.get() or {}
        progress_value = 100 if success else current_progress.get("value", 0)
        progress.end(
            text=f"{job_name} {'执行完成' if success else '执行失败'}",
            data={
                "id": job_id,
                "name": job_name,
                "provider": job.get("provider_name", "[系统]") if job else None,
                "status": "success" if success else "failed",
                "success": success,
                "finished_at": finished_at,
                "error": error,
            },
            value=progress_value,
        )

    def get_progress(self, job_id: str) -> Optional[schemas.ScheduleProgress]:
        """
        查询指定定时服务的执行进度。
        """
        if not job_id:
            return None
        with self._lock:
            job = self._jobs.get(job_id)
            job_name = job.get("name") if job else job_id
            provider_name = job.get("provider_name", "[系统]") if job else None
            running = bool(job.get("running")) if job else False
            last_started_at = job.get("last_started_at") if job else None
            last_finished_at = job.get("last_finished_at") if job else None
            last_error = job.get("last_error") if job else None
        detail = ProgressHelper(self._get_progress_key(job_id)).get() or {}
        if not job and not detail:
            return None
        data = detail.get("data") or {}
        value = detail.get("value", 0)
        try:
            value = float(value)
        except (TypeError, ValueError):
            value = 0.0
        return schemas.ScheduleProgress(
            id=job_id,
            name=data.get("name") or job_name,
            provider=data.get("provider") or provider_name,
            enable=bool(detail.get("enable", running)),
            value=max(min(value, 100), 0),
            text=detail.get("text"),
            status=data.get("status") or ("running" if running else "waiting"),
            success=data.get("success"),
            started_at=data.get("started_at") or last_started_at,
            finished_at=data.get("finished_at") or last_finished_at,
            error=data.get("error") or last_error,
            data=data,
        )

    @staticmethod
    def __handle_job_error(job_id: str, job: dict, error: Exception) -> None:
        """
        记录定时任务执行异常并发送系统错误事件。
        """
        logger.error(
            f"定时任务 {job.get('name')} 执行失败：{str(error)} - {traceback.format_exc()}"
        )
        MessageHelper().put(
            title=f"{job.get('name')} 执行失败", message=str(error), role="system"
        )
        eventmanager.send_event(
            EventType.SystemError,
            {
                "type": "scheduler",
                "scheduler_id": job_id,
                "scheduler_name": job.get("name"),
                "error": str(error),
                "traceback": traceback.format_exc(),
            },
        )

    def __build_progress_callback(self, job_id: str, job: dict) -> Callable[..., None]:
        """
        构建传递给定时任务内部的进度更新回调。
        """

        def update_progress(
                value: Optional[float] = None,
                text: Optional[str] = None,
                data: Optional[dict] = None,
        ) -> None:
            """
            更新当前定时任务进度。
            """
            progress_data = {
                "id": job_id,
                "name": job.get("name"),
                "provider": job.get("provider_name", "[系统]"),
                "status": "running",
                "success": None,
            }
            if data:
                progress_data.update(data)
            ProgressHelper(self._get_progress_key(job_id)).update(
                value=value,
                text=text,
                data=progress_data,
            )

        return update_progress

    @staticmethod
    def __supports_progress_callback(func: Callable[..., Any]) -> bool:
        """
        判断定时任务函数是否显式支持进度回调参数。
        """
        try:
            parameters = inspect.signature(func).parameters
        except (TypeError, ValueError):
            return False
        return "progress_callback" in parameters

    @staticmethod
    def __get_result_error(result: Any) -> Optional[str]:
        """
        从定时任务标准失败返回值中提取错误信息。
        """
        if (
                isinstance(result, tuple)
                and result
                and isinstance(result[0], bool)
                and result[0] is False
        ):
            return str(result[1]) if len(result) > 1 and result[1] else "定时任务返回失败"
        return None

    async def __run_coro_job(self, coro, job_id: str, job: dict) -> None:
        """
        在当前事件循环内执行协程定时任务并在真实完成后收敛状态。
        """
        success = True
        error = None
        try:
            result = await coro
            error = self.__get_result_error(result)
            success = error is None
        except Exception as err:
            success = False
            error = str(err)
            self.__handle_job_error(job_id=job_id, job=job, error=err)
        finally:
            self.__finish_job(job_id=job_id, success=success, error=error)

    def start(self, job_id: str, *args, **kwargs) -> None:
        """
        启动定时服务
        """

        def __start_coro(coro) -> bool:
            """
            启动协程，返回是否由异步回调自行收敛任务状态。
            """
            try:
                running_loop = asyncio.get_running_loop()
            except RuntimeError:
                running_loop = None
            target_loop = global_vars.loop
            if running_loop:
                asyncio.create_task(self.__run_coro_job(coro=coro, job_id=job_id, job=job))
                return True
            if target_loop and target_loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self.__run_coro_job(coro=coro, job_id=job_id, job=job),
                    target_loop,
                )
                return True
            asyncio.run(coro)
            return False

        # 获取定时任务
        job = self.__prepare_job(job_id)
        if not job:
            return
        success = True
        error = None
        deferred_finish = False
        # 开始运行
        try:
            if not kwargs:
                kwargs = dict(job.get("kwargs") or {})
            func = job.get("func")
            if not func:
                return
            if self.__supports_progress_callback(func) and "progress_callback" not in kwargs:
                kwargs["progress_callback"] = self.__build_progress_callback(
                    job_id=job_id, job=job
                )
            # 是否多进程运行
            run_in_process = job.get("run_in_process", False)
            if inspect.iscoroutinefunction(func):
                # 协程函数
                deferred_finish = __start_coro(func(*args, **kwargs))
            elif run_in_process:
                # 多进程运行
                p = multiprocessing.Process(target=func, args=args, kwargs=kwargs)
                p.start()
                p.join()
            else:
                # 普通函数
                result = func(*args, **kwargs)
                error = self.__get_result_error(result)
                success = error is None
        except Exception as e:
            success = False
            error = str(e)
            self.__handle_job_error(job_id=job_id, job=job, error=e)
        finally:
            if not deferred_finish:
                # 运行结束
                self.__finish_job(job_id=job_id, success=success, error=error)















    def list(self) -> List[schemas.ScheduleInfo]:
        """
        当前所有任务
        """
        if not self._scheduler:
            return []
        with self._lock:
            # 返回计时任务
            schedulers = []
            # 去重
            added = []
            # 避免_scheduler.shutdown()处于阻塞状态导致的死锁
            if not self._scheduler or not self._scheduler.running:
                return []
            jobs = self._scheduler.get_jobs()
            # 按照下次运行时间排序
            jobs.sort(key=lambda x: x.next_run_time)
            # 将正在运行的任务提取出来 (保障一次性任务正常显示)
            for job_id, service in self._jobs.items():
                name = service.get("name")
                provider_name = service.get("provider_name")
                if service.get("running") and name and provider_name:
                    if job_id not in added:
                        added.append(job_id)
                    progress = self.get_progress(job_id)
                    schedulers.append(
                        schemas.ScheduleInfo(
                            id=job_id,
                            name=name,
                            provider=provider_name,
                            status="正在运行",
                            progress=progress.value if progress else 0,
                            progress_text=progress.text if progress else None,
                            progress_enable=progress.enable if progress else False,
                            progress_detail=progress,
                        )
                    )
            # 获取其他待执行任务
            for job in jobs:
                job_id = job.id.split("|")[0]
                if job_id not in added:
                    added.append(job_id)
                else:
                    continue
                service = self._jobs.get(job_id)
                if not service:
                    continue
                # 任务状态
                status = "正在运行" if service.get("running") else "等待"
                # 下次运行时间
                next_run = TimerUtils.time_difference(job.next_run_time)
                progress = self.get_progress(job_id)
                schedulers.append(
                    schemas.ScheduleInfo(
                        id=job_id,
                        name=job.name,
                        provider=service.get("provider_name", "[系统]"),
                        status=status,
                        next_run=next_run,
                        progress=progress.value if progress else 0,
                        progress_text=progress.text if progress else None,
                        progress_enable=progress.enable if progress else False,
                        progress_detail=progress,
                    )
                )
            return schedulers

    def stop(self):
        """
        关闭定时服务
        """
        with lock:
            try:
                if self._scheduler:
                    logger.info("正在停止定时任务...")
                    self._event.set()
                    self._scheduler.remove_all_jobs()
                    if self._scheduler.running:
                        self._scheduler.shutdown()
                    self._scheduler = None
                    logger.info("定时任务停止完成")
            except Exception as e:
                logger.error(f"停止定时任务失败：：{str(e)} - {traceback.format_exc()}")

    @staticmethod
    def clear_cache():
        """
        清理缓存
        """
        SchedulerChain().clear_cache()

    @staticmethod
    def full_gc():
        """
        主动内存回收
        """
        memory_before = get_memory_usage()
        collected = gc.collect()
        memory_after = get_memory_usage()
        memory_freed = memory_before - memory_after
        logger.info(
            f"主动内存回收完成，回收对象数: {collected}，释放内存: {memory_freed:.2f} MB"
        )


