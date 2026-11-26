# -*- coding: utf-8 -*-
"""
Telegram 模块单元测试（pytest 原生）。
"""
import json
import warnings
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import pytest

from app.modules.telegram import TelegramModule
from app.modules.telegram.telegram import Telegram
from app.schemas import Notification
from app.schemas.types import MessageChannel


@pytest.fixture
def telegram():
    """构造 TeleBot 与 ImageHelper 均已打桩的 Telegram 实例。

    空 token 会让 Telegram.__init__ 提前返回、致 send_* 抛错，故用假 bot 让初始化完整、
    消息发送走内存桩；ImageHelper 打桩避免 send_medias/send_msg 按 poster_path 真实下载海报
    （否则对 raw.githubusercontent.com 等外链发起真实 HTTP，外部 IO 不可接受且拖慢用例）。
    with 上下文在 fixture 结束时自动停桩，即使实例化失败也不泄漏 patch。
    """
    with patch("app.modules.telegram.telegram.TeleBot") as mock_telebot_cls, \
            patch("app.modules.telegram.telegram.ImageHelper") as mock_image_cls:
        bot_instance = MagicMock()
        # get_me 用于初始化 bot 用户名，需返回带 username 的对象
        bot_instance.get_me.return_value = MagicMock(username="test_bot")
        # polling/stop 使用普通函数，避免后台线程执行 MagicMock 时在退出阶段产生锁竞争。
        bot_instance.infinity_polling = lambda *args, **kwargs: None
        bot_instance.stop_polling = lambda *args, **kwargs: None
        mock_telebot_cls.return_value = bot_instance
        mock_image_cls.return_value.fetch_image.return_value = b"fake-image-bytes"
        telegram = Telegram(TELEGRAM_TOKEN="fake_token", TELEGRAM_CHAT_ID="fake_chat_id")
        yield telegram
        telegram.stop()


def test_send_msg_success(telegram):
    """测试发送普通消息成功"""
    # 调用send_msg方法
    result = telegram.send_msg(
        title="📥 开始下载\n唐朝诡事录 (2022)S03E31-E32",
        text="\n🕒 时间： 2025-11-21 18:14:51\n🎭 类别： 国产剧\n🌐 站点： 天空\n🌟 质量： WEB-DL 2160p\n💾 大小： 1.68G\n⚡️ 促销： 未知\n🚨 H&R： 否\n📛 名称： \nStrange Tales of Tang Dynasty S03E31-E32 2025 2160p WEB-DL DDP5.1 H265-Pure@HDSWEB [唐朝诡事录之长安3 / 唐朝诡事录3 / 唐朝诡事录 第三部 / 唐朝诡事录·长安 / 唐诡3 / Horror Stories of Tang Dynasty Ⅲ / Strange Legend of Tang Dynasty Ⅲ 第3季 第31-32集 | 主演: 杨旭文 杨志刚 郜思雯 [内封简繁英多国软字幕] 【去头尾广告纯享版】[非伪去头] *发现未去净的广告或片头片尾，奖励魔力1W]"
    )

    # 验证返回值：send_msg 失败时返回 {"success": False}（非空字典，仅 truthy 检查会漏判），故显式断言 success
    assert result and result.get("success")


def test_telegram_parser_preserves_message_context():
    """Telegram 文本消息应保留 typing 所需的 message_id 和 chat_id。"""
    module = TelegramModule()
    client_config = SimpleNamespace(name="telegram-test", config={})
    client = SimpleNamespace(bot_username="mp_bot")
    payload = {
        "update_id": 1,
        "message": {
            "message_id": 101,
            "from": {"id": 10001, "username": "tester"},
            "chat": {"id": 10001, "type": "private"},
            "text": "东张西望",
            "reply_to_message": {"message_id": 99, "text": "请输入节目关键词"},
        },
    }

    with patch.object(module, "get_config", return_value=client_config), patch.object(
        module, "get_instance", return_value=client
    ):
        message = module.message_parser(
            source="telegram-test",
            body=json.dumps(payload),
            form=None,
            args={},
        )

    assert message.text == "东张西望"
    assert message.message_id == 101
    assert message.chat_id == "10001"


