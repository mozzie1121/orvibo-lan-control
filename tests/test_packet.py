"""
测试：AES 加密单例缓存。
验证 _get_cipher() 返回同一个 Cipher 对象对相同的 key，且加解密功能正常。
"""
import pytest
from cryptography.hazmat.primitives.ciphers import Cipher, modes

from custom_components.orvibo_lan.lib.packet import (
    _AES_CIPHER_CACHE, _get_cipher,
    _encrypt_aes_ecb, _decrypt_aes_ecb,
    DEFAULT_KEY,
)


class TestAesCipherSingleton:
    def test_encrypt_decrypt_roundtrip(self):
        """加解密往返正确。"""
        key = DEFAULT_KEY.encode()
        plaintext = '{"cmd":42,"deviceId":"test123"}'
        encrypted = _encrypt_aes_ecb(key, plaintext)
        decrypted = _decrypt_aes_ecb(key, encrypted)
        assert decrypted == plaintext

    def test_two_different_keys(self):
        """不同 key 创建不同的 cipher 对象。"""
        _AES_CIPHER_CACHE.clear()
        key1 = DEFAULT_KEY.encode()
        key2 = b"anotherKey1234567"[:16]  # 确保 16 字节
        c1 = _get_cipher(key1, modes.ECB())
        c2 = _get_cipher(key2, modes.ECB())
        assert c1 is not c2
        assert len(_AES_CIPHER_CACHE) == 2

    def test_cache_does_not_grow_indefinitely(self):
        """缓存不会无限增长。"""
        _AES_CIPHER_CACHE.clear()
        keys = [str(i).zfill(16).encode()[:16] for i in range(10)]
        for k in keys:
            _get_cipher(k, modes.ECB())
        assert len(_AES_CIPHER_CACHE) <= 10

    def test_same_key_returns_same_cipher(self):
        """相同的 key 返回同一个 Cipher 对象（单例）。"""
        _AES_CIPHER_CACHE.clear()
        key = DEFAULT_KEY.encode()
        c1 = _get_cipher(key, modes.ECB())
        c2 = _get_cipher(key, modes.ECB())
        assert c1 is c2

    def test_encrypt_with_cached_cipher(self):
        """复用缓存后的加密仍能正确解密。"""
        _AES_CIPHER_CACHE.clear()
        key = DEFAULT_KEY.encode()
        _get_cipher(key, modes.ECB())
        plain = '{"cmd":15,"order":"on"}'
        encrypted = _encrypt_aes_ecb(key, plain)
        decrypted = _decrypt_aes_ecb(key, encrypted)
        assert decrypted == plain
