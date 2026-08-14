"""Cambio a euros, solo para el objetivo de la liga.

El resto del proyecto calcula **en la divisa del extracto** y no toca tipos de
cambio a propósito: la clasificación va en porcentaje y ahí la divisa se
cancela, así que convertir no aportaría nada.

El objetivo sí es un importe —14.000 €—, y ahí la divisa manda: una cartera de
5.895 $ no lleva el 42 % de 14.000 €, lleva el 36 %. Por eso el módulo del
objetivo (y solo él) convierte el valor de la cartera a euros con el cambio de
cierre de Yahoo Finance (``EURUSD=X`` y equivalentes), cacheado y versionado
igual que los precios.

Si no hay cambio disponible (sin red y sin caché) se devuelve ``None``: el
módulo prefiere no enseñar el avance a enseñarlo mal.
"""

from __future__ import annotations

from datetime import date, timedelta

from .prices import PriceCache, PriceError

EUR = "EUR"

# Margen que se pide a la caché al comprobar el cambio: con ``--refresh`` (lo
# que hace la Action) se vuelve a descargar igualmente, y sin él evita dar por
# buena una caché de hace semanas.
_WINDOW = timedelta(days=10)


def symbol_for(currency: str) -> str:
    """Símbolo de Yahoo con el cambio ``1 EUR = x <currency>``."""
    return f"EUR{currency.upper()}=X"


def rate_to_eur(prices: PriceCache, currency: str, day: date) -> float | None:
    """Cuántos euros vale una unidad de ``currency`` al cierre de ``day``.

    ``None`` si no se puede saber: ni red ni caché. Nunca se inventa un cambio.
    """
    currency = (currency or EUR).upper()
    if currency == EUR:
        return 1.0
    symbol = symbol_for(currency)
    try:
        prices.ensure_range(symbol, day - _WINDOW, day)
        eur_in_currency = prices.close_on(symbol, day)
    except PriceError:
        return None
    if eur_in_currency <= 0:
        return None
    return 1.0 / eur_in_currency


def rates_to_eur(prices: PriceCache, currencies, day: date) -> dict[str, float]:
    """``{divisa: cambio a euros}`` para las divisas que se puedan resolver."""
    out: dict[str, float] = {}
    for currency in sorted({(c or EUR).upper() for c in currencies}):
        rate = rate_to_eur(prices, currency, day)
        if rate is not None:
            out[currency] = rate
    return out
