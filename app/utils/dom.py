class DomUtils:

    @staticmethod
    def add_node(doc, parent, name: str, value: str = None):
        """
        添加一个DOM节点
        """
        node = doc.createElement(name)
        parent.appendChild(node)
        if value is not None:
            text = doc.createTextNode(str(value))
            node.appendChild(text)
        return node
