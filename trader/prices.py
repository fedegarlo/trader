"""Precios de cierre diarios, con caché local en CSV.

La caché vive en ``data/prices/<TICKER>.csv`` (columnas: date,close) y se
versiona en git, de modo que los cálculos son reproducibles y la GitHub
Action no depende de que Yahoo Finance responda para fechas pasadas.
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

# Hosts equivalentes del endpoint chart de Yahoo: si uno responde con un error
# transitorio (400/429/5xx, habituales cuando limita peticiones anónimas), se
# reintenta en el otro.
_YAHOO_HOSTS = ("query1.finance.yahoo.com", "query2.finance.yahoo.com")
_FETCH_ATTEMPTS = 4


class PriceError(RuntimeError):
    pass


class PriceCache:
    """Precios de cierre por ticker con caché en disco y descarga de Yahoo."""

    def __init__(self, cache_dir: str = "data/prices", offline: bool = False,
                 refresh: bool = False):
        self.cache_dir = cache_dir
        self.offline = offline
        self.refresh = refresh  # fuerza la descarga aunque la caché cubra el rango
        self._series: dict[str, dict[date, float]] = {}

    # ------------------------------------------------------------- caché
    def _cache_path(self, ticker: str) -> str:
        safe = ticker.replace("/", "_")
        return os.path.join(self.cache_dir, f"{safe}.csv")

    def _load(self, ticker: str) -> dict[date, float]:
        if ticker in self._series:
            return self._series[ticker]
        series: dict[date, float] = {}
        path = self._cache_path(ticker)
        if os.path.exists(path):
            with open(path, newline="") as fh:
                for row in csv.DictReader(fh):
                    series[date.fromisoformat(row["date"])] = float(row["close"])
        self._series[ticker] = series
        return series

    def _save(self, ticker: str) -> None:
        series = self._series.get(ticker, {})
        if not series:
            return
        os.makedirs(self.cache_dir, exist_ok=True)
        with open(self._cache_path(ticker), "w", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["date", "close"])
            for day in sorted(series):
                writer.writerow([day.isoformat(), f"{series[day]:.6f}"])

    # ---------------------------------------------------------- descarga
    def _fetch(self, ticker: str, start: date, end: date) -> None:
        """Descarga cierres diarios del endpoint chart de Yahoo Finance.

        Yahoo limita las peticiones anónimas de forma intermitente (400/429),
        así que se reintenta con espera exponencial y alternando de host antes
        de rendirse. Un fallo persistente se eleva como ``PriceError``.
        """
        period1 = int(datetime(start.year, start.month, start.day).timestamp())
        period2 = int(datetime(end.year, end.month, end.day).timestamp()) + 86400
        query = (
            f"{urllib.parse.quote(ticker)}?period1={period1}&period2={period2}"
            "&interval=1d&events=div%2Csplit"
        )
        payload = None
        last_err: Exception | None = None
        for attempt in range(_FETCH_ATTEMPTS):
            host = _YAHOO_HOSTS[attempt % len(_YAHOO_HOSTS)]
            url = f"https://{host}/v8/finance/chart/{query}"
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Accept": "application/json",
            })
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    payload = json.load(resp)
                break
            except (urllib.error.URLError, TimeoutError) as exc:
                last_err = exc
                if attempt < _FETCH_ATTEMPTS - 1:
                    time.sleep(2 ** attempt)  # 1 s, 2 s, 4 s
        if payload is None:
            raise PriceError(f"Yahoo Finance no respondió para {ticker}: {last_err}")
        result = (payload.get("chart") or {}).get("result") or []
        if not result:
            raise PriceError(f"Yahoo Finance no devolvió datos para {ticker}")
        timestamps = result[0].get("timestamp") or []
        closes = ((result[0].get("indicators") or {}).get("quote") or [{}])[0].get("close") or []
        series = self._load(ticker)
        for ts, close in zip(timestamps, closes):
            if close is not None:
                series[datetime.utcfromtimestamp(ts).date()] = float(close)
        self._save(ticker)

    def ensure_range(self, ticker: str, start: date, end: date) -> None:
        """Garantiza que la caché cubre [start, end] (días de mercado)."""
        series = self._load(ticker)
        covered = (bool(series) and min(series) <= start
                   and max(series) >= end - timedelta(days=4))
        if self.offline or (covered and not self.refresh):
            return
        try:
            self._fetch(ticker, start - timedelta(days=7), end)
        except PriceError as exc:
            # Si solo era un refresco y la caché ya cubre el rango, seguimos con
            # ella; solo es fatal si no teníamos datos para valorar el ticker.
            if not covered:
                raise
            print(f"AVISO: no se pudo actualizar {ticker}, se usa la caché "
                  f"({exc})", file=sys.stderr)

    # -------------------------------------------------------- precio en vivo
    def live_price(self, ticker: str) -> float | None:
        """Cotización actual (regularMarketPrice) de Yahoo, sin cachear.

        Best-effort: devuelve ``None`` en modo offline o ante cualquier fallo
        de red/formato. Es un dato provisional, así que nunca se persiste en la
        caché de cierres (que debe contener solo cierres finales).
        """
        if self.offline:
            return None
        url = (
            "https://query1.finance.yahoo.com/v8/finance/chart/"
            f"{urllib.parse.quote(ticker)}?range=1d&interval=1d"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                payload = json.load(resp)
            result = (payload.get("chart") or {}).get("result") or []
            meta = (result[0].get("meta") or {}) if result else {}
            price = meta.get("regularMarketPrice")
            return float(price) if price is not None else None
        except Exception:
            return None

    def history(self, ticker: str, start: date, end: date) -> list[tuple[date, float]]:
        """Cierres cacheados de ``[start, end]`` como ``[(date, close)]`` ordenado.

        Solo lee de la caché (no descarga): alimenta la mini-gráfica de precio
        del detalle del ticker en la web. Son precios de mercado públicos, así
        que no revelan nada del jugador.
        """
        series = self._load(ticker)
        return [(day, series[day]) for day in sorted(series) if start <= day <= end]

    # ------------------------------------------------------------ lookup
    def close_on(self, ticker: str, day: date) -> float:
        """Cierre del día, o el último cierre anterior (fines de semana, festivos)."""
        series = self._load(ticker)
        for back in range(0, 8):
            candidate = day - timedelta(days=back)
            if candidate in series:
                return series[candidate]
        raise PriceError(
            f"Sin precio para {ticker} en torno a {day}. "
            f"Ejecuta sin --offline o añade data/prices/{ticker}.csv"
        )
