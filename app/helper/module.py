# -*- coding: utf-8 -*-
import importlib
import pkgutil
import traceback
from typing import List, Any, Callable

from app.log import logger

FilterFuncType = Callable[[str, Any], bool]


def _default_filter(name: str, obj: Any) -> bool:
    """
    默认过滤器
    """
    return True if name and obj else False


class ModuleHelper:
    """
    模块动态加载
    """

    @classmethod
    def load(cls, package_path: str, filter_func: FilterFuncType = _default_filter) -> List[Any]:
        """
        导入模块
        :param package_path: 父包名
        :param filter_func: 子模块过滤函数，入参为模块名和模块对象，返回True则导入，否则不导入
        :return: 导入的模块对象列表
        """

        submodules: list = []
        loaded_modules = set()
        packages = importlib.import_module(package_path)
        for importer, package_name, _ in pkgutil.iter_modules(packages.__path__):
            try:
                if package_name.startswith('_'):
                    continue
                full_package_name = f'{package_path}.{package_name}'
                module = importlib.import_module(full_package_name)
                importlib.reload(module)
                for name, obj in module.__dict__.items():
                    if name.startswith('_'):
                        continue
                    if isinstance(obj, type) and filter_func(name, obj):
                        if name in loaded_modules:
                            continue
                        loaded_modules.add(name)
                        submodules.append(obj)
            except Exception as err:
                logger.debug(f'加载模块 {package_name} 失败：{str(err)} - {traceback.format_exc()}')

        return submodules
