import base64
import hashlib
from hashlib import md5
from typing import Union, Optional, Tuple

from Crypto import Random
from Crypto.Cipher import AES
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding, rsa




class HashUtils:
    @staticmethod
    def md5(data: Union[str, bytes], encoding: str = "utf-8") -> str:
        """
        生成数据的MD5哈希值，并以字符串形式返回

        :param data: 输入的数据，类型为字符串
        :param encoding: 字符串编码类型，默认使用UTF-8
        :return: 生成的MD5哈希字符串
        """
        if isinstance(data, str):
            data = data.encode(encoding)
        return hashlib.md5(data).hexdigest()

    @staticmethod
    def sha1(data: Union[str, bytes], encoding: str = "utf-8") -> str:
        """
        生成数据的SHA-1哈希值，并以字符串形式返回

        :param data: 输入的数据，类型为字符串或字节
        :param encoding: 字符串编码类型，默认使用UTF-8
        :return: 生成的SHA-1哈希字符串
        """
        if isinstance(data, str):
            data = data.encode(encoding)
        return hashlib.sha1(data).hexdigest()

    @staticmethod
    def md5_bytes(data: Union[str, bytes], encoding: str = "utf-8") -> bytes:
        """
        生成数据的MD5哈希值，并以字节形式返回

        :param data: 输入的数据，类型为字符串
        :param encoding: 字符串编码类型，默认使用UTF-8
        :return: 生成的MD5哈希二进制数据
        """
        if isinstance(data, str):
            data = data.encode(encoding)
        return hashlib.md5(data).digest()


class CryptoJsUtils:

    @staticmethod
    def bytes_to_key(data: bytes, salt: bytes, output=48) -> bytes:
        """
        生成加密/解密所需的密钥和初始化向量 (IV)
        """
        # extended from https://gist.github.com/gsakkis/4546068
        assert len(salt) == 8, len(salt)
        data += salt
        key = md5(data).digest()
        final_key = key
        while len(final_key) < output:
            key = md5(key + data).digest()
            final_key += key
        return final_key[:output]

    @staticmethod
    def encrypt(message: bytes, passphrase: bytes) -> bytes:
        """
        使用 CryptoJS 兼容的加密策略对消息进行加密
        """
        # This is a modified copy of https://stackoverflow.com/questions/36762098/how-to-decrypt-password-from-javascript-cryptojs-aes-encryptpassword-passphras
        # 生成8字节的随机盐值
        salt = Random.new().read(8)
        # 通过密码短语和盐值生成密钥和IV
        key_iv = CryptoJsUtils.bytes_to_key(passphrase, salt, 32 + 16)
        key = key_iv[:32]
        iv = key_iv[32:]
        # 创建AES加密器（CBC模式）
        aes = AES.new(key, AES.MODE_CBC, iv)
        # 应用PKCS#7填充
        padding_length = 16 - (len(message) % 16)
        padding = bytes([padding_length] * padding_length)
        padded_message = message + padding
        # 加密消息
        encrypted = aes.encrypt(padded_message)
        # 构建加密数据格式：b"Salted__" + salt + encrypted_message
        salted_encrypted = b"Salted__" + salt + encrypted
        # 返回Base64编码的加密数据
        return base64.b64encode(salted_encrypted)

    @staticmethod
    def decrypt(encrypted: Union[str, bytes], passphrase: bytes) -> bytes:
        """
        使用 CryptoJS 兼容的解密策略对加密消息进行解密
        """
        # 确保输入是字节类型
        if isinstance(encrypted, str):
            encrypted = encrypted.encode("utf-8")
        # Base64 解码
        encrypted = base64.b64decode(encrypted)
        # 检查前8字节是否为 "Salted__"
        assert encrypted.startswith(b"Salted__"), "Invalid encrypted data format"
        # 提取盐值
        salt = encrypted[8:16]
        # 通过密码短语和盐值生成密钥和IV
        key_iv = CryptoJsUtils.bytes_to_key(passphrase, salt, 32 + 16)
        key = key_iv[:32]
        iv = key_iv[32:]
        # 创建AES解密器（CBC模式）
        aes = AES.new(key, AES.MODE_CBC, iv)
        # 解密加密部分
        decrypted_padded = aes.decrypt(encrypted[16:])
        # 移除PKCS#7填充
        padding_length = decrypted_padded[-1]
        if isinstance(padding_length, str):
            padding_length = ord(padding_length)
        decrypted = decrypted_padded[:-padding_length]
        return decrypted
