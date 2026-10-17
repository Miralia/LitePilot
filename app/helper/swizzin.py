import hmac
import re
import secrets
from pathlib import Path
from typing import List, Optional

from app.core.config import settings
from app.core.security import get_password_hash
from app.db.models.user import User
from app.db.user_oper import UserOper
from app.log import logger
from app.utils.singleton import Singleton

# swizzin 用户清单文件所在目录（root 家目录下的 <user>.info 与 .master.info）
_SWIZZIN_ROOT = Path("/root")
# swizzin 保存的用户名合法字符，避免把脏数据写进用户表
_USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_.-]{1,32}$")


class SwizzinUserSync(metaclass=Singleton):
    """
    swizzin 用户同步

    本分支不再维护多用户与权限体系：用户身份以宿主机 swizzin 为唯一来源，
    MoviePilot 只保留与 swizzin 同名的账号，并在启动与登录时按需补齐。
    """

    @staticmethod
    def available() -> bool:
        """
        判断当前宿主机是否可读取 swizzin 用户清单。
        """
        return (_SWIZZIN_ROOT / ".master.info").is_file()

    @staticmethod
    def _read_username(info_file: Path) -> Optional[str]:
        """
        从 swizzin 的 info 文件读取用户名。

        :param info_file: swizzin 用户信息文件
        :return: 合法用户名，读取失败或格式非法时返回 None
        """
        try:
            content = info_file.read_text(encoding="utf-8", errors="ignore")
        except OSError as err:
            logger.debug(f"读取 swizzin 用户文件失败：{info_file} - {err}")
            return None
        username = (content.split(":", 1)[0] if content else "").strip()
        if not username or not _USERNAME_PATTERN.fullmatch(username):
            return None
        return username

    def list_users(self) -> List[str]:
        """
        列出 swizzin 管理的用户，主用户（master）始终位于首位。

        :return: 用户名单
        """
        if not self.available():
            return []

        master_file = _SWIZZIN_ROOT / ".master.info"
        master = self._read_username(master_file)
        users: List[str] = [master] if master else []
        for info_file in sorted(_SWIZZIN_ROOT.glob("*.info")):
            if info_file.name == ".master.info":
                continue
            username = self._read_username(info_file)
            if username and username not in users:
                users.append(username)
        return users

    @property
    def master_user(self) -> Optional[str]:
        """
        主用户（swizzin 中的 master 账号）。
        """
        return self._read_username(_SWIZZIN_ROOT / ".master.info")

    def _password_of(self, username: str) -> Optional[str]:
        """
        读取 swizzin 为用户保存的登录口令。

        swizzin 的 `<user>.info` 与 `.master.info` 以 `用户名:口令` 行保存账号信息，
        因此本分支的登录口令以 swizzin 侧为准，本地不再单独维护密码。

        :param username: swizzin 用户名
        :return: 口令字符串，文件缺失或格式异常时返回 None
        """
        if not self.available() or not username:
            return None
        for info_file in (_SWIZZIN_ROOT / f"{username}.info", _SWIZZIN_ROOT / ".master.info"):
            if not info_file.is_file():
                continue
            try:
                content = info_file.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            parts = content.strip().split(":", 1)
            if len(parts) != 2 or parts[0].strip() != username:
                continue
            return parts[1].strip() or None
        return None

    def verify_credentials(self, username: str, password: Optional[str]) -> bool:
        """
        校验用户口令是否与 swizzin 侧一致。

        :param username: swizzin 用户名
        :param password: 待校验口令
        :return: 校验是否通过
        """
        if not password:
            return False
        stored = self._password_of(username)
        if not stored:
            return False
        return hmac.compare_digest(stored, password)

    def ensure_user(self, username: str) -> Optional[User]:
        """
        确保用户表中存在与 swizzin 同名的账号。

        首次出现时按 swizzin 的约定初始化：主用户为超级管理员，其余为普通用户；
        密码不在本地维护（登录由 swizzin 侧鉴权），写入随机占位值以满足非空约束。

        :param username: swizzin 用户名
        :return: 用户对象，用户名非法时返回 None
        """
        if not username or not _USERNAME_PATTERN.fullmatch(username):
            return None

        user_oper = UserOper()
        user = user_oper.get_by_name(username)
        is_superuser = username == self.master_user
        if user:
            # 仅纠正主用户的超管标记，避免覆盖用户自定义的头像与设置
            if is_superuser and not user.is_superuser:
                user.update(user_oper._db, {"is_superuser": True})
                logger.info(f"已将 swizzin 主用户 {username} 提升为超级管理员")
            return user

        user_oper.add(
            name=username,
            email=None,
            hashed_password=get_password_hash(secrets.token_urlsafe(16)),
            is_active=True,
            is_superuser=is_superuser,
            avatar="",
        )
        logger.info(f"已按 swizzin 用户清单创建账号：{username}")
        return user_oper.get_by_name(username)

    def sync(self) -> List[str]:
        """
        按 swizzin 用户清单补齐本地账号，并调整超管标记。

        :return: 已同步的用户名单（swizzin 不可用时为空列表）
        """
        users = self.list_users()
        if not users:
            # 非 swizzin 环境退化为单管理员模式，保证至少存在一个可用账号
            fallback = str(settings.SUPERUSER or "").strip()
            if fallback:
                self.ensure_user(fallback)
            return []

        for username in users:
            self.ensure_user(username)
        return users