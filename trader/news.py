"""Titulares de prensa por ticker, con caché local en JSON.

La web del ranking es estática: no llama a ninguna API al abrirse. Igual que
los precios o el consenso de analistas, las noticias de los valores que tienen
los participantes de la liga se descargan **en tiempo de build** (el comando
``ranking``, que en GitHub Actions corre con internet abierto), se normalizan y
se embeben en la página; además se cachean en ``data/news/<TICKER>.json`` para
que un fallo puntual de la API no deje la ficha sin titulares.

La fuente es la API de noticias de la liga::

    POST http://imprifyapp.com/api/trader/news
    {"tickers": ["AAPL", "TSLA"], "timezone": "Europe/Madrid", "limit": 5}

que responde con ``results[]``, un bloque por ticker con sus ``news[]``
(``title``, ``description``, ``link``, ``publishedAt``, ``source``). El
endpoint se puede cambiar con ``--news-api`` o con la variable de entorno
``TRADER_NEWS_API`` (útil para apuntar a otro despliegue o a un mock).

Qué se manda y qué no: **solo los símbolos** de la cartera agregada de la liga,
que ya son públicos en la propia página (el widget de cartera los enseña con su
peso). Nunca se manda quién tiene qué, ni importes, ni operaciones.

Todo es *best-effort*: si la API no responde (o el entorno bloquea el host) se
usa lo que hubiera en caché y, si no hay nada, la ficha del valor enseña los
enlaces de búsqueda de siempre. Nunca se inventan titulares y el build no se
rompe por esto.

Los textos y enlaces son de terceros (los agrega la API desde Yahoo Finance /
Finnhub) y se muestran a título informativo, con su fuente y su fecha.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

# El endpoint responde por HTTPS; en claro contesta un 307 hacia él. Se pide
# directo por HTTPS (una ida y vuelta menos, y el cuerpo no viaja en claro),
# pero si alguien apunta a `http://` los redirects se siguen igual.
DEFAULT_ENDPOINT = "https://imprifyapp.com/api/trader/news"
DEFAULT_TIMEZONE = "Europe/Madrid"
DEFAULT_LIMIT = 5
# Tickers por petición: la API acepta una lista, pero se trocea para no mandar
# una petición desmedida cuando la liga tiene muchos valores.
BATCH = 20
TIMEOUT = 20
MAX_REDIRECTS = 3
UA = "trader-league/1.0 (+https://github.com/fedegarlo/trader)"


class _KeepPost(urllib.request.HTTPRedirectHandler):
    """Redirects sin seguir: los reenvía :meth:`NewsCache._post` con su cuerpo.

    Devolver ``None`` aquí hace que urllib no siga el redirect y eleve el
    ``HTTPError``, que es justo lo que necesitamos para repetir el POST en el
    destino en vez de dejar que lo degrade a un GET sin cuerpo.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_KeepPost)

# Formato de símbolo que acepta la API (`AAPL`, `BRK.B`, `^GSPC`, `BTC-USD`).
# Lo que no encaje se descarta antes de mandarlo: la API lo rechazaría igual.
TICKER_RE = re.compile(r"^\^?[A-Z0-9][A-Z0-9.\-]*$")

# Recortes de texto: la página embebe los titulares en el propio HTML, así que
# se acota lo que ocupa cada uno.
MAX_TITLE = 180
MAX_DESC = 220


def _text(value, limit: int) -> str | None:
    """Texto plano recortado a ``limit`` caracteres (o ``None`` si no hay)."""
    if not isinstance(value, str):
        return None
    clean = " ".join(value.split())
    if not clean:
        return None
    if len(clean) > limit:
        clean = clean[:limit - 1].rstrip() + "…"
    return clean


def _link(value) -> str | None:
    """URL http(s) o ``None``: nunca se publica un enlace de otro esquema."""
    if not isinstance(value, str):
        return None
    url = value.strip()
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return None


