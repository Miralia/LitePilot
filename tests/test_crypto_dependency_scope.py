"""加密工具依赖边界测试。"""

from pathlib import Path

import app.core.security as core_security
import app.utils.crypto as crypto_utils


def test_crypto_utils_keeps_only_active_hash_helpers():
    """内部加密工具只保留仍有消费者的哈希能力，不保留上游 CryptoJS 兼容层。"""
    assert hasattr(crypto_utils, "HashUtils")
    assert hasattr(crypto_utils.HashUtils, "md5")
    assert not hasattr(crypto_utils, "CryptoJsUtils")
    assert not hasattr(crypto_utils.HashUtils, "sha1")
    assert not hasattr(crypto_utils.HashUtils, "md5_bytes")


def test_application_does_not_depend_on_pycryptodome():
    """AES 死引用移除后，应用不再依赖重复的 pycryptodome 加密栈。"""
    app_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in Path("app").rglob("*.py")
    )
    requirements_source = Path("requirements.in").read_text(encoding="utf-8")

    assert "from Crypto" not in app_sources
    assert "import Crypto" not in app_sources
    assert not any(
        line.startswith("pycryptodome")
        for line in requirements_source.splitlines()
    )


def test_core_security_drops_dead_fernet_decrypt_dependency():
    """核心认证模块不保留无消费者的 Fernet 解密兼容入口及重复加密依赖。"""
    security_source = Path("app/core/security.py").read_text(encoding="utf-8")
    requirements_source = Path("requirements.in").read_text(encoding="utf-8")

    assert not hasattr(core_security, "decrypt")
    assert "cryptography.fernet" not in security_source
    assert not any(
        line.startswith("cryptography")
        for line in requirements_source.splitlines()
    )
