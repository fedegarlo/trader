"""Sistema de insignias (badges) **acumulativo**.

Calcula los logros de la liga a partir de las series diarias de cada jugador y
los va **acumulando** en un histórico persistente (``data/badges.json``). La
idea clave es que el histórico **no se recalcula desde cero** en cada ejecución:
se **añaden** las insignias nuevas a las ya conseguidas (una insignia, una vez
ganada, se conserva para siempre), y el récord de «mayor subida de un valor en
un día» solo se **actualiza cuando alguien lo supera**, guardando el anterior en
su historial.

Insignias que se otorgan:

* ``champion_month``   — campeón del mes (mejor rentabilidad compuesta del mes).
                         Los meses ya cerrados quedan grabados; el mes en curso
                         se muestra como provisional (no se persiste).
* ``week_streak``      — una semana ganando: 5 jornadas de mercado seguidas en
                         verde.
* ``milestone`` 5/10/25 — alcanzar +5 %, +10 % o +25 % de rentabilidad acumulada.
* ``months_2`` / ``months_3`` — dos o tres meses naturales consecutivos ganando.
* récord ``top_daily_gain`` — mayor subida de un solo valor en un solo día. Es un
                         récord de la liga que se reescribe cada vez que se supera
                         (el anterior pasa a ``history``).

Todo el módulo trabaja con porcentajes y metadatos públicos (ticker, fecha,
nombre del jugador): nunca importes ni operaciones, igual que el resto de la web.
"""

from __future__ import annotations

import json
import os
from datetime import date

from .players import Player
from .portfolio import DayResult, _positions_at

# Umbrales de rentabilidad acumulada (en %) que otorgan la insignia de hito.
MILESTONES = (5, 10, 25)
# Jornadas de mercado seguidas en verde para la insignia de «una semana ganando».
WEEK_STREAK = 5
# Rachas de meses naturales consecutivos ganando que se premian.
MONTH_STREAKS = (2, 3)
# Cuántos récords antiguos se conservan en el historial del récord de la liga.
RECORD_HISTORY = 10

DEFAULT_STORE = "data/badges.json"


# --------------------------------------------------------------------------- #
# Persistencia del histórico
# --------------------------------------------------------------------------- #
def _empty_store() -> dict:
    return {"version": 1, "awards": [], "record": None}


def load_store(path: str = DEFAULT_STORE) -> dict:
    """Carga el histórico de insignias; si no existe (o está corrupto), vacío."""
    try:
        with open(path, encoding="utf-8") as fh:
            store = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return _empty_store()
    store.setdefault("version", 1)
    store.setdefault("awards", [])
    store.setdefault("record", None)
    return store