def test_telegram_parser_ignores_media_only_message():
    """无文本的媒体消息不应进入只支持命令和按钮回调的消息链。"""
    module = TelegramModule()
    client_config = SimpleNamespace(name="telegram-test", config={})
    client = SimpleNamespace(bot_username="mp_bot")
    payload = {
        "message": {
            "message_id": 102,
            "from": {"id": 10001, "username": "tester"},
            "chat": {"id": 10001, "type": "private"},
            "photo": [{"file_id": "photo-file", "file_size": 1024}],
        },
    }

    with patch.object(module, "get_config", return_value=client_config), patch.object(
        module, "get_instance", return_value=client
    ):
        message = module.message_parser(
            source="telegram-test",
            body=json.dumps(payload),
            form=None,
            args={},
        )

    assert message is None


def test_telegram_parser_preserves_callback_context():
    """按钮回调仍应转换为 CALLBACK 文本并保留原消息定位信息。"""
    module = TelegramModule()
    client_config = SimpleNamespace(name="telegram-test", config={})
    client = SimpleNamespace(bot_username="mp_bot")
    payload = {
        "callback_query": {
            "id": "callback-1",
            "from": {"id": 10001, "username": "tester"},
            "message": {"message_id": 88, "chat": {"id": 10001}},
            "data": "transfer_retry_12",
        },
    }

    with patch.object(module, "get_config", return_value=client_config), patch.object(
        module, "get_instance", return_value=client
    ):
        message = module.message_parser(
            source="telegram-test",
            body=json.dumps(payload),
            form=None,
            args={},
        )

    assert message.text == "CALLBACK:transfer_retry_12"
    assert message.message_id == 88
    assert message.chat_id == "10001"


def _parse_callback(module, config, client, user_id=10001):
    """构造并解析一条整理重试按钮回调。"""
    payload = {
        "callback_query": {
            "id": "callback-1",
            "from": {"id": user_id, "username": "tester"},
            "message": {"message_id": 88, "chat": {"id": 10001}},
            "data": "transfer_retry_12",
        },
    }
    client_config = SimpleNamespace(name="telegram-test", config=config)
    with patch.object(module, "get_config", return_value=client_config), patch.object(
        module, "get_instance", return_value=client
    ):
        return module.message_parser(
            source="telegram-test",
            body=json.dumps(payload),
            form=None,
            args={},
        )


def test_telegram_callback_rejects_user_outside_whitelist():
    """用户白名单外的群成员不得通过按钮回调操作机器人。"""
    module = TelegramModule()
    client = MagicMock()
    client.bot_username = "mp_bot"

    message = _parse_callback(
        module,
        {"TELEGRAM_USERS": "10001"},
        client,
        user_id=20002,
    )

    assert message is None
    client.answer_callback_query.assert_called_once_with(
        callback_query_id="callback-1",
        text="你不在用户白名单中，无法使用此机器人",
        show_alert=True,
    )


def test_telegram_transfer_callback_requires_configured_admin():
    """配置管理员后，整理重试按钮只允许管理员触发。"""
    module = TelegramModule()
    client = MagicMock()
    client.bot_username = "mp_bot"

    message = _parse_callback(
        module,
        {"TELEGRAM_ADMINS": "10001"},
        client,
        user_id=20002,
    )

    assert message is None
    client.answer_callback_query.assert_called_once_with(
        callback_query_id="callback-1",
        text="只有管理员才有权限执行此操作",
        show_alert=True,
    )


def test_telegram_transfer_callback_accepts_configured_admin():
    """管理员仍可正常触发整理重试按钮。"""
    module = TelegramModule()
    client = MagicMock()
    client.bot_username = "mp_bot"

    message = _parse_callback(
        module,
        {"TELEGRAM_ADMINS": "10001"},
        client,
        user_id=10001,
    )

    assert message is not None
    assert message.text == "CALLBACK:transfer_retry_12"
    client.answer_callback_query.assert_not_called()


