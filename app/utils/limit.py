import threading


class ExponentialBackoffRateLimiter:
    """
    指数退避等待计时器。

    事件队列空闲时逐步延长下一轮等待时间，成功取得事件后恢复基础等待时间。
    当前产品只存在这一处退避消费者，因此不再保留通用限流装饰器接口。
    """

    def __init__(
        self,
        base_wait: float = 60.0,
        max_wait: float = 600.0,
        backoff_factor: float = 2.0,
    ):
        """
        初始化指数退避等待计时器。

        :param base_wait: 基础等待时间（秒）
        :param max_wait: 最大等待时间（秒）
        :param backoff_factor: 每次空闲后的等待时间递增倍数
        """
        self.current_wait = base_wait
        self.base_wait = base_wait
        self.max_wait = max_wait
        self.backoff_factor = backoff_factor
        self.lock = threading.Lock()

    def reset(self):
        """
        成功取得事件后恢复基础等待时间。
        """
        with self.lock:
            self.current_wait = self.base_wait

    def trigger_limit(self):
        """
        队列空闲后按倍率延长等待时间，且不超过配置上限。
        """
        with self.lock:
            self.current_wait = min(
                self.current_wait * self.backoff_factor, self.max_wait
            )
