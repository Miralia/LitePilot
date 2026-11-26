import datetime


class TimerUtils:
    """
    定时与时间差计算工具。
    """

    @staticmethod
    def time_difference(input_datetime: datetime) -> str:
        """
        判断输入时间与当前的时间差，如果输入时间大于当前时间则返回时间差，否则返回空字符串
        """
        if not input_datetime:
            return ""
        current_datetime = datetime.datetime.now(datetime.timezone.utc).astimezone()
        time_difference = input_datetime - current_datetime

        if time_difference.total_seconds() < 0:
            return ""

        days = time_difference.days
        hours, remainder = divmod(time_difference.seconds, 3600)
        minutes, second = divmod(remainder, 60)

        time_difference_string = ""
        if days > 0:
            time_difference_string += f"{days}天"
        if hours > 0:
            time_difference_string += f"{hours}小时"
        if minutes > 0:
            time_difference_string += f"{minutes}分钟"
        if not time_difference_string and second:
            time_difference_string = f"{second}秒"

        return time_difference_string