def _parse_text_message(module, config, client, user_id=10001, text="/redo 1"):
    """构造并解析一条 Telegram 文本消息。"""
    payload = {
        "message": {
            "message_id": 101,
            "from": {"id": user_id, "username": "tester"},
            "chat": {"id": user_id, "type": "private"},
            "text": text,
        },
    }
    client_config = SimpleNamespace(name="telegram-test", config=config)
    with patch.object(module, "get_config", return_value=client_config), patch.object(
        module, "get_instance", return_value=client
    ):
        return module.message_parser(
            source="telegram-test",
            body=json.dumps(payload),
            form=None,
            args={},
        )


def test_telegram_command_rejects_user_outside_whitelist():
    """用户白名单外的用户不得通过斜杠命令绕过授权。"""
    module = TelegramModule()
    client = MagicMock()
    client.bot_username = "mp_bot"

    message = _parse_text_message(
        module,
        {"TELEGRAM_USERS": "10001"},
        client,
        user_id=20002,
    )

    assert message is None
    client.send_msg.assert_called_once_with(
        title="你不在用户白名单中，无法使用此机器人",
        userid=20002,
    )


def test_telegram_command_accepts_whitelisted_user_without_admin_config():
    """未配置管理员白名单时，普通白名单用户仍可使用命令。"""
    module = TelegramModule()
    client = MagicMock()
    client.bot_username = "mp_bot"

    message = _parse_text_message(
        module,
        {"TELEGRAM_USERS": "10001"},
        client,
        user_id=10001,
    )

    assert message is not None
    assert message.text == "/redo 1"
    client.send_msg.assert_not_called()


def test_telegram_unauthorized_message_is_safe_without_client_instance():
    """模块重载窗口中没有客户端实例时，拒绝逻辑也不应抛错。"""
    module = TelegramModule()

    message = _parse_text_message(
        module,
        {"TELEGRAM_USERS": "10001"},
        None,
        user_id=20002,
    )

    assert message is None


def test_should_process_message_skips_media_without_text(telegram):
    """纯媒体消息不应再转发到只处理文本命令的后端消息链。"""
    message = SimpleNamespace(
        chat=SimpleNamespace(type="private"),
        from_user=SimpleNamespace(id=10001),
        text=None,
        caption=None,
    )

    assert telegram._should_process_message(message) is False


def test_should_process_message_accepts_private_text(telegram):
    """私聊文本消息仍应进入命令处理链。"""
    message = SimpleNamespace(
        chat=SimpleNamespace(type="private"),
        from_user=SimpleNamespace(id=10001),
        text="/redo 1",
        caption=None,
    )

    assert telegram._should_process_message(message) is True


