"""Precios de cierre diarios, con caché local en CSV.

La caché vive en ``data/prices/<TICKER>.csv`` (columnas: date,close) y se
versiona en git, de modo que los cálculos son reproducibles y la GitHub
Action no depende de que Yahoo Finance responda para fechas pasadas.
"""

from __future__ import annotations

import csv
import json
import os
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta


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
        """Descarga cierres diarios del endpoint chart de Yahoo Finance."""
        period1 = int(datetime(start.year, start.month, start.day).timestamp())
        period2 = int(datetime(end.year, end.month, end.day).timestamp()) + 86400
        url = (
            "https://query1.finance.yahoo.com/v8/finance/chart/"
            f"{urllib.parse.quote(ticker)}?period1={period1}&period2={period2}"
            "&interval=1d&events=div%2Csplit"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.load(resp)
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
        need = (self.refresh or not series or min(series) > start
                or max(series) < end - timedelta(days=4))
        if need and not self.offline:
            self._fetch(ticker, start - timedelta(days=7), end)

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
