"""上游通用工具残留边界测试。"""

from pathlib import Path

import app.core.cache as core_cache
import app.utils.gc as memory_utils
import app.utils.singleton as singleton_utils

from app.helper import message
from app.utils import dom, http, ip, limit, media, security, system, timer, tokens, url


def test_xml_cache_ip_and_url_dead_helpers_are_removed():
    """站点采集和上游通用请求适配移除后，不保留无调用工具。"""
    assert not hasattr(dom.DomUtils, "tag_value")
    assert not hasattr(http.RequestUtils, "parse_cache_control")
    assert not hasattr(ip.IpUtils, "is_ipv4")
    assert not hasattr(ip.IpUtils, "is_ipv6")
    assert not hasattr(url.UrlUtils, "adapt_request_url")


def test_unwired_rate_limiter_abstractions_are_removed():
    """当前只使用指数退避限流器，不保留未接线窗口、组合和装饰器抽象。"""
    assert hasattr(limit, "ExponentialBackoffRateLimiter")
    assert not hasattr(limit, "BaseRateLimiter")
    assert not hasattr(limit, "WindowRateLimiter")
    assert not hasattr(limit, "CompositeRateLimiter")
    assert not hasattr(limit, "rate_limit_handler")
    for name in ("can_call", "reset_on_success", "record_call"):
        assert not hasattr(limit.ExponentialBackoffRateLimiter, name)


def test_dead_security_wrappers_and_system_utilities_are_removed():
    """安全校验主链路直接使用诊断结果，不保留同步/异步私有包装和上游系统工具。"""
    for name in (
        "_is_global_hostname",
        "_is_global_hostname_async",
        "_is_allowed_private_hostname",
        "_is_allowed_private_hostname_async",
    ):
        assert not hasattr(security.SecurityUtils, name)
    for name in (
        "is_synology",
        "exits_files",
        "list_sub_files",
        "is_hardlink",
        "generate_user_unique_id",
    ):
        assert not hasattr(system.SystemUtils, name)


def test_dead_timer_token_media_and_message_helpers_are_removed():
    """识别、通知和调度主链路未消费的 helper 不作为通用库保留。"""
    assert not hasattr(timer.TimerUtils, "SCHEDULE_TRIGGER_TYPES")
    assert not hasattr(timer.TimerUtils, "normalize_schedule_trigger")
    assert not hasattr(timer.TimerUtils, "build_schedule_trigger")
    for name in (
        "get_schedule_next_run_time",
        "random_scheduler",
        "random_even_scheduler",
        "diff_minutes",
    ):
        assert not hasattr(timer.TimerUtils, name)
    assert not hasattr(tokens.Tokens, "peek_at")
    assert not hasattr(media, "build_media_key")
    assert not hasattr(message.MessageQueueManager, "_time_to_minutes")


def test_dead_memory_decorators_and_http_convenience_methods_are_removed():
    """调度只读取内存指标，外部请求也不保留无消费者的 PUT/DELETE/JSON 便捷包装。"""
    for name in ("memory_gc", "memory_monitor", "memory_cleanup", "auto_gc", "memory_watch"):
        assert not hasattr(memory_utils, name)
    for cls in (http.RequestUtils, http.AsyncRequestUtils):
        for name in ("put_res", "delete_res", "get_json", "post_json"):
            assert not hasattr(cls, name)


def test_test_only_structures_utility_is_removed_with_its_tests():
    """ListUtils 只有测试消费者，工具和对应测试一起移除。"""
    assert not Path("app/utils/structures.py").exists()
    assert not Path("tests/test_structures.py").exists()


def test_exponential_backoff_limiter_preserves_event_loop_backoff_semantics():
    """事件队列只依赖当前等待时间的指数增长、上限和成功重置。"""
    limiter = limit.ExponentialBackoffRateLimiter(
        base_wait=1.0,
        max_wait=3.0,
        backoff_factor=2.0,
    )
    assert limiter.current_wait == 1.0
    limiter.trigger_limit()
    assert limiter.current_wait == 2.0
    limiter.trigger_limit()
    assert limiter.current_wait == 3.0
    limiter.reset()
    assert limiter.current_wait == 1.0


def test_unused_singleton_and_cache_compatibility_wrappers_are_removed():
    """当前单例与缓存调用方直接使用具体能力，不保留上游抽象兼容外壳。"""
    assert not hasattr(singleton_utils, "AbstractSingleton")
    assert not hasattr(singleton_utils, "AbstractSingletonClass")
    assert hasattr(core_cache, "TTLCache")
    assert not hasattr(core_cache, "LRUCache")