def test_send_msg_with_longtext(telegram):
    """测试发送长消息"""
    result = telegram.send_msg(
        title="MoviePilot助手",
        text="好的，为您推荐一些近期热门的电视剧：\n\n*   *怪奇物语 (Stranger Things)* - 2016年，TMDB评分8.6\n*   *小丑回魂：欢迎来到德里镇* - 2025年，TMDB评分8.0\n*   *维京传奇* - 2013年，TMDB评分8.1\n*   *地狱客栈* - 2024年，TMDB评分8.7\n*   *超人回来了* - 2013年，TMDB评分7.7\n\n还有一些经典剧集也一直很受欢迎：\n\n*   *法律与秩序：特殊受害者* - 1999年，TMDB评分7.9\n*   *实习医生格蕾* - 2005年，TMDB评分8.2\n*   *邪恶力量* - 2005年，TMDB评分8.3\n*   *菜鸟老警* - 2018年，TMDB评分8.5\n*   *猎魔人* - 2019年，TMDB评分8.0\n*   *海军罪案调查处* - 2003年，TMDB评分7.6\n*   *塔尔萨之王* - 2022年，TMDB评分8.3\n*   *武士生死斗* - 2025年，TMDB评分8.1\n*   *嗜血法医* - 2006年，TMDB评分8.2\n*   *辛普森一家* - 1989年，TMDB评分8.0\n*   *无耻之徒* - 2011年，TMDB评分8.2\n*   *绝命毒师* - 2008年，TMDB评分8.9\n*   *法律与秩序* - 1990年，TMDB评分7.4\n*   *权力的游戏* - 2011年，TMDB评分8.5\n\n您对哪部剧比较感兴趣，或者想了解更多信息呢？好的，为您推荐一些近期热门的电视剧：\n\n*   *怪奇物语 (Stranger Things)* - 2016年，TMDB评分8.6\n*   *小丑回魂：欢迎来到德里镇* - 2025年，TMDB评分8.0\n*   *维京传奇* - 2013年，TMDB评分8.1\n*   *地狱客栈* - 2024年，TMDB评分8.7\n*   *超人回来了* - 2013年，TMDB评分7.7\n\n还有一些经典剧集也一直很受欢迎：\n\n*   *法律与秩序：特殊受害者* - 1999年，TMDB评分7.9\n*   *实习医生格蕾* - 2005年，TMDB评分8.2\n*   *邪恶力量* - 2005年，TMDB评分8.3\n*   *菜鸟老警* - 2018年，TMDB评分8.5\n*   *猎魔人* - 2019年，TMDB评分8.0\n*   *海军罪案调查处* - 2003年，TMDB评分7.6\n*   *塔尔萨之王* - 2022年，TMDB评分8.3\n*   *武士生死斗* - 2025年，TMDB评分8.1\n*   *嗜血法医* - 2006年，TMDB评分8.2\n*   *辛普森一家* - 1989年，TMDB评分8.0\n*   *无耻之徒* - 2011年，TMDB评分8.2\n*   *绝命毒师* - 2008年，TMDB评分8.9\n*   *法律与秩序* - 1990年，TMDB评分7.4\n*   *权力的游戏* - 2011年，TMDB评分8.5\n\n您对哪部剧比较感兴趣，或者想了解更多信息呢？好的，为您推荐一些近期热门的电视剧：\n\n*   *怪奇物语 (Stranger Things)* - 2016年，TMDB评分8.6\n*   *小丑回魂：欢迎来到德里镇* - 2025年，TMDB评分8.0\n*   *维京传奇* - 2013年，TMDB评分8.1\n*   *地狱客栈* - 2024年，TMDB评分8.7\n*   *超人回来了* - 2013年，TMDB评分7.7\n\n还有一些经典剧集也一直很受欢迎：\n\n*   *法律与秩序：特殊受害者* - 1999年，TMDB评分7.9\n*   *实习医生格蕾* - 2005年，TMDB评分8.2\n*   *邪恶力量* - 2005年，TMDB评分8.3\n*   *菜鸟老警* - 2018年，TMDB评分8.5\n*   *猎魔人* - 2019年，TMDB评分8.0\n*   *海军罪案调查处* - 2003年，TMDB评分7.6\n*   *塔尔萨之王* - 2022年，TMDB评分8.3\n*   *武士生死斗* - 2025年，TMDB评分8.1\n*   *嗜血法医* - 2006年，TMDB评分8.2\n*   *辛普森一家* - 1989年，TMDB评分8.0\n*   *无耻之徒* - 2011年，TMDB评分8.2\n*   *绝命毒师* - 2008年，TMDB评分8.9\n*   *法律与秩序* - 1990年，TMDB评分7.4\n*   *权力的游戏* - 2011年，TMDB评分8.5\n\n您对哪部剧比较感兴趣，或者想了解更多信息呢？好的，为您推荐一些近期热门的电视剧：\n\n*   *怪奇物语 (Stranger Things)* - 2016年，TMDB评分8.6\n*   *小丑回魂：欢迎来到德里镇* - 2025年，TMDB评分8.0\n*   *维京传奇* - 2013年，TMDB评分8.1\n*   *地狱客栈* - 2024年，TMDB评分8.7\n*   *超人回来了* - 2013年，TMDB评分7.7\n\n还有一些经典剧集也一直很受欢迎：\n\n*   *法律与秩序：特殊受害者* - 1999年，TMDB评分7.9\n*   *实习医生格蕾* - 2005年，TMDB评分8.2\n*   *邪恶力量* - 2005年，TMDB评分8.3\n*   *菜鸟老警* - 2018年，TMDB评分8.5\n*   *猎魔人* - 2019年，TMDB评分8.0\n*   *海军罪案调查处* - 2003年，TMDB评分7.6\n*   *塔尔萨之王* - 2022年，TMDB评分8.3\n*   *武士生死斗* - 2025年，TMDB评分8.1\n*   *嗜血法医* - 2006年，TMDB评分8.2\n*   *辛普森一家* - 1989年，TMDB评分8.0\n*   *无耻之徒* - 2011年，TMDB评分8.2\n*   *绝命毒师* - 2008年，TMDB评分8.9\n*   *法律与秩序* - 1990年，TMDB评分7.4\n*   *权力的游戏* - 2011年，TMDB评分8.5\n\n您对哪部剧比较感兴趣，或者想了解更多信息呢？好的，为您推荐一些近期热门的电视剧：\n\n*   *怪奇物语 (Stranger Things)* - 2016年，TMDB评分8.6\n*   *小丑回魂：欢迎来到德里镇* - 2025年，TMDB评分8.0\n*   *维京传奇* - 2013年，TMDB评分8.1\n*   *地狱客栈* - 2024年，TMDB评分8.7\n*   *超人回来了* - 2013年，TMDB评分7.7\n\n还有一些经典剧集也一直很受欢迎：\n\n*   *法律与秩序：特殊受害者* - 1999年，TMDB评分7.9\n*   *实习医生格蕾* - 2005年，TMDB评分8.2\n*   *邪恶力量* - 2005年，TMDB评分8.3\n*   *菜鸟老警* - 2018年，TMDB评分8.5\n*   *猎魔人* - 2019年，TMDB评分8.0\n*   *海军罪案调查处* - 2003年，TMDB评分7.6\n*   *塔尔萨之王* - 2022年，TMDB评分8.3\n*   *武士生死斗* - 2025年，TMDB评分8.1\n*   *嗜血法医* - 2006年，TMDB评分8.2\n*   *辛普森一家* - 1989年，TMDB评分8.0\n*   *无耻之徒* - 2011年，TMDB评分8.2\n*   *绝命毒师* - 2008年，TMDB评分8.9\n*   *法律与秩序* - 1990年，TMDB评分7.4\n*   *权力的游戏* - 2011年，TMDB评分8.5\n\n您对哪部剧比较感兴趣，或者想了解更多信息呢？好的，为您推荐一些近期热门的电视剧：\n\n*   *怪奇物语 (Stranger Things)* - 2016年，TMDB评分8.6\n*   *小丑回魂：欢迎来到德里镇* - 2025年，TMDB评分8.0\n*   *维京传奇* - 2013年，TMDB评分8.1\n*   *地狱客栈* - 2024年，TMDB评分8.7\n*   *超人回来了* - 2013年，TMDB评分7.7\n\n还有一些经典剧集也一直很受欢迎：\n\n*   *法律与秩序：特殊受害者* - 1999年，TMDB评分7.9\n*   *实习医生格蕾* - 2005年，TMDB评分8.2\n*   *邪恶力量* - 2005年，TMDB评分8.3\n*   *菜鸟老警* - 2018年，TMDB评分8.5\n*   *猎魔人* - 2019年，TMDB评分8.0\n*   *海军罪案调查处* - 2003年，TMDB评分7.6\n*   *塔尔萨之王* - 2022年，TMDB评分8.3\n*   *武士生死斗* - 2025年，TMDB评分8.1\n*   *嗜血法医* - 2006年，TMDB评分8.2\n*   *辛普森一家* - 1989年，TMDB评分8.0\n*   *无耻之徒* - 2011年，TMDB评分8.2\n*   *绝命毒师* - 2008年，TMDB评分8.9\n*   *法律与秩序* - 1990年，TMDB评分7.4\n*   *权力的游戏* - 2011年，TMDB评分8.5\n\n您对哪部剧比较感兴趣，或者想了解更多信息呢？好的，为您推荐一些近期热门的电视剧：\n\n*   *怪奇物语 (Stranger Things)* - 2016年，TMDB评分8.6\n*   *小丑回魂：欢迎来到德里镇* - 2025年，TMDB评分8.0\n*   *维京传奇* - 2013年，TMDB评分8.1\n*   *地狱客栈* - 2024年，TMDB评分8.7\n*   *超人回来了* - 2013年，TMDB评分7.7\n\n还有一些经典剧集也一直很受欢迎：\n\n*   *法律与秩序：特殊受害者* - 1999年，TMDB评分7.9\n*   *实习医生格蕾* - 2005年，TMDB评分8.2\n*   *邪恶力量* - 2005年，TMDB评分8.3\n*   *菜鸟老警* - 2018年，TMDB评分8.5\n*   *猎魔人* - 2019年，TMDB评分8.0\n*   *海军罪案调查处* - 2003年，TMDB评分7.6\n*   *塔尔萨之王* - 2022年，TMDB评分8.3\n*   *武士生死斗* - 2025年，TMDB评分8.1\n*   *嗜血法医* - 2006年，TMDB评分8.2\n*   *辛普森一家* - 1989年，TMDB评分8.0\n*   *无耻之徒* - 2011年，TMDB评分8.2\n*   *绝命毒师* - 2008年，TMDB评分8.9\n*   *法律与秩序* - 1990年，TMDB评分7.4\n*   *权力的游戏* - 2011年，TMDB评分8.5\n\n您对哪部剧比较感兴趣，或者想了解更多信息呢？好的，为您推荐一些近期热门的电视剧：\n\n*   *怪奇物语 (Stranger Things)* - 2016年，TMDB评分8.6\n*   *小丑回魂：欢迎来到德里镇* - 2025年，TMDB评分8.0\n*   *维京传奇* - 2013年，TMDB评分8.1\n*   *地狱客栈* - 2024年，TMDB评分8.7\n*   *超人回来了* - 2013年，TMDB评分7.7\n\n还有一些经典剧集也一直很受欢迎：\n\n*   *法律与秩序：特殊受害者* - 1999年，TMDB评分7.9\n*   *实习医生格蕾* - 2005年，TMDB评分8.2\n*   *邪恶力量* - 2005年，TMDB评分8.3\n*   *菜鸟老警* - 2018年，TMDB评分8.5\n*   *猎魔人* - 2019年，TMDB评分8.0\n*   *海军罪案调查处* - 2003年，TMDB评分7.6\n*   *塔尔萨之王* - 2022年，TMDB评分8.3\n*   *武士生死斗* - 2025年，TMDB评分8.1\n*   *嗜血法医* - 2006年，TMDB评分8.2\n*   *辛普森一家* - 1989年，TMDB评分8.0\n*   *无耻之徒* - 2011年，TMDB评分8.2\n*   *绝命毒师* - 2008年，TMDB评分8.9\n*   *法律与秩序* - 1990年，TMDB评分7.4\n*   *权力的游戏* - 2011年，TMDB评分8.5\n\n您对哪部剧比较感兴趣，或者想了解更多信息呢？好的，为您推荐一些近期热门的电视剧：\n\n*   *怪奇物语 (Stranger Things)* - 2016年，TMDB评分8.6\n*   *小丑回魂：欢迎来到德里镇* - 2025年，TMDB评分8.0\n*   *维京传奇* - 2013年，TMDB评分8.1\n*   *地狱客栈* - 2024年，TMDB评分8.7\n*   *超人回来了* - 2013年，TMDB评分7.7\n\n还有一些经典剧集也一直很受欢迎：\n\n*   *法律与秩序：特殊受害者* - 1999年，TMDB评分7.9\n*   *实习医生格蕾* - 2005年，TMDB评分8.2\n*   *邪恶力量* - 2005年，TMDB评分8.3\n*   *菜鸟老警* - 2018年，TMDB评分8.5\n*   *猎魔人* - 2019年，TMDB评分8.0\n*   *海军罪案调查处* - 2003年，TMDB评分7.6\n*   *塔尔萨之王* - 2022年，TMDB评分8.3\n*   *武士生死斗* - 2025年，TMDB评分8.1\n*   *嗜血法医* - 2006年，TMDB评分8.2\n*   *辛普森一家* - 1989年，TMDB评分8.0\n*   *无耻之徒* - 2011年，TMDB评分8.2\n*   *绝命毒师* - 2008年，TMDB评分8.9\n*   *法律与秩序* - 1990年，TMDB评分7.4\n*   *权力的游戏* - 2011年，TMDB评分8.5\n\n您对哪部剧比较感兴趣，或者想了解更多信息呢？好的，为您推荐一些近期热门的电视剧：\n\n*   *怪奇物语 (Stranger Things)* - 2016年，TMDB评分8.6\n*   *小丑回魂：欢迎来到德里镇* - 2025年，TMDB评分8.0\n*   *维京传奇* - 2013年，TMDB评分8.1\n*   *地狱客栈* - 2024年，TMDB评分8.7\n*   *超人回来了* - 2013年，TMDB评分7.7\n\n还有一些经典剧集也一直很受欢迎：\n\n*   *法律与秩序：特殊受害者* - 1999年，TMDB评分7.9\n*   *实习医生格蕾* - 2005年，TMDB评分8.2\n*   *邪恶力量* - 2005年，TMDB评分8.3\n*   *菜鸟老警* - 2018年，TMDB评分8.5\n*   *猎魔人* - 2019年，TMDB评分8.0\n*   *海军罪案调查处* - 2003年，TMDB评分7.6\n*   *塔尔萨之王* - 2022年，TMDB评分8.3\n*   *武士生死斗* - 2025年，TMDB评分8.1\n*   *嗜血法医* - 2006年，TMDB评分8.2\n*   *辛普森一家* - 1989年，TMDB评分8.0\n*   *无耻之徒* - 2011年，TMDB评分8.2\n*   *绝命毒师* - 2008年，TMDB评分8.9\n*   *法律与秩序* - 1990年，TMDB评分7.4\n*   *权力的游戏* - 2011年，TMDB评分8.5\n\n您对哪部剧比较感兴趣，或者想了解更多信息呢？好的，为您推荐一些近期热门的电视剧：\n\n*   *怪奇物语 (Stranger Things)* - 2016年，TMDB评分8.6\n*   *小丑回魂：欢迎来到德里镇* - 2025年，TMDB评分8.0\n*   *维京传奇* - 2013年，TMDB评分8.1\n*   *地狱客栈* - 2024年，TMDB评分8.7\n*   *超人回来了* - 2013年，TMDB评分7.7\n\n还有一些经典剧集也一直很受欢迎：\n\n*   *法律与秩序：特殊受害者* - 1999年，TMDB评分7.9\n*   *实习医生格蕾* - 2005年，TMDB评分8.2\n*   *邪恶力量* - 2005年，TMDB评分8.3\n*   *菜鸟老警* - 2018年，TMDB评分8.5\n*   *猎魔人* - 2019年，TMDB评分8.0\n*   *海军罪案调查处* - 2003年，TMDB评分7.6\n*   *塔尔萨之王* - 2022年，TMDB评分8.3\n*   *武士生死斗* - 2025年，TMDB评分8.1\n*   *嗜血法医* - 2006年，TMDB评分8.2\n*   *辛普森一家* - 1989年，TMDB评分8.0\n*   *无耻之徒* - 2011年，TMDB评分8.2\n*   *绝命毒师* - 2008年，TMDB评分8.9\n*   *法律与秩序* - 1990年，TMDB评分7.4\n*   *权力的游戏* - 2011年，TMDB评分8.5\n\n您对哪部剧比较感兴趣，或者想了解更多信息呢？好的，为您推荐一些近期热门的电视剧：\n\n*   *怪奇物语 (Stranger Things)* - 2016年，TMDB评分8.6\n*   *小丑回魂：欢迎来到德里镇* - 2025年，TMDB评分8.0\n*   *维京传奇* - 2013年，TMDB评分8.1\n*   *地狱客栈* - 2024年，TMDB评分8.7\n*   *超人回来了* - 2013年，TMDB评分7.7\n\n还有一些经典剧集也一直很受欢迎：\n\n*   *法律与秩序：特殊受害者* - 1999年，TMDB评分7.9\n*   *实习医生格蕾* - 2005年，TMDB评分8.2\n*   *邪恶力量* - 2005年，TMDB评分8.3\n*   *菜鸟老警* - 2018年，TMDB评分8.5\n*   *猎魔人* - 2019年，TMDB评分8.0\n*   *海军罪案调查处* - 2003年，TMDB评分7.6\n*   *塔尔萨之王* - 2022年，TMDB评分8.3\n*   *武士生死斗* - 2025年，TMDB评分8.1\n*   *嗜血法医* - 2006年，TMDB评分8.2\n*   *辛普森一家* - 1989年，TMDB评分8.0\n*   *无耻之徒* - 2011年，TMDB评分8.2\n*   *绝命毒师* - 2008年，TMDB评分8.9\n*   *法律与秩序* - 1990年，TMDB评分7.4\n*   *权力的游戏* - 2011年，TMDB评分8.5\n\n您对哪部剧比较感兴趣，或者想了解更多信息呢？",
    )
    assert result and result.get("success")

