# -*- coding: utf-8 -*-
"""自定义识别词快照用例：下载时保存完整识别词，整理时优先复用快照。

本分支已删除订阅能力，因此不再按下载来源实时反查订阅：有快照用快照，无快照回退全局识别词。
"""
from types import SimpleNamespace

from app.chain.transfer import TransferChain


def _fake_history(custom_words=None, note=None):
    """构造仅含测试所需字段的下载历史替身。"""
    return SimpleNamespace(custom_words=custom_words, note=note)


def test_transfer_prefers_snapshot():
    """整理时存在下载快照，应直接使用快照中的识别词。"""
    history = _fake_history(custom_words="S04 => S01\n第 <> 集 >> EP+66")
    result = TransferChain._get_subscribe_custom_words(history)

    assert result == ["S04 => S01", "第 <> 集 >> EP+66"]


def test_transfer_returns_none_without_snapshot():
    """无快照（历史旧记录）时不再反查订阅，返回 None 以回退全局识别词。"""
    history = _fake_history(custom_words=None, note={"source": "Subscribe|{...}"})

    assert TransferChain._get_subscribe_custom_words(history) is None


def test_transfer_returns_none_when_unavailable():
    """无下载记录或 note 非字典时返回 None。"""
    # 无下载记录
    assert TransferChain._get_subscribe_custom_words(None) is None
    # 无快照且 note 非字典
    assert TransferChain._get_subscribe_custom_words(_fake_history(note="不是字典")) is None
