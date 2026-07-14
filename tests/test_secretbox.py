import pytest

from trader import secretbox


def test_roundtrip():
    blob = secretbox.encrypt(b"hola,mundo\n", "clave-secreta")
    assert blob.startswith(secretbox.MAGIC)
    assert secretbox.decrypt(blob, "clave-secreta") == b"hola,mundo\n"


def test_wrong_passphrase():
    blob = secretbox.encrypt(b"datos", "buena")
    with pytest.raises(secretbox.DecryptError):
        secretbox.decrypt(blob, "mala")


def test_bad_format():
    with pytest.raises(secretbox.DecryptError):
        secretbox.decrypt(b"no es un fichero cifrado", "x")


def test_file_roundtrip(tmp_path):
    src = tmp_path / "trades.csv"
    src.write_bytes(b"Date,Ticker\n2026-01-01,AAPL\n")
    enc = tmp_path / "trades.csv.enc"
    secretbox.encrypt_file(str(src), str(enc), "pw")
    assert secretbox.decrypt_file(str(enc), "pw") == src.read_bytes()
