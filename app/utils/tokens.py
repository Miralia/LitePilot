import re


class Tokens:
    """
    按分隔符切分文本，并提供顺序消费与归属登记能力。

    归属登记用于避免同一个词被反复认领：片名一旦占用了某个 token，
    制作组等其他字段就不得再把它当作自己的内容。缺少这层约束时，
    片名里的常见词（例如 Paris）会同时被匹配成组名。
    """
    _text: str = ""
    _index: int = 0
    _tokens: list = []
    _owners: dict = None

    def __init__(self, text):
        self._text = text
        self._tokens = []
        self._owners = {}
        self.load_text(text)

    def load_text(self, text):
        splitted_text = re.split(r"\.|\s+|\(|\)|\[|]|-|【|】|/|～|;|&|\||#|_|「|」|~", text)
        for sub_text in splitted_text:
            if sub_text:
                self._tokens.append(sub_text)

    def cur(self):
        if self._index >= len(self._tokens):
            return None
        else:
            token = self._tokens[self._index]
            return token

    def get_next(self):
        token = self.cur()
        if token:
            self._index = self._index + 1
        return token

    def peek(self):
        index = self._index + 1
        if index >= len(self._tokens):
            return None
        else:
            return self._tokens[index]

    def peek_at(self, index):
        """
        读取指定位置的 token，不移动游标。

        :param index: token 索引
        :return: 该位置的 token，越界时返回 None
        """
        if index is None or index < 0 or index >= len(self._tokens):
            return None
        return self._tokens[index]

    def claim(self, index, owner: str) -> None:
        """
        登记某个 token 的归属。

        已登记的 token 不会被后续字段重复认领，先到先得。

        :param index: token 索引
        :param owner: 归属字段名，如 "name"
        """
        if index is None or index < 0 or index >= len(self._tokens):
            return
        self._owners.setdefault(index, owner)

    def is_claimed(self, index) -> bool:
        """
        判断 token 是否已被任一方认领。

        :param index: token 索引
        :return: 已认领返回 True
        """
        return index in self._owners

    def owners(self) -> dict:
        """
        返回 token 索引到归属字段的映射副本。
        """
        return dict(self._owners)

    def claimed_texts(self, owner: str = None) -> set:
        """
        收集已被认领的 token 文本。

        制作组等基于全文正则的匹配只能拿到文本，因此需要按文本反查：
        该文本归一化后若命中已认领集合，说明它已属于其它字段。

        :param owner: 只统计该归属字段；为 None 时统计全部
        :return: 已认领 token 的文本集合
        """
        result = set()
        for index, holder in self._owners.items():
            if owner is not None and holder != owner:
                continue
            if 0 <= index < len(self._tokens):
                result.add(self._tokens[index])
        return result

    @property
    def tokens(self):
        return self._tokens
