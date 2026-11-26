import asyncio
import json
import queue
import threading
import time
from unittest.mock import Mock

import pytest

import app.api.endpoints.system as system_endpoint
from app.api.endpoints.message import clear_notification_message, get_notification_message
from app.api.endpoints.system import get_message as get_system_message_stream
from app.chain import ChainBase
from app.core.meta import MetaBase
from app.db import AsyncSessionFactory, SessionFactory
from app.db.message_oper import MessageOper
from app.db.models.message import Message
from app.db.systemconfig_oper import SystemConfigOper
from app.helper.message import MessageHelper
from app.schemas import Notification, NotificationClearScope
from app.schemas.types import MediaType, NotificationType, SystemConfigKey


def _clear_messages() -> None:
    """
    清空消息表，隔离通知测试数据。
    """
    with SessionFactory() as db:
        db.query(Message).delete()
        db.commit()
    SystemConfigOper().delete(SystemConfigKey.NotificationClearBefore)


def _reset_message_helper(helper: MessageHelper) -> None:
    """
    清空单例消息队列和去重缓存，避免用例间互相影响。
    """
    with helper._subscription_lock:
        helper._system_messages.clear()
        helper._subscribers.clear()
    helper._recent_notification_keys.clear()


class AlwaysConnectedRequest:
    """
    测试请求对象，始终报告连接未断开。
    """

    async def is_disconnected(self) -> bool:
        """
        模拟连接仍处于活跃状态。
        """
        return False


def _set_message_time(title: str, reg_time: str) -> None:
    """
    调整测试消息时间，避免消息写入时的当前秒影响清理边界断言。
    """
    with SessionFactory() as db:
        db.query(Message).filter(Message.title == title).update({"reg_time": reg_time})
        db.commit()


def test_notification_history_only_lists_sent_messages() -> None:
    """
    通知历史应返回已发送消息，包含通过消息链登记的非系统消息。
    """
    _clear_messages()
    oper = MessageOper()
    oper.add(title="系统通知", text="下载完成", action=1, mtype=NotificationType.Download)
    oper.add(title="用户消息", text="帮我搜索", action=0)
    oper.add(title="自动回复", text="已处理", action=1, mtype=NotificationType.Other)

    messages = MessageOper().list_by_page(page=1, count=10)
    assert [message.title for message in messages if message.action == 1] == ["自动回复", "系统通知"]


def test_web_message_history_returns_all_messages() -> None:
    """
    Web 消息历史返回消息表中的全部记录。
    """
    _clear_messages()
    oper = MessageOper()
    oper.add(title="自动回复", text="已处理", action=1, mtype=NotificationType.Other)
    oper.add(title="用户消息", text="/ai 帮我处理", action=0)
    oper.add(title="普通通知", text="下载完成", action=1, mtype=NotificationType.Download)

    messages = MessageOper().list_by_page(page=1, count=10)
    assert [message.title for message in messages] == ["普通通知", "用户消息", "自动回复"]


def test_notification_clear_marker_filters_history_across_requests() -> None:
    """
    通知清理时间写入后端后，后续通知历史查询应直接返回过滤后的结果。
    """
    _clear_messages()
    oper = MessageOper()
    oper.add(
        title="旧系统通知",
        text="任务失败",
        action=1,
        mtype=NotificationType.Other,
    )
    oper.add(
        title="旧媒体通知",
        text="影片入库",
        image="https://example.com/poster.jpg",
        action=1,
    )
    _set_message_time("旧系统通知", "2026-01-01 00:00:00")
    _set_message_time("旧媒体通知", "2026-01-01 00:00:00")

    asyncio.run(clear_notification_message(scope=NotificationClearScope.Media))

    oper.add(
        title="新媒体通知",
        text="影片入库",
        image="https://example.com/new.jpg",
        action=1,
    )
    _set_message_time("新媒体通知", "2999-01-01 00:00:00")

    async def _load_titles() -> list[str]:
        """
        通过异步接口读取通知标题。
        """
        async with AsyncSessionFactory() as db:
            messages = await get_notification_message(db=db)
        return [message.title for message in messages]

    assert asyncio.run(_load_titles()) == ["新媒体通知", "旧系统通知"]


