from datetime import timedelta
from typing import Any, Optional

from app import schemas
from app.core import security
from app.core.config import settings
from app.db.models.user import User
from app.db.systemconfig_oper import SystemConfigOper
from app.helper.sites import SitesHelper
from app.schemas.types import SystemConfigKey
from app.utils.singleton import Singleton








def build_token_response(user: User) -> schemas.Token:
    """
    使用系统统一逻辑构造登录 Token 响应。

    :param user: 已认证的本地用户
    :return: 标准 Token 响应
    """
    level = SitesHelper().auth_level
    show_wizard = (
        not SystemConfigOper().get(SystemConfigKey.SetupWizardState)
        and not settings.ADVANCED_MODE
    )
    return schemas.Token(
        access_token=security.create_access_token(
            userid=user.id,
            username=user.name,
            super_user=user.is_superuser,
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
            level=level,
        ),
        token_type="bearer",
        super_user=user.is_superuser,
        user_id=user.id,
        user_name=user.name,
        avatar=user.avatar,
        level=level,
        permissions=user.permissions or {},
        wizard=show_wizard,
    )