def test_send_msg_with_buttons_and_link(telegram):
    """测试发送带按钮和链接的消息"""
    buttons = [[
        {"text": "测试按钮", "callback_data": "test_callback"}
    ]]

    result = telegram.send_msg(
        title="测试标题",
        text="*测试内容*",
        link="http://example.com",
        buttons=buttons
    )

    # 验证返回值：send_msg 失败时返回 {"success": False}（非空字典），故显式断言 success
    assert result and result.get("success")

def test_send_msg_with_url_buttons(telegram):
    """测试发送带URL按钮的消息"""
    buttons = [[
        {"text": "URL按钮", "url": "http://example.com"}
    ]]

    result = telegram.send_msg(
        title="测试标题",
        text="测试内容",
        buttons=buttons
    )

    # 验证返回值：send_msg 失败时返回 {"success": False}（非空字典），故显式断言 success
    assert result and result.get("success")


def test_send_msg_markdown_escaping(telegram):
    """测试Markdown特殊字符转义"""
    result = telegram.send_msg(
        title="测试标题",
        text="_测试_||内容||"
    )

    # 验证返回值：send_msg 失败时返回 {"success": False}（非空字典），故显式断言 success
    assert result and result.get("success")
    send_kwargs = telegram.bot.send_message.call_args.kwargs
    assert send_kwargs["parse_mode"] == "MarkdownV2"
    assert send_kwargs["text"].startswith("*测试标题*\n")