def save_store(store: dict, path: str = DEFAULT_STORE) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(store, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    return path


# --------------------------------------------------------------------------- #
# Cálculos sobre las series
# --------------------------------------------------------------------------- #
def _next_month(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


def _monthly_returns(series: list[DayResult]) -> dict[tuple[int, int], float]:
    """Rentabilidad compuesta (fracción) de cada mes natural con datos."""
    factors: dict[tuple[int, int], float] = {}
    for r in series:
        key = (r.day.year, r.day.month)
        factors[key] = factors.get(key, 1.0) * (1.0 + r.daily_return)
    return {k: v - 1.0 for k, v in factors.items()}


def _last_day_in_month(series: list[DayResult], year: int, month: int) -> date:
    days = [r.day for r in series if r.day.year == year and r.day.month == month]
    return max(days) if days else date(year, month, 1)


def _milestone_date(series: list[DayResult], tier: int) -> date | None:
    """Primer día en que la rentabilidad acumulada alcanza ``tier`` %."""
    for r in series:
        if r.cumulative_return * 100 >= tier:
            return r.day
    return None


def _week_streak_date(series: list[DayResult], need: int = WEEK_STREAK) -> date | None:
    """Día en que se completa la primera racha de ``need`` jornadas en verde.

    Las filas de la serie son jornadas de mercado consecutivas (los fines de
    semana y festivos no generan fila), así que ``need`` filas seguidas con
    rentabilidad positiva equivalen a «una semana ganando».
    """
    run = 0
    for r in series:
        if r.daily_return > 0:
            run += 1
            if run >= need:
                return r.day
        else:
            run = 0
    return None


def _months_streak_end(series: list[DayResult], today: date, n: int) -> tuple[int, int] | None:
    """Mes en que se cierra la primera racha de ``n`` meses consecutivos ganando.

    Solo cuentan los meses **ya cerrados** (anteriores al mes en curso): un mes
    a medias todavía puede torcerse. Devuelve ``(año, mes)`` del mes que remata
    la racha, o ``None`` si aún no se ha logrado.
    """
    months = _monthly_returns(series)
    completed = sorted(k for k in months if k < (today.year, today.month))
    run = 0
    prev: tuple[int, int] | None = None
    for key in completed:
        winning = months[key] > 0
        if winning and prev is not None and _next_month(*prev) == key:
            run += 1
        elif winning:
            run = 1
        else:
            run = 0
        prev = key
        if run >= n:
            return key
    return None


def _champions(computed: list[tuple[Player, list[DayResult]]], today: date):
    """Campeón de cada mes con datos.

    Rinde ``(year, month, player_id, name, ret_pct, date, provisional)`` por
    cada mes. ``provisional`` es cierto para el mes en curso (aún no cerrado):
    esas insignias se muestran pero no se persisten. Los empates se resuelven
    de forma determinista por id de jugador.
    """
    series_by_id = {p.player_id: s for p, s in computed}
    names = {p.player_id: p.display_name for p, _ in computed}
    per: dict[tuple[int, int], list[tuple[float, str]]] = {}
    for player, series in computed:
        for key, ret in _monthly_returns(series).items():
            per.setdefault(key, []).append((ret, player.player_id))

    out = []
    for (year, month), rows in sorted(per.items()):
        rows.sort(key=lambda x: (-x[0], x[1]))
        ret, pid = rows[0]
        provisional = (year, month) >= (today.year, today.month)
        out.append((
            year, month, pid, names[pid], round(ret * 100, 2),
            _last_day_in_month(series_by_id[pid], year, month), provisional,
        ))
    return out


def _best_daily_moves(price_history: dict[str, list]) -> list[tuple[float, str, date]]:
    """Subida porcentual de cada jornada de cada valor: ``(pct, ticker, fecha)``.

    ``price_history`` es ``{ticker: [(fecha, cierre), ...]}`` (cierres públicos).
    Solo se consideran las subidas (día a día); las bajadas no compiten por el
    récord.
    """
    out: list[tuple[float, str, date]] = []
    for ticker, hist in (price_history or {}).items():
        seq = sorted(hist, key=lambda item: item[0])
        for (_d0, c0), (d1, c1) in zip(seq, seq[1:]):
            if c0 and c0 > 0:
                pct = (c1 / c0 - 1.0) * 100
                if pct > 0:
                    out.append((pct, ticker, d1))
    return out


def _holders_on(computed: list[tuple[Player, list[DayResult]]],
                ticker: str, day: date) -> list[dict]:
    """Jugadores que tenían ``ticker`` en cartera al cierre de ``day``."""
    out = []
    for player, _series in computed:
        positions, _cash = _positions_at(player.events, day)
        if positions.get(ticker, 0.0) > 1e-9:
            out.append({"id": player.player_id, "name": player.display_name})
    return out


# --------------------------------------------------------------------------- #
# Motor: acumula insignias nuevas y actualiza el récord
# --------------------------------------------------------------------------- #
def _update_record(store: dict,
                   price_history: dict[str, list] | None,
                   computed: list[tuple[Player, list[DayResult]]],
                   today: date) -> dict | None:
    """Actualiza el récord de «mayor subida de un valor en un día» si se supera.

    El récord vive en el histórico y solo se reescribe cuando la mayor subida
    observada en los precios disponibles bate la guardada; el récord anterior se
    conserva en ``history`` (acotado a los últimos ``RECORD_HISTORY``). Así el
    récord es **acumulativo**: no depende de que los precios de la jornada que lo
    fijó sigan en la caché.
    """
    moves = _best_daily_moves(price_history or {})
    if not moves:
        return store.get("record")
    pct, ticker, day = max(moves, key=lambda m: m[0])
    pct = round(pct, 2)
    current = store.get("record")
    if current is not None and pct <= current.get("pct", float("-inf")) + 1e-9:
        return current

    history = list(current.get("history", [])) if current else []
    if current:
        history.append({k: v for k, v in current.items() if k != "history"})
    store["record"] = {
        "ticker": ticker,
        "pct": pct,
        "date": day.isoformat(),
        "holders": _holders_on(computed, ticker, day),
        "recorded": today.isoformat(),
        "history": history[-RECORD_HISTORY:],
    }
    return store["record"]


def update_badges(computed: list[tuple[Player, list[DayResult]]],
                  store: dict | None = None,
                  *,
                  price_history: dict[str, list] | None = None,
                  today: date | None = None) -> tuple[dict, dict]:
    """Añade al histórico las insignias nuevas y actualiza el récord.

    Devuelve ``(store, display)``: ``store`` es el histórico persistente ya
    actualizado (para guardarlo) y ``display`` son los datos listos para la web
    (insignias ordenadas de más reciente a más antigua, con el color de cada
    jugador, más el récord de la liga y el campeón provisional del mes en curso).
    """
    today = today or date.today()
    store = store or _empty_store()
    store.setdefault("awards", [])
    store.setdefault("record", None)
    awards: list[dict] = store["awards"]
    existing = {a["key"] for a in awards}

    def add(key: str, award: dict) -> None:
        if key in existing:
            return
        award = {"key": key, "recorded": today.isoformat(), **award}
        awards.append(award)
        existing.add(key)

    # Color estable por jugador (orden alfabético de id), como en el resto de la web.
    order = {p.player_id: i for i, p in enumerate(
        sorted((p for p, _ in computed), key=lambda p: p.player_id))}

    provisional: list[dict] = []
    for year, month, pid, name, ret, day, is_prov in _champions(computed, today):
        award = {
            "type": "champion_month", "player": pid, "name": name,
            "date": day.isoformat(), "month": f"{year}-{month:02d}", "pct": ret,
        }
        if is_prov:
            provisional.append({**award, "key": f"champion:{year}-{month:02d}",
                                "provisional": True})
        else:
            add(f"champion:{year}-{month:02d}", award)

    for player, series in computed:
        pid, name = player.player_id, player.display_name
        for tier in MILESTONES:
            day = _milestone_date(series, tier)
            if day:
                add(f"milestone:{pid}:{tier}", {
                    "type": "milestone", "tier": tier, "player": pid,
                    "name": name, "date": day.isoformat()})
        day = _week_streak_date(series)
        if day:
            add(f"week_streak:{pid}", {
                "type": "week_streak", "player": pid, "name": name,
                "date": day.isoformat()})
        for n in MONTH_STREAKS:
            end = _months_streak_end(series, today, n)
            if end:
                add(f"months_{n}:{pid}", {
                    "type": f"months_{n}", "player": pid, "name": name,
                    "date": _last_day_in_month(series, *end).isoformat(),
                    "month": f"{end[0]}-{end[1]:02d}"})

    record = _update_record(store, price_history, computed, today)

    def decorate(award: dict) -> dict:
        return {**award, "slot": order.get(award.get("player"), 0)}

    feed = sorted((decorate(a) for a in awards),
                  key=lambda a: (a.get("date", ""), a.get("recorded", "")),
                  reverse=True)
    display = {
        "awards": feed,
        "provisional": [decorate(a) for a in provisional],
        "record": record,
    }
    return store, display
