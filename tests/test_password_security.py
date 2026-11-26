"""密码哈希实现边界测试。"""

from pathlib import Path

from app.core.security import get_password_hash, verify_password


def test_password_hash_round_trip_uses_standard_bcrypt():
    """新密码哈希保持标准 bcrypt 格式并能完成正确与错误密码校验。"""
    password_hash = get_password_hash("correct horse battery staple")

    assert password_hash.startswith("$2b$12$")
    assert verify_password("correct horse battery staple", password_hash)
    assert not verify_password("wrong password", password_hash)


def test_password_verify_accepts_existing_passlib_bcrypt_hash():
    """已有 passlib bcrypt 哈希迁移后仍可验证，用户无需重置密码。"""
    passlib_hash = "$2b$12$lfa8drf0E3.9vtGwx6bL.ODR/TQcpYNF5FVFUClR6tygc4ZkZbm8."

    assert verify_password("correct horse battery staple", passlib_hash)
    assert not verify_password("wrong password", passlib_hash)


def test_password_preserves_bcrypt_72_byte_truncation_contract():
    """超过 72 字节的密码后缀继续按 bcrypt 协议忽略，不改变既有认证语义。"""
    prefix = "a" * 72
    password_hash = get_password_hash(prefix + "first")

    assert verify_password(prefix + "second", password_hash)


def test_unicode_password_matches_passlib_byte_truncation_contract():
    """多字节 UTF-8 密码仍按字节截断，兼容迁移前生成的长中文密码哈希。"""
    passlib_hash = "$2b$12$UQS2U06blEUnZ1qqUFjKDuYfh7P9BmRFIhHk9Tpx9F9XVbXa8WH8i"

    assert verify_password("密" * 24 + "first", passlib_hash)
    assert verify_password("密" * 24 + "second", passlib_hash)
    assert not verify_password("密" * 23 + "first", passlib_hash)


def test_malformed_password_hash_is_not_valid():
    """损坏的哈希值只代表认证失败，不能把数据异常扩散成登录接口错误。"""
    assert not verify_password("password", "invalid")


def test_password_hash_does_not_use_unmaintained_passlib():
    """项目只使用 bcrypt 原语，不再保留 passlib 兼容层。"""
    security_source = Path("app/core/security.py").read_text(encoding="utf-8")
    requirements_source = Path("requirements.in").read_text(encoding="utf-8")

    assert "from passlib" not in security_source
    assert "import passlib" not in security_source
    assert not any(
        line.startswith("passlib")
        for line in requirements_source.splitlines()
    )
