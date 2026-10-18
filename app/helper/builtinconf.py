# -*- coding: utf-8 -*-
"""
内置功能配置读取。

三个内置能力（下载文件同步、媒体服务器联动删除、媒体库封面生成）早期只存布尔开关，
现在升级为结构化配置。为保证升级后旧值仍然可用，这里统一做一次兼容读取：
布尔值映射为 `enabled`，字典按模型校验，非法值回退到默认配置。
"""

from typing import Optional, Type, TypeVar, Union

from pydantic import BaseModel, ValidationError

from app.db.systemconfig_oper import SystemConfigOper
from app.log import logger
from app.schemas.system import (
    DownloadFileSyncConf,
    LibraryCoverGeneratorConf,
    SyncDelByMediaServerConf,
)
from app.schemas.types import SystemConfigKey

# 配置模型类型
ConfType = TypeVar("ConfType", bound=BaseModel)


def load_conf(
    key: SystemConfigKey,
    model: Type[ConfType],
    config_oper: Optional[SystemConfigOper] = None,
) -> ConfType:
    """
    读取并校验结构化配置。

    兼容历史布尔值：`True` 视为启用并使用默认参数，`False`/空值视为未启用。

    :param key: 配置键
    :param model: 目标配置模型
    :param config_oper: 配置操作器，默认新建
    :return: 校验后的配置对象，异常时返回默认配置
    """
    oper = config_oper or SystemConfigOper()
    raw: Union[bool, dict, None] = oper.get(key)
    if raw is None or raw is False:
        return model()
    if raw is True:
        return model(enabled=True)
    if isinstance(raw, dict):
        try:
            return model(**raw)
        except ValidationError as err:
            logger.warn(f"配置 {key.value} 校验失败，使用默认值：{err}")
            return model()
    logger.warn(f"配置 {key.value} 类型异常（{type(raw).__name__}），使用默认值")
    return model()


def save_conf(
    key: SystemConfigKey,
    conf: BaseModel,
    config_oper: Optional[SystemConfigOper] = None,
) -> None:
    """
    保存结构化配置。

    :param key: 配置键
    :param conf: 配置对象
    :param config_oper: 配置操作器，默认新建
    """
    (config_oper or SystemConfigOper()).set(key, conf.model_dump())


def download_file_sync_conf() -> DownloadFileSyncConf:
    """
    读取下载文件同步配置。
    """
    return load_conf(SystemConfigKey.DownloadFileSync, DownloadFileSyncConf)


def sync_del_by_media_server_conf() -> SyncDelByMediaServerConf:
    """
    读取媒体服务器联动删除配置。
    """
    return load_conf(SystemConfigKey.SyncDelByMediaServer, SyncDelByMediaServerConf)


def library_cover_generator_conf() -> LibraryCoverGeneratorConf:
    """
    读取媒体库封面生成配置。
    """
    return load_conf(SystemConfigKey.LibraryCoverGenerator, LibraryCoverGeneratorConf)