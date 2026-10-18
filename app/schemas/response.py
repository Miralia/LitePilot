from typing import Any, Optional

from pydantic import BaseModel, Field


class Response(BaseModel):
    """通用接口响应结构"""

    # 状态
    success: bool
    # 消息文本
    message: Optional[str] = None
    # 数据
    data: Optional[Any] = Field(default_factory=dict)
