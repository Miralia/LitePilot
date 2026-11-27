import ast
import dis
import inspect
import textwrap
from types import FunctionType
from typing import Any, Callable, get_type_hints, get_origin


class ObjectUtils:

    @staticmethod
    def arguments(func: Callable) -> int:
        """
        返回函数的参数个数
        """
        signature = inspect.signature(func)
        parameters = signature.parameters

        return len(list(parameters.keys()))

    @staticmethod
    def check_method(func: Callable[..., Any]) -> bool:
        """
        检查函数是否已实现
        """
        try:
            src = inspect.getsource(func)
            tree = ast.parse(textwrap.dedent(src))
            node = tree.body[0]
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return True
            body = node.body

            for stmt in body:
                # 跳过 pass
                if isinstance(stmt, ast.Pass):
                    continue
                # 跳过 docstring 或 ...
                if isinstance(stmt, ast.Expr):
                    expr = stmt.value
                    if isinstance(expr, ast.Constant):
                        if isinstance(expr.value, str) or expr.value is Ellipsis:
                            continue
                # 检查 raise NotImplementedError
                if isinstance(stmt, ast.Raise):
                    exc = stmt.exc
                    if isinstance(exc, ast.Call) and getattr(exc.func, "id", None) == "NotImplementedError":
                        continue
                    if isinstance(exc, ast.Name) and exc.id == "NotImplementedError":
                        continue

                return True
            return False
        except Exception as err:
            print(err)
            # 源代码分析失败时，进行字节码分析
            code_obj = func.__code__  # type: ignore[attr-defined]
            instructions = list(dis.get_instructions(code_obj))
            # 检查是否为仅返回None的简单结构
            if len(instructions) == 2:
                first, second = instructions
                if (first.opname == 'LOAD_CONST' and
                        second.opname == 'RETURN_VALUE'):
                    # 验证加载的常量是否为None
                    const_index = first.arg
                    if (const_index < len(code_obj.co_consts) and
                            code_obj.co_consts[const_index] is None):
                        # 未实现的空函数
                        return False
            # 其他情况认为已实现
            return True

    @staticmethod
    def check_signature(func: FunctionType, *args) -> bool:
        """
        检查输出与函数的参数类型是否一致
        """
        # 获取函数的参数信息
        signature = inspect.signature(func)
        parameters = signature.parameters
        if len(args) != len(parameters):
            return False
        try:
            # 获取解析后的类型提示；无法解析的注解不应中断模块链
            type_hints = get_type_hints(func)
        except (TypeError, NameError, SyntaxError):
            type_hints = {}
        for arg, (param_name, param) in zip(args, parameters.items()):
            # 优先使用解析后的类型提示
            param_type = type_hints.get(param_name, None)
            if param_type is None:
                # 处理原始注解（可能为字符串或Cython类型）
                param_annotation = param.annotation
                if param_annotation is inspect.Parameter.empty:
                    continue
                # get_type_hints 已统一解析字符串注解；仍无法解析时按无类型约束处理
                if isinstance(param_annotation, str):
                    continue
                param_type = param_annotation
            if param_type is None:
                continue
            try:
                matches = isinstance(arg, param_type)
            except TypeError:
                # list[int] 等泛型容器不能直接 isinstance，降级校验容器本身；
                # Literal/Annotated 等特殊 typing 形式无法安全校验时维持无类型约束
                origin = get_origin(param_type)
                if origin is None or not isinstance(origin, type):
                    continue
                matches = isinstance(arg, origin)
            if not matches:
                return False
        return True
