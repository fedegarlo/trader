"""Cifrado de los extractos para poder subirlos a un repositorio público.

Formato del fichero: cabecera ``TRADERENC1`` + 16 bytes de salt + token
Fernet (AES-128-CBC + HMAC-SHA256). La clave se deriva de la frase de paso
del jugador con PBKDF2-HMAC-SHA256 (600k iteraciones).
"""

from __future__ import annotations

import base64
import os

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

MAGIC = b"TRADERENC1"
SALT_LEN = 16
ITERATIONS = 600_000


class DecryptError(RuntimeError):
    pass


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(algorithm=SHA256(), length=32, salt=salt, iterations=ITERATIONS)
    return base64.urlsafe_b64encode(kdf.derive(passphrase.encode("utf-8")))


def encrypt(plaintext: bytes, passphrase: str) -> bytes:
    salt = os.urandom(SALT_LEN)
    token = Fernet(_derive_key(passphrase, salt)).encrypt(plaintext)
    return MAGIC + salt + token


def decrypt(blob: bytes, passphrase: str) -> bytes:
    if not blob.startswith(MAGIC):
        raise DecryptError("El fichero no tiene el formato TRADERENC1")
    salt = blob[len(MAGIC):len(MAGIC) + SALT_LEN]
    token = blob[len(MAGIC) + SALT_LEN:]
    try:
        return Fernet(_derive_key(passphrase, salt)).decrypt(token)
    except InvalidToken as exc:
        raise DecryptError("Frase de paso incorrecta o fichero corrupto") from exc


def encrypt_file(src: str, dst: str, passphrase: str) -> None:
    with open(src, "rb") as fh:
        blob = encrypt(fh.read(), passphrase)
    with open(dst, "wb") as fh:
        fh.write(blob)


def decrypt_file(src: str, passphrase: str) -> bytes:
    with open(src, "rb") as fh:
        return decrypt(fh.read(), passphrase)
