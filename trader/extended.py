"""Cotización fuera de horario: pre-market y after-hours por ticker.

La web es estática y no llama a ninguna API al abrirse, así que —igual que con
los precios y el consenso de analistas— la foto de la sesión extendida se toma
**en tiempo de build** (el comando ``ranking``, que corre en GitHub Actions) del
endpoint ``quoteSummary`` de Yahoo Finance, módulo ``price``, y se embebe en la
página con la hora a la que se tomó.

Qué se publica y qué no:

* Solo hay dato cuando el mercado está en pre-market o en after-hours. Durante
  la sesión regular el precio ya se refleja en la jornada, y con el mercado
  cerrado del todo (noche, fin de semana) no hay nada «fuera de horario» que
  contar: la tarjeta simplemente no aparece.
* El porcentaje se calcula aquí (precio extendido frente al último precio
  regular), no se copia el de Yahoo: así no dependemos de si el campo viene en
  tanto por uno o en tanto por ciento.
* Una cotización más vieja que :data:`STALE_SECONDS` se descarta: mejor no
  enseñar nada que enseñar el after-hours de anteayer como si fuera de ahora.

Nada de esto se cachea en disco: son valores que caducan en minutos, y una
caché versionada solo serviría para publicar datos viejos. Todo es
*best-effort*: si Yahoo no responde, la sección no aparece y el build sigue.

Los precios son de mercado público (no revelan nada de ningún jugador) y se
muestran a título informativo, con atribución a Yahoo Finance.
"""

from __future__ import annotations

import sys
import time as time_mod
import urllib.parse

from .yahoo import Session, num

# Más allá de esto la cotización extendida se considera vieja y se descarta.
# Cubre de sobra el hueco entre dos builds dentro de la misma franja (pre-market
# empieza 5 h 30 min antes de la apertura; after-hours dura 4 h tras el cierre).
STALE_SECONDS = 6 * 3600

# ``marketState`` de Yahoo → sesión extendida que toca enseñar. REGULAR (el
# mercado está abierto) y CLOSED (noche cerrada, fin de semana, festivo) no
# tienen sesión extendida en curso.
_SESSION_BY_STATE = {
    "PRE": "pre",
    "PREPRE": "pre",
    "POST": "post",
    "POSTPOST": "post",
}


def parse_quote(payload: dict, now: float | None = None) -> dict | None:
    """Normaliza la respuesta de ``quoteSummary?modules=price``.

    Devuelve un dict compacto con el último precio regular y, si hay sesión
    extendida en curso con datos frescos, el precio y la variación de esa
    sesión. ``None`` si no hay ni siquiera precio regular (nada que enseñar).
    """
    try:
        price = payload["quoteSummary"]["result"][0]["price"]
    except (KeyError, IndexError, TypeError):
        return None
    if not isinstance(price, dict):
        return None

    state = str(price.get("marketState") or "").upper()
    regular = num(price.get("regularMarketPrice"))
    prev_close = num(price.get("regularMarketPreviousClose"))

    out = {
        "state": state or None,
        "session": None,
        "regular": round(regular, 4) if regular is not None else None,
        "currency": price.get("currency") or None,
    }
    if regular and prev_close:
        out["regularPct"] = round((regular / prev_close - 1.0) * 100, 2)

    session = _SESSION_BY_STATE.get(state)
    if session:
        prefix = "preMarket" if session == "pre" else "postMarket"
        ext = num(price.get(prefix + "Price"))
        at = num(price.get(prefix + "Time"))
        fresh = at is None or (now or time_mod.time()) - at <= STALE_SECONDS
        if ext and fresh:
            # El % se calcula contra el último precio regular: en pre-market ese
            # precio es el cierre de ayer y en after-hours el de hoy, que es
            # justo la referencia que espera quien lo lee. Si por lo que sea no
            # viene el precio regular, se cae al porcentaje de Yahoo (que llega
            # en tanto por uno).
            if regular:
                pct = (ext / regular - 1.0) * 100
            else:
                raw = num(price.get(prefix + "ChangePercent"))
                if raw is None:
                    return out if out["regular"] is not None else None
                pct = raw * 100
            out.update({
                "session": session,
                "price": round(ext, 4),
                "pct": round(pct, 2),
                "at": int(at) if at is not None else None,
            })

    if out["regular"] is None and out["session"] is None:
        return None
    return out


class ExtendedQuotes:
    """Cotización extendida por ticker (sin caché en disco: caduca en minutos)."""

    def __init__(self, offline: bool = False, session: Session | None = None):
        self.offline = offline
        self._session = session
        self._mem: dict[str, dict | None] = {}

    def get(self, ticker: str) -> dict | None:
        """Sesión extendida de un ticker, o ``None`` si no hay dato.

        Cualquier fallo de red se traga con un aviso: la página se publica igual,
        solo que sin la tarjeta de pre-market/after-hours.
        """
        if self.offline:
            return None
        if ticker in self._mem:
            return self._mem[ticker]
        data: dict | None = None
        try:
            if self._session is None:
                self._session = Session()
            payload = self._session.get_json(
                f"v10/finance/quoteSummary/{urllib.parse.quote(ticker)}",
                {"modules": "price"})
            data = parse_quote(payload)
        except Exception as exc:  # best-effort: nunca rompe el build
            print(f"AVISO: sin cotización fuera de horario para {ticker} ({exc})",
                  file=sys.stderr)
        self._mem[ticker] = data
        return data

    def fetch_all(self, tickers) -> dict[str, dict]:
        """``{ticker: cotización}`` para los tickers con dato (los demás se caen)."""
        out: dict[str, dict] = {}
        for ticker in tickers:
            data = self.get(ticker)
            if data:
                out[ticker] = data
        return out
