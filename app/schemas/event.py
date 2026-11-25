from typing import Iterable, Optional, Any

from pydantic import BaseModel, Field, field_validator


class Event(BaseModel):
    """
    事件模型
    """

    event_type: str = Field(..., description="事件类型")
    event_data: Optional[dict] = Field(default={}, description="事件数据")
    priority: Optional[int] = Field(0, description="事件优先级")


class BaseEventData(BaseModel):
    """
    事件数据的基类，所有具体事件数据类应继承自此类
    """

    pass


class ConfigChangeEventData(BaseEventData):
    """
    ConfigChange 事件的数据模型
    """

    key: set[str] = Field(..., description="配置项的键（集合类型）")
    value: Optional[Any] = Field(default=None, description="配置项的新值")
    change_type: str = Field(
        default="update", description="配置项的变更类型，如 'add', 'update', 'delete'"
    )

    @field_validator("key", mode="before")
    @classmethod
    def convert_to_set(cls, v):
        """将输入的 str、list、dict.keys() 等转为 set"""
        if v is None:
            return set()
        elif isinstance(v, str):
            return {v}
        elif isinstance(v, dict):
            return set(str(k) for k in v.keys())
        elif isinstance(v, (list, tuple)):
            return set(str(item) for item in v)
        elif isinstance(v, set):
            return set(str(item) for item in v)
        elif isinstance(v, Iterable):
            return set(str(item) for item in v)
        else:
            return {str(v)}