def test_system_helper_message_only_enters_sse_queue() -> None:
    """
    系统实时消息只进入前端 SSE 队列，不写入通知历史。
    """
    _clear_messages()
    helper = MessageHelper()
    _reset_message_helper(helper)

    subscriber = helper.subscribe()
    try:
        helper.put("调度任务执行失败", title="系统错误")

        assert MessageOper().list_by_page(page=1, count=10) == []
        realtime_message = json.loads(subscriber.get_nowait())
        assert realtime_message["type"] == "system"
        assert realtime_message["title"] == "系统错误"
        assert realtime_message["text"] == "调度任务执行失败"
    finally:
        helper.unsubscribe(subscriber)


def test_system_message_stream_unsubscribes_when_closed(monkeypatch) -> None:
    """
    SSE 生成器关闭时必须移除订阅，避免已断开连接继续占用实时消息内存。
    """
    helper = MessageHelper()
    _reset_message_helper(helper)
    monkeypatch.setattr(system_endpoint.global_vars, "STOP_EVENT", threading.Event())

    async def exercise_stream() -> None:
        response = await get_system_message_stream(AlwaysConnectedRequest(), None)
        stream = response.body_iterator
        first_frame = await stream.__anext__()
        assert first_frame.startswith("data:")
        assert len(helper._subscribers) == 1

        await stream.aclose()
        assert not helper._subscribers

    asyncio.run(exercise_stream())


def test_system_message_stream_drains_burst_frames(monkeypatch) -> None:
    """
    一次产生多条实时消息时，SSE 必须连续排空，不能每 3 秒只推送一条。
    """
    helper = MessageHelper()
    _reset_message_helper(helper)
    monkeypatch.setattr(system_endpoint.global_vars, "STOP_EVENT", threading.Event())
    helper.put("第一条突发消息", title="系统错误一")
    helper.put("第二条突发消息", title="系统错误二")

    async def exercise_stream() -> None:
        response = await get_system_message_stream(AlwaysConnectedRequest(), None)
        stream = response.body_iterator
        started_at = time.monotonic()
        first_frame = await stream.__anext__()
        second_frame = await stream.__anext__()
        elapsed = time.monotonic() - started_at
        assert elapsed < 1
        assert json.loads(first_frame.removeprefix("data: "))["text"] == "第一条突发消息"
        assert json.loads(second_frame.removeprefix("data: "))["text"] == "第二条突发消息"
        await stream.aclose()

    asyncio.run(exercise_stream())


def test_system_helper_replays_pending_message_to_new_subscriber() -> None:
    """
    SSE 未连接期间产生的系统实时消息，应在首个新订阅建立后仍可回放。
    """
    helper = MessageHelper()
    _reset_message_helper(helper)
    helper.put("离线期间产生的系统消息", title="系统错误")

    subscriber = helper.subscribe()
    try:
        realtime_message = json.loads(subscriber.get_nowait())
        assert realtime_message["type"] == "system"
        assert realtime_message["title"] == "系统错误"
        assert realtime_message["text"] == "离线期间产生的系统消息"
    finally:
        helper.unsubscribe(subscriber)


def test_system_helper_broadcasts_realtime_message_to_all_subscribers() -> None:
    """
    多个浏览器标签页建立多个 SSE 连接时，实时消息不能被单个连接竞争消费。
    """
    helper = MessageHelper()
    _reset_message_helper(helper)
    first = helper.subscribe()
    second = helper.subscribe()
    try:
        helper.put("广播系统消息", title="系统错误")

        assert json.loads(first.get_nowait())["text"] == "广播系统消息"
        assert json.loads(second.get_nowait())["text"] == "广播系统消息"
    finally:
        helper.unsubscribe(first)
        helper.unsubscribe(second)


