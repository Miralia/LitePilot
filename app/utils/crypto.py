from hashlib import md5
from typing import Union


class HashUtils:
    """提供当前业务仍需要的字符串哈希工具。"""

    @staticmethod
    def md5(data: Union[str, bytes], encoding: str = "utf-8") -> str:
        """
        生成数据的MD5哈希值，并以字符串形式返回

        :param data: 输入的数据，类型为字符串
        :param encoding: 字符串编码类型，默认使用UTF-8
        :return: 生成的MD5哈希字符串
        """
        if isinstance(data, str):
            data = data.encode(encoding)
        return md5(data).hexdigest()
