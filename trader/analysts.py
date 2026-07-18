"""Consenso de analistas por ticker, con caché local en JSON.

La web del ranking es estática: no llama a ninguna API al abrirse. Igual que
con los precios, el consenso de analistas se descarga **en tiempo de build**
(el comando ``ranking``, que en GitHub Actions corre con internet abierto) del
endpoint ``quoteSummary`` de Yahoo Finance, se normaliza y se cachea en
``data/analysts/<TICKER>.json`` (versionado), y luego se embebe en la página.

Todo es *best-effort*: si Yahoo no responde (o el entorno bloquea el host), no
se escribe nada y la sección de analistas simplemente no aparece. Nunca se
inventan cifras: solo se muestra lo que se ha podido descargar de verdad.

Los datos son de terceros (Yahoo agrega estimaciones de analistas) y se enseñan
a título informativo, con atribución; no son una recomendación de inversión.
"""

from __future__ import annotations

import http.cookiejar
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
_HOSTS = ("query1.finance.yahoo.com", "query2.finance.yahoo.com")


def _num(value):
    """Acepta un número crudo o el ``{"raw":..}`` de Yahoo y devuelve float."""
    if isinstance(value, dict):
        value = value.get("raw")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value):
    n = _num(value)
    return int(round(n)) if n is not None else None


def _label(mean: float | None) -> tuple[str | None, str]:
    """Etiqueta y tono a partir de la media de recomendación (1=compra fuerte)."""
    if mean is None:
        return None, "neutral"
    if mean <= 1.5:
        return "Compra fuerte", "pos"
    if mean <= 2.5:
        return "Comprar", "pos"
    if mean <= 3.5:
        return "Mantener", "neutral"
    if mean <= 4.5:
        return "Vender", "neg"
    return "Venta fuerte", "neg"


def parse_summary(payload: dict) -> dict | None:
    """Normaliza la respuesta de ``quoteSummary`` a un dict compacto.

    Devuelve ``None`` si no hay ni media de recomendación ni precio objetivo ni
    reparto de opiniones (nada que enseñar). El ``upside`` es la revalorización
    implícita hasta el precio objetivo medio frente al precio actual.
    """
    try:
        result = payload["quoteSummary"]["result"][0]
    except (KeyError, IndexError, TypeError):
        return None
    fin = result.get("financialData") or {}
    trend = (result.get("recommendationTrend") or {}).get("trend") or []

    mean = _num(fin.get("recommendationMean"))
    count = _int(fin.get("numberOfAnalystOpinions"))
    target = _num(fin.get("targetMeanPrice"))
    high = _num(fin.get("targetHighPrice"))
    low = _num(fin.get("targetLowPrice"))
    current = _num(fin.get("currentPrice"))

    dist = None
    if trend:
        t = trend[0]
        dist = {k: (_int(t.get(k)) or 0)
                for k in ("strongBuy", "buy", "hold", "sell", "strongSell")}
        if not any(dist.values()):
            dist = None

    if mean is None and target is None and dist is None:
        return None

    label, tone = _label(mean)
    upside = None
    if target and current:
        upside = round((target / current - 1.0) * 100, 1)

    out = {
        "label": label,
        "tone": tone,
        "mean": round(mean, 2) if mean is not None else None,
        "count": count,
        "target": round(target, 2) if target is not None else None,
        "targetHigh": round(high, 2) if high is not None else None,
        "targetLow": round(low, 2) if low is not None else None,
        "current": round(current, 2) if current is not None else None,
        "upside": upside,
        "dist": dist,
    }
    return out


class AnalystCache:
    """Consenso de analistas por ticker con caché en disco y descarga de Yahoo."""

    def __init__(self, cache_dir: str = "data/analysts", offline: bool = False,
                 refresh: bool = False):
        self.cache_dir = cache_dir
        self.offline = offline
        self.refresh = refresh
        self._mem: dict[str, dict | None] = {}
        self._crumb: str | None = None
        self._opener: urllib.request.OpenerDirector | None = None

    def _path(self, ticker: str) -> str:
        return os.path.join(self.cache_dir, f"{ticker.replace('/', '_')}.json")

    def _load(self, ticker: str) -> dict | None:
        path = self._path(ticker)
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as fh:
                    return json.load(fh)
            except (OSError, json.JSONDecodeError):
                return None
        return None

    def _save(self, ticker: str, data: dict) -> None:
        os.makedirs(self.cache_dir, exist_ok=True)
        with open(self._path(ticker), "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1, sort_keys=True)

    # ------------------------------------------------------------- red
    def _ensure_session(self) -> None:
        """Cookie + crumb de Yahoo (necesarios para ``quoteSummary`` anónimo)."""
        if self._crumb is not None:
            return
        jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(jar))
        # una visita a finance.yahoo.com siembra la cookie de sesión
        req = urllib.request.Request("https://finance.yahoo.com/quote/AAPL",
                                     headers={"User-Agent": _UA})
        with self._opener.open(req, timeout=20):
            pass
        req = urllib.request.Request(
            "https://query1.finance.yahoo.com/v1/test/getcrumb",
            headers={"User-Agent": _UA, "Accept": "text/plain"})
        with self._opener.open(req, timeout=20) as resp:
            self._crumb = resp.read().decode("utf-8").strip()

    def _fetch(self, ticker: str) -> dict | None:
        self._ensure_session()
        params = urllib.parse.urlencode({
            "modules": "financialData,recommendationTrend",
            "crumb": self._crumb or "",
        })
        last_err: Exception | None = None
        for host in _HOSTS:
            url = (f"https://{host}/v10/finance/quoteSummary/"
                   f"{urllib.parse.quote(ticker)}?{params}")
            req = urllib.request.Request(url, headers={
                "User-Agent": _UA, "Accept": "application/json"})
            try:
                with self._opener.open(req, timeout=25) as resp:  # type: ignore[union-attr]
                    return parse_summary(json.load(resp))
            except (urllib.error.URLError, TimeoutError, ValueError) as exc:
                last_err = exc
        if last_err is not None:
            raise last_err
        return None

    # ------------------------------------------------------------ lookup
    def get(self, ticker: str) -> dict | None:
        """Consenso normalizado de un ticker (o ``None``).

        Usa la caché; si estamos online y falta (o se pidió ``refresh``), intenta
        descargarlo y lo cachea. Cualquier fallo de red se traga: se devuelve lo
        que hubiera en caché (o ``None``).
        """
        if ticker in self._mem:
            return self._mem[ticker]
        cached = self._load(ticker)
        if self.offline or (cached is not None and not self.refresh):
            self._mem[ticker] = cached
            return cached
        try:
            data = self._fetch(ticker)
        except Exception as exc:  # best-effort: nunca rompe el build
            print(f"AVISO: sin consenso de analistas para {ticker} ({exc})",
                  file=sys.stderr)
            data = cached
        else:
            if data is not None:
                data = {**data, "asOf": date.today().isoformat()}
                self._save(ticker, data)
            elif cached is not None:
                data = cached
        self._mem[ticker] = data
        return data
