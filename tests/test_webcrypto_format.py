"""Blinda el contrato del formato cifrado que reproduce docs/subir.html.

La web cifra el extracto en el navegador con WebCrypto (PBKDF2 -> 32 bytes,
token Fernet construido a mano, envuelto en el formato TRADERENC1). Aquí se
reconstruye ese mismo token con primitivas de bajo nivel (sin usar Fernet) y
se comprueba que ``secretbox.decrypt`` -que sí usa Fernet- lo descifra. Si
alguien cambia el formato, este test se rompe antes que la web.
"""

import base64
import hashlib
import hmac
import os
import struct
import time

import pytest
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.padding import PKCS7

from trader import secretbox


def _encrypt_like_browser(plaintext: bytes, passphrase: str) -> bytes:
    """Réplica en Python de lo que hace encryptTraderEnc() en subir.html."""
    salt = os.urandom(16)
    raw = PBKDF2HMAC(algorithm=SHA256(), length=32, salt=salt,
                     iterations=600_000).derive(passphrase.encode("utf-8"))
    sign_key, enc_key = raw[:16], raw[16:]

    iv = os.urandom(16)
    padder = PKCS7(128).padder()
    padded = padder.update(plaintext) + padder.finalize()
    encryptor = Cipher(algorithms.AES(enc_key), modes.CBC(iv)).encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()

    header = b"\x80" + struct.pack(">Q", int(time.time())) + iv + ciphertext
    mac = hmac.new(sign_key, header, hashlib.sha256).digest()
    token = base64.urlsafe_b64encode(header + mac)
    return secretbox.MAGIC + salt + token


def test_browser_format_decrypts_with_secretbox():
    plaintext = "Date,Ticker,Type\n2026-01-01,AAPL,BUY - MARKET\n".encode("utf-8")
    blob = _encrypt_like_browser(plaintext, "mi-frase-de-paso")
    assert blob.startswith(secretbox.MAGIC)
    assert secretbox.decrypt(blob, "mi-frase-de-paso") == plaintext


def test_browser_format_rejects_wrong_passphrase():
    blob = _encrypt_like_browser(b"datos", "buena")
    with pytest.raises(secretbox.DecryptError):
        secretbox.decrypt(blob, "mala")
