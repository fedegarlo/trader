"""Sesión anónima contra la API de Yahoo Finance (cookie + crumb).

Los endpoints ``quoteSummary`` exigen desde hace tiempo una cookie de sesión y
un «crumb»; el de ``chart`` (los cierres diarios de :mod:`trader.prices`) sigue
siendo abierto y no pasa por aquí.

Esta sesión la comparten el consenso de analistas (:mod:`trader.analysts`) y la
cotización fuera de horario (:mod:`trader.extended`), de forma que la cookie y
el crumb se piden **una sola vez** por ejecución del build en lugar de una vez
por módulo.
"""

from __future__ import annotations

import http.cookiejar
import json
import urllib.error
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
# Hosts equivalentes: si uno responde con un error transitorio (401/429, muy
# habituales en las peticiones anónimas) se reintenta en el otro.
HOSTS = ("query1.finance.yahoo.com", "query2.finance.yahoo.com")


def num(value):
    """Acepta un número crudo o el ``{"raw":..}`` de Yahoo y devuelve float."""
    if isinstance(value, dict):
        value = value.get("raw")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class Session:
    """Cookie + crumb de Yahoo, obtenidos de forma perezosa y reutilizados."""

    def __init__(self) -> None:
        self._crumb: str | None = None
        self._opener: urllib.request.OpenerDirector | None = None
        self._failed: Exception | None = None

    def _ensure(self) -> None:
        """Negocia cookie y crumb una vez; si no se puede, no se reintenta.

        Cuando el entorno no llega a Yahoo (proxy, bloqueo de red) el handshake
        falla para todos los tickers por igual. Recordar el fallo evita repetir
        dos peticiones con su timeout por cada ticker, que era lo que hacía que
        un build sin salida a internet tardara minutos en rendirse.
        """
        if self._crumb is not None:
            return
        if self._failed is not None:
            raise self._failed
        try:
            self._handshake()
        except Exception as exc:
            self._failed = exc
            raise

    def _handshake(self) -> None:
        jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(jar))
        # una visita a finance.yahoo.com siembra la cookie de sesión
        req = urllib.request.Request("https://finance.yahoo.com/quote/AAPL",
                                     headers={"User-Agent": UA})
        with self._opener.open(req, timeout=20):
            pass
        req = urllib.request.Request(
            "https://query1.finance.yahoo.com/v1/test/getcrumb",
            headers={"User-Agent": UA, "Accept": "text/plain"})
        with self._opener.open(req, timeout=20) as resp:
            self._crumb = resp.read().decode("utf-8").strip()

    def get_json(self, path: str, params: dict | None = None,
                 timeout: int = 25) -> dict:
        """GET de ``https://<host>/<path>?<params>&crumb=…`` devuelto como JSON.

        Prueba los dos hosts equivalentes; si fallan ambos eleva el último
        error (quien llama decide si eso es fatal o solo un aviso).
        """
        self._ensure()
        query = urllib.parse.urlencode({**(params or {}),
                                        "crumb": self._crumb or ""})
        last_err: Exception | None = None
        for host in HOSTS:
            url = f"https://{host}/{path.lstrip('/')}?{query}"
            req = urllib.request.Request(url, headers={
                "User-Agent": UA, "Accept": "application/json"})
            try:
                with self._opener.open(req, timeout=timeout) as resp:  # type: ignore[union-attr]
                    return json.load(resp)
            except (urllib.error.URLError, TimeoutError, ValueError) as exc:
                last_err = exc
        raise last_err  # type: ignore[misc]
