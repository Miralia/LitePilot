# -*- coding: utf-8 -*-
"""内置功能配置读取用例。

重点覆盖历史布尔值到结构化配置的兼容，以及非法值回退默认，避免升级后配置失效。
"""
import pytest

from app.helper.builtinconf import load_conf
from app.schemas.system import (
    DownloadFileSyncConf,
    LibraryCoverGeneratorConf,
    SyncDelByMediaServerConf,
)
from app.schemas.types import SystemConfigKey


class _FakeOper:
    """最小配置操作器替身，只实现 get/set。"""

    def __init__(self, value=None):
        self.value = value

    def get(self, key):
        """返回预设值。"""
        return self.value

    def set(self, key, value):
        """记录写入值。"""
        self.value = value


def test_missing_value_returns_disabled_default():
    """配置缺失时应返回默认配置且未启用。"""
    conf = load_conf(SystemConfigKey.DownloadFileSync, DownloadFileSyncConf, _FakeOper(None))

    assert conf.enabled is False
    assert conf.interval_minutes == 5


def test_legacy_true_enables_with_defaults():
    """历史布尔值 True 应映射为启用并使用默认参数。"""
    conf = load_conf(SystemConfigKey.DownloadFileSync, DownloadFileSyncConf, _FakeOper(True))

    assert conf.enabled is True
    assert conf.interval_minutes == 5
    assert conf.max_torrents == 200


def test_legacy_false_keeps_disabled():
    """历史布尔值 False 应视为未启用。"""
    conf = load_conf(
        SystemConfigKey.SyncDelByMediaServer, SyncDelByMediaServerConf, _FakeOper(False)
    )

    assert conf.enabled is False
    assert conf.delete_torrent is True


def test_dict_value_is_validated():
    """字典配置应按模型字段解析。"""
    conf = load_conf(
        SystemConfigKey.SyncDelByMediaServer,
        SyncDelByMediaServerConf,
        _FakeOper({"enabled": True, "delete_source_file": True, "dry_run": True}),
    )

    assert conf.enabled is True
    assert conf.delete_source_file is True
    assert conf.dry_run is True


def test_invalid_dict_falls_back_to_default():
    """字段类型非法时应回退默认配置，而不是抛异常中断任务。"""
    conf = load_conf(
        SystemConfigKey.LibraryCoverGenerator,
        LibraryCoverGeneratorConf,
        _FakeOper({"enabled": True, "width": "not-a-number"}),
    )

    assert conf.enabled is False
    assert conf.width == 1920


def test_cover_conf_custom_values():
    """封面配置应保留自定义尺寸与字号。"""
    conf = load_conf(
        SystemConfigKey.LibraryCoverGenerator,
        LibraryCoverGeneratorConf,
        _FakeOper(
            {
                "enabled": True,
                "width": 1280,
                "height": 720,
                "zh_font_size": 120,
                "en_font_size": 48,
                "libraries": ["电影"],
            }
        ),
    )

    assert conf.width == 1280
    assert conf.zh_font_size == 120
    assert conf.libraries == ["电影"]

def test_trigger_throttle_default():
    """按需同步的节流窗口应有合理默认值。"""
    conf = DownloadFileSyncConf()
    assert conf.trigger_throttle_seconds == 30


def test_trigger_throttle_can_be_disabled():
    """配置为 0 时应表示不节流。"""
    conf = load_conf(
        SystemConfigKey.DownloadFileSync,
        DownloadFileSyncConf,
        _FakeOper({"enabled": True, "trigger_throttle_seconds": 0}),
    )
    assert conf.trigger_throttle_seconds == 0


def test_probe_conf_defaults():
    """技术信息探测默认开启，且两项覆盖都打开。"""
    from app.schemas.system import MediaInfoProbeConf

    conf = load_conf(SystemConfigKey.MediaInfoProbe, MediaInfoProbeConf, _FakeOper(None))
    assert conf.enabled is True
    assert conf.override_resolution is True
    assert conf.override_source is True

def test_cover_generator_runs_after_queue_idle():
    """封面生成应在整理队列清空后才触发，且受开关控制。"""
    from unittest.mock import MagicMock, patch

    from app.chain.transfer import JobManager, TransferChain

    jobview = JobManager()
    chain = TransferChain()
    chain.jobview = jobview

    # 队列为空且开关关闭时不应触发
    with patch("app.chain.transfer.library_cover_generator_conf") as conf_mock, \
            patch("app.chain.mediacover.MediaCoverChain") as cover_mock:
        conf_mock.return_value = MagicMock(enabled=False)
        chain._TransferChain__refresh_library_covers_when_idle()
        cover_mock.assert_not_called()

    # 队列为空且开关开启时应触发
    with patch("app.chain.transfer.library_cover_generator_conf") as conf_mock, \
            patch("app.chain.mediacover.MediaCoverChain") as cover_mock:
        conf_mock.return_value = MagicMock(enabled=True)
        chain._TransferChain__refresh_library_covers_when_idle()
        cover_mock.return_value.process.assert_called_once()

    # 队列仍有未完成任务时不应触发
    with patch("app.chain.transfer.library_cover_generator_conf") as conf_mock, \
            patch.object(JobManager, "has_pending_jobs", return_value=True), \
            patch("app.chain.mediacover.MediaCoverChain") as cover_mock:
        conf_mock.return_value = MagicMock(enabled=True)
        chain._TransferChain__refresh_library_covers_when_idle()
        cover_mock.return_value.process.assert_not_called()


def test_has_pending_jobs_false_for_empty_queue():
    """空队列应判定为没有待处理作业。"""
    from app.chain.transfer import JobManager

    assert JobManager().has_pending_jobs() is False