def normalize_item(raw) -> dict | None:
    """Normaliza una noticia de la API al dict compacto que embebe la página.

    Devuelve ``None`` si le falta lo imprescindible (titular y enlace): un
    titular que no se puede abrir no vale de nada.
    """
    if not isinstance(raw, dict):
        return None
    title = _text(raw.get("title"), MAX_TITLE)
    link = _link(raw.get("link") or raw.get("url"))
    if not title or not link:
        return None
    item = {"title": title, "link": link}
    source = _text(raw.get("source"), 60)
    if source:
        item["source"] = source
    at = _text(raw.get("publishedAt") or raw.get("published_at"), 40)
    if at:
        item["at"] = at
    desc = _text(raw.get("description"), MAX_DESC)
    if desc and desc != title:
        item["desc"] = desc
    return item


def normalize_items(raws, limit: int | None = None) -> list[dict]:
    """Lista de noticias normalizadas, sin repetidos y de más a menos reciente."""
    out: list[dict] = []
    seen: set[str] = set()
    for raw in raws or []:
        item = normalize_item(raw)
        if item is None:
            continue
        key = item["link"]
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    # La API ya las manda ordenadas, pero el orden vuelve a importar cuando se
    # mezclan varios tickers (la ficha de un jugador junta los de su cartera):
    # de más a menos reciente. Las fechas son ISO 8601, que ordena bien como
    # texto; las que no traen fecha se van al final sin alterar su orden.
    out.sort(key=lambda i: i.get("at") or "", reverse=True)
    return out[:limit] if limit else out


def parse_response(payload) -> tuple[dict[str, list[dict]], list[str]]:
    """Normaliza la respuesta de la API a ``({ticker: noticias}, avisos)``.

    Los avisos son texto para stderr (tickers inválidos, errores por ticker o
    un error global): nada de esto rompe el build, solo se cuenta.
    """
    warnings: list[str] = []
    if not isinstance(payload, dict):
        return {}, ["respuesta de la API de noticias que no es un objeto JSON"]
    if payload.get("success") is False or payload.get("error"):
        warnings.append(f"la API de noticias respondió con error: "
                        f"{payload.get('error') or 'success=false'}")
    out: dict[str, list[dict]] = {}
    for result in payload.get("results") or []:
        if not isinstance(result, dict):
            continue
        ticker = result.get("ticker")
        if not isinstance(ticker, str) or not ticker:
            continue
        if result.get("error"):
            warnings.append(f"sin noticias de {ticker} ({result['error']})")
        items = normalize_items(result.get("news"))
        if items:
            out[ticker] = items
    invalid = [t for t in (payload.get("invalidTickers") or []) if isinstance(t, str)]
    if invalid:
        warnings.append("tickers rechazados por la API de noticias: "
                        + ", ".join(invalid))
    return out, warnings