def test_telegramify_current_fields_are_used_directly():
    """telegramify 对象直接使用当前 MarkdownV2 字段"""
    from telegramify_markdown.content import ContentTrace, File, Text

    text_item = Text(
        text="已转义_文本",
        entities=[],
        content_trace=ContentTrace(source_type="test"),
    )
    file_item = File(
        file_name="test.txt",
        file_data=b"test",
        caption_text="已转义_说明",
        caption_entities=[],
        content_trace=ContentTrace(source_type="test"),
    )

    with warnings.catch_warnings(record=True) as warning_records:
        warnings.simplefilter("always")
        assert Telegram._telegramify_item_text(text_item) == "已转义\\_文本"
        assert Telegram._telegramify_item_caption(file_item) == "已转义\\_说明"

    assert not warning_records


def test_telegram_module_post_message_passes_active_fields_to_client():
    """模块发送通知时只透传当前仍有生产者的消息字段。"""
    module = TelegramModule()
    client = Mock()
    buttons = [[{"text": "重试", "callback_data": "transfer_retry_1"}]]

    with patch.object(
        module,
        "get_configs",
        return_value={"telegram-test": SimpleNamespace(name="telegram-test")},
    ), patch.object(
        module, "check_message", return_value=True
    ), patch.object(
        module, "get_instance", return_value=client
    ):
        module.post_message(
            Notification(
                channel=MessageChannel.Telegram,
                source="telegram-test",
                title="入库失败",
                text="原因：识别失败",
                image="https://example.com/poster.jpg",
                userid="10001",
                link="https://example.com/#/history",
                buttons=buttons,
            )
        )

    client.send_msg.assert_called_once_with(
        title="入库失败",
        text="原因：识别失败",
        image="https://example.com/poster.jpg",
        userid="10001",
        link="https://example.com/#/history",
        buttons=buttons,
    )
