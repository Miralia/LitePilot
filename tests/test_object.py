from app.utils.object import ObjectUtils


def test_check_method():
    def implemented_function():
        return "Hello"

    def pass_function():
        pass

    def docstring_function():
        """This is a docstring."""

    def ellipsis_function():
        ...

    def not_implemented_function():
        raise NotImplementedError

    def not_implemented_function_with_call():
        raise NotImplementedError()

    async def multiple_lines_async_def(_param1: str,
                                       _param2: str):
        pass

    def empty_function():
        return

    assert ObjectUtils.check_method(implemented_function)
    assert not ObjectUtils.check_method(pass_function)
    assert not ObjectUtils.check_method(docstring_function)
    assert not ObjectUtils.check_method(ellipsis_function)
    assert not ObjectUtils.check_method(not_implemented_function)
    assert not ObjectUtils.check_method(not_implemented_function_with_call)
    assert not ObjectUtils.check_method(multiple_lines_async_def)
    assert ObjectUtils.check_method(empty_function)


def test_check_signature_matches_runtime_type():
    """模块链只在结果类型与下一处理器入参一致时传递结果。"""
    def target(value: int):
        return value

    assert ObjectUtils.check_signature(target, 1) is True
    assert ObjectUtils.check_signature(target, "1") is False


def test_check_signature_unresolved_annotation_is_unconstrained():
    """无法解析的字符串注解不得中断模块链，应按既有语义视为无类型约束。"""
    def target(value: "MissingRuntimeType"):
        return value

    assert ObjectUtils.check_signature(target, object()) is True


def test_check_signature_matches_generic_container_origin():
    """泛型容器注解按容器类型校验，元素泛型不应使模块链抛出 TypeError。"""
    def target(values: list[int]):
        return values

    assert ObjectUtils.check_signature(target, [1]) is True
    assert ObjectUtils.check_signature(target, {"value": 1}) is False
