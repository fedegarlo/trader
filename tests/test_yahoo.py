"""Sesión anónima de Yahoo compartida por analistas y sesión extendida."""

import pytest

from trader.yahoo import Session, num


def test_num_accepts_raw_wrapper_and_plain_numbers():
    assert num(3.5) == 3.5
    assert num({"raw": 3.5, "fmt": "3.5"}) == 3.5
    assert num(None) is None
    assert num({"fmt": "n/a"}) is None
    assert num("no es un número") is None


def test_handshake_failure_is_not_retried_per_call():
    """Sin salida a Yahoo, el handshake se intenta una vez y no por ticker.

    Reintentarlo por cada valor hacía que un build sin red gastara dos
    peticiones con su timeout por ticker antes de rendirse.
    """
    calls = []

    class Boom(Session):
        def _handshake(self):
            calls.append(1)
            raise OSError("sin red")

    session = Boom()
    for _ in range(5):
        with pytest.raises(OSError):
            session.get_json("v10/finance/quoteSummary/AAPL", {"modules": "price"})
    assert len(calls) == 1
