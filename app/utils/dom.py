import re


class DomUtils:

    _INVALID_XML_CHARS_RE = re.compile(
        r"[^\x09\x0a\x0d\x20-\ud7ff\ue000-\ufffd\U00010000-\U0010ffff]"
    )

    @staticmethod
    def sanitize_xml_text(value) -> str:
        """
        移除 XML 1.0 不允许的字符，避免外部元数据使 NFO 不可解析。
        """
        return DomUtils._INVALID_XML_CHARS_RE.sub("", str(value))

    @staticmethod
    def append_cdata(doc, parent, value) -> None:
        """
        追加保留原文语义的 CDATA 内容。

        ``]]>`` 不能出现在单个 CDATA 节点中，因此将其拆到相邻节点边界：
        前半段以 ``]]`` 结束，后半段以 ``>`` 开始，XML 解析后会重新拼成原文。
        """
        text = DomUtils.sanitize_xml_text(value or "")
        parts = text.split("]]>")
        for index, part in enumerate(parts):
            segment = part
            if index < len(parts) - 1:
                segment += "]]"
            if index > 0:
                segment = ">" + segment
            if segment:
                parent.appendChild(doc.createCDATASection(segment))

    @staticmethod
    def add_node(doc, parent, name: str, value: str = None):
        """
        添加一个DOM节点
        """
        node = doc.createElement(name)
        parent.appendChild(node)
        if value is not None:
            text = doc.createTextNode(DomUtils.sanitize_xml_text(value))
            node.appendChild(text)
        return node