class NewsCache:
    """Titulares por ticker: caché en disco + descarga en lote de la API."""

    def __init__(self, cache_dir: str = "data/news", offline: bool = False,
                 refresh: bool = False, endpoint: str | None = None,
                 limit: int = DEFAULT_LIMIT, timezone: str = DEFAULT_TIMEZONE,
                 today: date | None = None):
        self.cache_dir = cache_dir
        self.offline = offline
        self.refresh = refresh
        self.endpoint = (endpoint or os.environ.get("TRADER_NEWS_API")
                         or DEFAULT_ENDPOINT)
        self.limit = limit
        self.timezone = timezone
        self.today = today or date.today()

    # ----------------------------------------------------------- caché
    def _path(self, ticker: str) -> str:
        safe = re.sub(r"[^A-Za-z0-9.^-]", "_", ticker)
        return os.path.join(self.cache_dir, f"{safe}.json")

    def _load(self, ticker: str) -> dict | None:
        path = self._path(ticker)
        if not os.path.exists(path):
            return None
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) and data.get("items") else None

    def _save(self, ticker: str, items: list[dict]) -> None:
        os.makedirs(self.cache_dir, exist_ok=True)
        with open(self._path(ticker), "w", encoding="utf-8") as fh:
            json.dump({"asOf": self.today.isoformat(), "items": items},
                      fh, ensure_ascii=False, indent=1)

    # ------------------------------------------------------------- red
    def _post(self, tickers: list[str], url: str | None = None,
              hops: int = 0) -> dict:
        """POST del lote, siguiendo los redirects **sin perder el cuerpo**.

        urllib no reenvía un POST cuando le contestan 307/308: lo convierte en
        `HTTPError` (y con 301/302/303 lo reintenta como GET, sin el cuerpo).
        La API contesta 307 al hablarle en claro, así que ese redirect hay que
        seguirlo a mano, repitiendo el POST tal cual en el destino.
        """
        url = url or self.endpoint
        body = json.dumps({
            "tickers": tickers,
            "limit": self.limit,
            "timezone": self.timezone,
        }).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST",
                                     headers={"Content-Type": "application/json",
                                              "Accept": "application/json",
                                              "User-Agent": UA})
        try:
            with _OPENER.open(req, timeout=TIMEOUT) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as exc:
            target = self._redirect_target(exc, url, hops)
            if target is None:
                raise
            return self._post(tickers, target, hops + 1)

    @staticmethod
    def _redirect_target(exc: urllib.error.HTTPError, url: str,
                         hops: int) -> str | None:
        """Destino al que repetir el POST, o ``None`` si no hay que seguir."""
        if exc.code not in (301, 302, 303, 307, 308) or hops >= MAX_REDIRECTS:
            return None
        location = exc.headers.get("Location") if exc.headers else None
        if not location:
            return None
        target = urllib.parse.urljoin(url, location)
        # Nunca se sigue a otro esquema (un `file://` o similar en un Location
        # de terceros no tiene ningún sentido aquí).
        return target if target.startswith(("http://", "https://")) else None

    def _download(self, tickers: list[str]) -> dict[str, list[dict]]:
        """Descarga en lotes; cada lote que falle solo se pierde a sí mismo."""
        fresh: dict[str, list[dict]] = {}
        for i in range(0, len(tickers), BATCH):
            batch = tickers[i:i + BATCH]
            try:
                payload = self._post(batch)
            except Exception as exc:  # best-effort: nunca rompe el build
                print(f"AVISO: sin noticias de {', '.join(batch)} ({exc})",
                      file=sys.stderr)
                continue
            items, warnings = parse_response(payload)
            for warning in warnings:
                print(f"AVISO: {warning}", file=sys.stderr)
            fresh.update(items)
        return fresh

    # ---------------------------------------------------------- lookup
    def fetch_all(self, tickers) -> dict[str, list[dict]]:
        """``{ticker: noticias}`` de los tickers pedidos (los demás se caen).

        Se descarga lo que falte en caché o esté cacheado de otro día (los
        titulares envejecen rápido); con ``refresh`` se vuelve a pedir todo.
        Lo que la API no devuelva se sirve de la caché, si la hay. Con
        ``limit <= 0`` no se pide nada: la página se queda sin titulares.
        """
        if self.limit <= 0:
            return {}
        wanted, skipped = [], []
        for ticker in tickers:
            if TICKER_RE.match(ticker or ""):
                wanted.append(ticker)
            else:
                skipped.append(ticker)
        if skipped:
            print("AVISO: símbolos no válidos para la API de noticias: "
                  + ", ".join(skipped), file=sys.stderr)

        cached = {t: self._load(t) for t in wanted}
        stale = [t for t in wanted
                 if self.refresh or not cached[t]
                 or cached[t].get("asOf") != self.today.isoformat()]

        fresh: dict[str, list[dict]] = {}
        if wanted and stale and not self.offline:
            fresh = self._download(stale)
            for ticker, items in fresh.items():
                if ticker in cached:  # solo se cachea lo que se ha pedido
                    self._save(ticker, items)

        out: dict[str, list[dict]] = {}
        for ticker in wanted:
            items = fresh.get(ticker)
            if not items and cached.get(ticker):
                items = normalize_items(cached[ticker].get("items"))
            if items:
                out[ticker] = items[:self.limit]
        return out
