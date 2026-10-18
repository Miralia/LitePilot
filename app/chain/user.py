from dataclasses import dataclass
from typing import Literal, Optional, Tuple, Union

from app.chain import ChainBase
from app.db.models.user import User
from app.db.user_oper import UserOper
from app.helper.swizzin import SwizzinUserSync
from app.core.security import verify_password
from app.log import logger
from app.utils.otp import OtpUtils

PASSWORD_INVALID_CREDENTIALS_MESSAGE = "用户名、密码或验证码错误"


MfaMethod = Literal["otp"]


@dataclass(frozen=True)
class AuthCredentials:
    """登录认证凭据（仅密码认证，用户与口令均以 swizzin 为准）。"""

    username: Optional[str] = None
    password: Optional[str] = None
    mfa_code: Optional[str] = None
    grant_type: str = "password"


@dataclass(frozen=True)
class MfaRequired:
    """密码验证通过后，当前账号仍需完成的二次验证要求。"""

    methods: Tuple[MfaMethod, ...]


class UserChain(ChainBase):
    """
    用户链，处理多种认证协议
    """

    def user_authenticate(
            self,
            username: Optional[str] = None,
            password: Optional[str] = None,
            mfa_code: Optional[str] = None,
            grant_type: Optional[str] = "password"
    ) -> Tuple[bool, Union[str, User, MfaRequired, None]]:
        """
        认证用户，根据不同的 grant_type 处理不同的认证流程

        :param username: 用户名，适用于 "password" grant_type
        :param password: 用户密码，适用于 "password" grant_type
        :param mfa_code: 一次性密码，适用于 "password" grant_type
        :param grant_type: 认证类型，当前只支持 "password"
        :return:
            - 对于成功的认证，返回 (True, User)
            - 对于失败的认证，返回 (False, "错误信息")
        """
        credentials = AuthCredentials(
            username=username,
            password=password,
            mfa_code=mfa_code,
            grant_type=grant_type
        )
        logger.debug(f"认证类型：{grant_type}，开始准备对用户 {username} 进行身份校验")
        if credentials.grant_type != "password":
            logger.debug(f"认证类型 {grant_type} 未实现")
            return False, "不支持的认证类型"

        # Password 认证
        success, user_or_message = self.password_authenticate(credentials=credentials)
        if not success:
            return False, PASSWORD_INVALID_CREDENTIALS_MESSAGE
        # 如果用户启用了二次验证，则进一步验证
        mfa_result = self._verify_mfa(user_or_message, credentials.mfa_code)
        if isinstance(mfa_result, MfaRequired):
            return False, mfa_result
        if not mfa_result:
            return False, PASSWORD_INVALID_CREDENTIALS_MESSAGE
        logger.info(f"用户 {username} 通过密码认证成功")
        return True, user_or_message

    @staticmethod
    def password_authenticate(credentials: AuthCredentials) -> Tuple[bool, Union[User, str]]:
        """
        密码认证

        :param credentials: 认证凭证，包含用户名、密码以及可选的 MFA 认证码
        :return:
            - 成功时返回 (True, User)，其中 User 是认证通过的用户对象
            - 失败时返回 (False, "错误信息")
        """
        if not credentials or credentials.grant_type != "password":
            logger.info("密码认证失败，认证类型不匹配")
            return False, PASSWORD_INVALID_CREDENTIALS_MESSAGE

        sync = SwizzinUserSync()
        if sync.available():
            # swizzin 环境：账号与口令都以宿主机为准
            if not sync.verify_credentials(credentials.username, credentials.password):
                logger.info(f"密码认证失败，swizzin 用户 {credentials.username} 校验不通过")
                return False, PASSWORD_INVALID_CREDENTIALS_MESSAGE
            user = sync.ensure_user(credentials.username)
            if not user or not user.is_active:
                logger.info(f"密码认证失败，用户 {credentials.username} 不可用")
                return False, PASSWORD_INVALID_CREDENTIALS_MESSAGE
            return True, user

        user = UserOper().get_by_name(name=credentials.username)
        if not user:
            logger.info(f"密码认证失败，用户 {credentials.username} 不存在")
            return False, PASSWORD_INVALID_CREDENTIALS_MESSAGE

        if not user.is_active:
            logger.info(f"密码认证失败，用户 {credentials.username} 已被禁用")
            return False, PASSWORD_INVALID_CREDENTIALS_MESSAGE

        if not verify_password(credentials.password, str(user.hashed_password)):
            logger.info(f"密码认证失败，用户 {credentials.username} 的密码验证不通过")
            return False, PASSWORD_INVALID_CREDENTIALS_MESSAGE

        return True, user


    @staticmethod
    def _verify_mfa(user: User, mfa_code: Optional[str]) -> Union[bool, MfaRequired]:
        """
        验证密码登录后的 6 位验证码。

        :param user: 用户对象
        :param mfa_code: 身份验证器生成的 6 位验证码
        :return:
            - 如果验证成功返回 True
            - 如果需要 MFA 但未提供，返回当前账号实际可用的验证方式
            - 如果MFA验证失败，返回 False
        """
        if not user.is_otp:
            return True

        if not mfa_code:
            logger.info(f"用户 {user.name} 已启用二次验证，需要提供验证码")
            return MfaRequired(methods=("otp",))

        if not OtpUtils.check(str(user.otp_secret), mfa_code):
            logger.info(f"用户 {user.name} 的 MFA 认证失败")
            return False
        return True