def test_system_helper_unsubscribed_stream_does_not_receive_new_messages() -> None:
    """
    SSE 断开后必须退订，不能继续累积无人消费的实时消息。
    """
    helper = MessageHelper()
    _reset_message_helper(helper)
    disconnected = helper.subscribe()
    active = helper.subscribe()
    try:
        helper.unsubscribe(disconnected)
        helper.put("断开后产生的系统消息", title="系统错误")

        assert json.loads(active.get_nowait())["text"] == "断开后产生的系统消息"
        with pytest.raises(queue.Empty):
            disconnected.get_nowait()
    finally:
        helper.unsubscribe(disconnected)
        helper.unsubscribe(active)


def test_system_helper_bounds_replay_backlog_per_subscriber() -> None:
    """
    订阅端长期不消费时只保留近期消息，不能随通知数量无限占用内存。
    """
    helper = MessageHelper()
    _reset_message_helper(helper)
    subscriber = helper.subscribe()
    try:
        for index in range(105):
            helper.put(f"积压系统消息{index}", title=f"系统错误{index}")

        messages = []
        while True:
            try:
                messages.append(json.loads(subscriber.get_nowait()))
            except queue.Empty:
                break

        assert len(messages) == 100
        assert messages[0]["text"] == "积压系统消息5"
        assert messages[-1]["text"] == "积压系统消息104"
    finally:
        helper.unsubscribe(subscriber)


def test_notification_post_message_is_persisted_without_sse_queue(monkeypatch) -> None:
    """
    业务通知通过消息链发送时只登记数据库，不进入前端 SSE 队列。
    """
    _clear_messages()
    helper = MessageHelper()
    _reset_message_helper(helper)
    chain = ChainBase()

    monkeypatch.setattr(chain.messagequeue, "send_message", Mock())
    monkeypatch.setattr(chain.eventmanager, "send_event", Mock())

    chain.post_message(
        Notification(
            mtype=NotificationType.Download,
            title="下载完成",
            text="影片已加入下载器",
        )
    )

    messages = MessageOper().list_by_page(page=1, count=10)
    assert len(messages) == 1
    assert messages[0].title == "下载完成"
    assert messages[0].mtype == NotificationType.Download.value
    subscriber = helper.subscribe()
    try:
        assert subscriber.empty()
    finally:
        helper.unsubscribe(subscriber)
    chain.messagequeue.send_message.assert_called_once()


def test_other_notification_post_message_is_persisted_without_sse_queue(monkeypatch) -> None:
    """
    非系统消息通过消息链发送时登记数据库，但不进入前端 SSE 队列。
    """
    _clear_messages()
    helper = MessageHelper()
    _reset_message_helper(helper)
    chain = ChainBase()

    monkeypatch.setattr(chain.messagequeue, "send_message", Mock())
    monkeypatch.setattr(chain.eventmanager, "send_event", Mock())

    chain.post_message(
        Notification(
            mtype=NotificationType.Other,
            title="MoviePilot助手",
            text="已完成处理",
        )
    )

    messages = MessageOper().list_by_page(page=1, count=10)
    assert len(messages) == 1
    assert messages[0].title == "MoviePilot助手"
    assert messages[0].mtype == NotificationType.Other.value
    subscriber = helper.subscribe()
    try:
        assert subscriber.empty()
    finally:
        helper.unsubscribe(subscriber)
    chain.messagequeue.send_message.assert_called_once()


def test_transient_notification_post_message_skips_history_but_dispatches(monkeypatch) -> None:
    """
    标记为不保存历史的过程消息应跳过数据库登记，但仍正常派发。
    """
    _clear_messages()
    chain = ChainBase()

    monkeypatch.setattr(chain.messagequeue, "send_message", Mock())
    monkeypatch.setattr(chain.eventmanager, "send_event", Mock())

    chain.post_message(
        Notification(
            title="请选择下载目录",
            text="1. 默认目录",
            save_history=False,
        )
    )

    assert MessageOper().list_by_page(page=1, count=10) == []
    chain.eventmanager.send_event.assert_not_called()
    chain.messagequeue.send_message.assert_called_once()
