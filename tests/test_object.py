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
