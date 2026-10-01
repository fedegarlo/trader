"""Genera docs/index.html: dashboard estático para GitHub Pages.

Autocontenido (datos embebidos, sin CDNs). La portada es un **hilo de
conversación** al estilo de los agentes (dibujitos + burbujas): Warren
(Trader) y Scout (Watch) van contando la liga, y debajo de cada turno
siguen los mismos módulos de siempre. De primero, el «Canada Grand Prix
26/27»: el banner de turismo de Canadá hace de cabecera de la clasificación
general —el viaje es el premio—, debajo va quién lo lleva ganado (líder y
podio) y luego la clasificación en formato tabla (1º, 2º, 3º… con su
acumulado y el % de la última jornada). El mes en curso se cuenta igual, con
su propia carrera: el «Gran Premio de la ciudad de Vancouver», con el banner
del ayuntamiento (vancouver.ca) de cabecera, el líder y el podio del mes, y
detrás la gráfica de todos los jugadores. Las líneas van suavizadas (spline
cúbico monótono, sin sobreoscilación) y el color se asigna a cada jugador por
orden alfabético de id (estable: no cambia si cambia su posición en el
ranking) de una paleta cálida: naranja, marrón y ocres.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from datetime import date, datetime, time, timezone

from .players import DEFAULT_GOAL, Player
from .portfolio import CASH_KEY, DayResult
from .revolut import BUY, SELL
from .tickers import ticker_meta

# La competición oficial empezó este día: los días anteriores (pruebas o
# histórico previo) no cuentan. Todos los jugadores se comparan desde esta
# fecha (incluida), rebasando la rentabilidad acumulada al inicio real de la
# competición (ver ``rebase_from`` en portfolio.py), y también acota los
# widgets de «mejor del mes».
COMPETITION_START = date(2026, 7, 14)

# El objetivo de la liga tiene fecha: el 1 de agosto. Es una meta que se
# renueva cada año, así que la cuenta atrás mira siempre al **próximo** 1 de
# agosto (el mismo día 1 todavía cuenta como plazo abierto, con 0 días).
GOAL_MONTH, GOAL_DAY = 8, 1

# Quién invita y **dónde**: el ganador del mes paga la comida, y su propia
# rentabilidad decide el precio del sitio. Cuanto mejor le haya ido, más caro
# es el restaurante; un mes en rojo se salda con unas cañas.
#
# La escala vive aquí (y viaja entera al payload, ``treatScale``) para que la
# página, el README y las pruebas hablen del mismo baremo. Cada peldaño lleva:
#
# - ``min``: rentabilidad mensual (en %) a partir de la cual se entra en él;
#   ``None`` es el primero, el de los meses en negativo.
# - ``euros``: los € de la categoría, como en cualquier guía.
# - ``price``: precio orientativo por persona (en euros, bebida incluida); en
#   el último peldaño se lee como «a partir de».
# - ``places``: restaurantes de Madrid de ejemplo, solo como referencia de a
#   qué precio juega cada escalón.
#
# El nombre de cada peldaño se traduce en el cliente (``treatTiers``): aquí no
# hay texto que traducir, solo el baremo.
TREAT_TIERS: list[dict] = [
    {"min": None, "euros": "€", "price": 15,
     "places": ["El Tigre", "Casa Julio", "Bar Santurce"]},
    {"min": 0.0, "euros": "€€", "price": 30,
     "places": ["La Ardosa", "La Musa", "La Carmencita"]},
    {"min": 2.5, "euros": "€€€", "price": 55,
     "places": ["Casa Lucio", "Sala de Despiece", "Ten con Ten"]},
    {"min": 5.0, "euros": "€€€€", "price": 110,
     "places": ["Sacha", "Horcher", "Kabuki"]},
    {"min": 10.0, "euros": "€€€€€", "price": 200,
     "places": ["DiverXO", "Coque", "DSTAgE"]},
]


def treat_tier(value: float | None) -> int | None:
    """Peldaño de :data:`TREAT_TIERS` que le toca a una rentabilidad mensual.

    ``value`` va en porcentaje (el mismo que se pinta en el widget), así que el
    tramo y el número que se enseña nunca se contradicen. Devuelve ``None`` si
    no hay dato.
    """
    if value is None:
        return None
    tier = 0
    for i, step in enumerate(TREAT_TIERS):
        if step["min"] is not None and value >= step["min"]:
            tier = i
    return tier



def _read_web_text(web: Path, name: str) -> str:
    """Lee ``trader/web/<name>`` o, si falta, concatena ``_pack/<name>.p*``.

    Las partes son texto UTF-8 crudo (no gzip): así el ensamblado no depende
    de un script extra y GitHub puede recibir el CSS/JS en trozos pequeños.
    """
    direct = web / name
    if direct.is_file() and direct.stat().st_size:
        return direct.read_text(encoding="utf-8")
    parts = sorted((web / "_pack").glob(name + ".p*"))
    if not parts:
        raise FileNotFoundError(direct)
    return "".join(p.read_text(encoding="utf-8") for p in parts)


def _assemble_template() -> str:
    """Junta cabecera, CSS, cuerpo y JS de ``trader/web`` en un HTML autocontenido."""
    web = Path(__file__).resolve().parent / "web"
    css = _read_web_text(web, "style.css")
    head = _read_web_text(web, "head.html").replace("/* __PAGE_CSS__ */", css)
    body = _read_web_text(web, "body.html")
    boot = _read_web_text(web, "boot.js")
    app = _read_web_text(web, "app.js")
    return (
        head
        + body
        + "<script>\n"
        + boot
        + app
        + "</script>\n</body>\n</html>\n"
    )


_TEMPLATE = _assemble_template()


def _allocation_weights(allocation: dict[str, float] | None) -> list[dict]:
    """Normaliza el valor de mercado agregado por ticker a pesos (%).

    Recibe ``{ticker: valor}`` (agregado de toda la liga) y devuelve una lista
    ordenada de mayor a menor ``[{\"ticker\", \"w\"}]`` con el peso en porcentaje.
    Solo se exponen pesos, nunca importes: el mix agregado no revela ni las
    operaciones ni el dinero de ningún jugador.
    """
    if not allocation:
        return []
    total = sum(v for v in allocation.values() if v > 0)
    if total <= 0:
        return []
    out = [{"ticker": t, "w": round(v / total * 100, 2)}
           for t, v in allocation.items() if v > 0]
    out.sort(key=lambda d: d["w"], reverse=True)
    return out


def _ticker_details(
    allocation: dict[str, float] | None,
    holdings: dict[str, dict[str, float]],
    order: dict[str, int],
    names: dict[str, str],
    prices: dict[str, list[tuple]] | None,
    price_days: int,
    analysts: dict[str, dict] | None = None,
    extended: dict[str, dict] | None = None,
    news: dict[str, list[dict]] | None = None,
) -> list[dict]:
    """Detalle público por ticker para la vista de detalle de la web.

    Para cada valor de la cartera agregada de la liga reúne: nombre y dominio
    (para el logo), peso agregado (%), qué jugadores lo tienen con su peso
    dentro de *su propia* cartera (solo %), y una mini-serie de precio de cierre
    de los últimos ``price_days`` días con su variación. Esta ventana es solo
    del contexto de mercado del valor: la competición (la gráfica del acumulado)
    va siempre desde el inicio. Nada de esto expone importes ni operaciones:
    pesos y precios públicos de mercado.
    """
    weights = _allocation_weights(allocation)
    if not weights:
        return []
    prices = prices or {}
    analysts = analysts or {}
    extended = extended or {}
    news = news or {}
    out = []
    for item in weights:
        ticker = item["ticker"]
        meta = ticker_meta(ticker)
        peers = []
        for peer in meta.get("peers", []):
            pm = ticker_meta(peer)
            peers.append({"ticker": peer, "name": pm["name"], "domain": pm["domain"]})
        holders = []
        for pid, hv in holdings.items():
            for x in _allocation_weights(hv):
                if x["ticker"] == ticker:
                    holders.append({
                        "name": names.get(pid, pid),
                        "slot": order.get(pid, 0),
                        "w": x["w"],
                    })
                    break
        holders.sort(key=lambda h: h["w"], reverse=True)

        raw = prices.get(ticker) or []
        window = raw[-price_days:] if price_days else raw
        series = [{"date": d.isoformat() if hasattr(d, "isoformat") else str(d),
                   "close": round(float(c), 4)} for d, c in window]
        ret = None
        if len(series) >= 2 and series[0]["close"]:
            ret = round((series[-1]["close"] / series[0]["close"] - 1.0) * 100, 2)

        entry = {
            "ticker": ticker,
            "name": meta["name"],
            "domain": meta["domain"],
            "w": item["w"],
            "holders": holders,
            "prices": series,
            "ret": ret,
            "peers": peers,
        }
        consensus = analysts.get(ticker)
        if consensus:
            entry["analyst"] = consensus
        ext = extended.get(ticker)
        if ext:
            entry["ext"] = ext
        headlines = news.get(ticker)
        if headlines:
            entry["news"] = headlines
        out.append(entry)
    return out


def _market_snapshot(allocation: dict[str, float] | None,
                     extended: dict[str, dict] | None,
                     stamp: int) -> dict | None:
    """Resumen de la sesión extendida en curso para la tarjeta del dashboard.

    Devuelve la sesión (``pre``/``post``), cuándo se tomó la foto y la variación
    media de la liga: la media de la variación de cada valor **ponderada por su
    peso en la cartera agregada**, así que pesa lo que de verdad pesa. Solo
    entran los valores con dato de esa misma sesión, y los pesos se
    renormalizan entre ellos.

    ``stamp`` es el instante del build en segundos epoch: la página lo usa para
    decir a qué hora se tomó la foto y para esconder la tarjeta si quien la abre
    lo hace mucho después (la web es estática y no se refresca sola).

    ``None`` si no hay ninguna sesión extendida en curso (mercado abierto,
    noche cerrada o fin de semana): entonces la tarjeta no se pinta.
    """
    extended = extended or {}
    weights = {d["ticker"]: d["w"] for d in _allocation_weights(allocation)}

    # Puede que algún ticker vaya rezagado y siga en la sesión anterior (o que
    # la liga tenga valores de plazas distintas): manda la sesión que más pesa
    # en la cartera, y a igualdad de peso la que tenga más valores.
    stats: dict[str, list[float]] = {}
    for ticker, quote in extended.items():
        session = quote.get("session")
        if not session:
            continue
        acc = stats.setdefault(session, [0.0, 0.0])
        acc[0] += weights.get(ticker, 0.0)
        acc[1] += 1
    if not stats:
        return None
    session = max(sorted(stats), key=lambda s: (stats[s][0], stats[s][1]))

    total = 0.0
    weighted = 0.0
    count = 0
    for ticker, quote in extended.items():
        if quote.get("session") != session or quote.get("pct") is None:
            continue
        count += 1
        w = weights.get(ticker, 0.0)
        total += w
        weighted += w * quote["pct"]
    snapshot = {"session": session, "asOf": stamp, "count": count}
    if total > 0:
        snapshot["pct"] = round(weighted / total, 2)
    return snapshot


def _buy_sell_suggestion(holdings_weights: list[dict],
                         analysts: dict[str, dict]) -> dict | None:
    """Sugerencia de «próximo paso» sobre la cartera de un jugador.

    De sus posiciones con consenso de analistas elige la de señal más marcada:
    la de mayor recorrido al alza (comprar/ampliar) o mayor recorrido a la baja
    (reducir/vender). Es solo informativo, a partir del consenso de Yahoo; no es
    una recomendación de inversión. Devuelve ``None`` si ninguna posición tiene
    datos de analistas.
    """
    if not holdings_weights or not analysts:
        return None
    best = None
    best_score = -1.0
    for h in holdings_weights:
        a = analysts.get(h["ticker"])
        if not a:
            continue
        upside = a.get("upside")
        # saliencia: si hay precio objetivo, el recorrido; si no, la distancia a
        # «mantener» según la media de recomendación (1=compra fuerte, 5=venta).
        if upside is not None:
            score = abs(upside)
            action = "buy" if upside >= 0 else "trim"
        elif a.get("mean") is not None:
            score = abs(3.0 - a["mean"]) * 8.0
            action = "buy" if a["mean"] < 3.0 else "trim"
        else:
            continue
        if a.get("tone") == "neg":
            action = "trim"
        elif a.get("tone") == "pos":
            action = "buy"
        if score > best_score:
            best_score = score
            meta = ticker_meta(h["ticker"])
            best = {
                "ticker": h["ticker"],
                "name": meta["name"],
                "domain": meta["domain"],
                "w": h["w"],
                "action": action,
                "label": a.get("label"),
                "tone": a.get("tone"),
                "upside": upside,
                "count": a.get("count"),
                "target": a.get("target"),
            }
    return best


def _goal_deadline(today: date) -> date:
    """El próximo 1 de agosto, contando el de hoy si hoy es 1 de agosto."""
    deadline = date(today.year, GOAL_MONTH, GOAL_DAY)
    if deadline < today:
        deadline = date(today.year + 1, GOAL_MONTH, GOAL_DAY)
    return deadline


def _goal_progress(player: Player, series: list[DayResult],
                   fx: dict[str, float] | None) -> dict | None:
    """Avance del jugador hacia su objetivo, o ``None`` si no lo publica.

    El progreso se mide sobre el valor de la cartera al cierre del último día
    calculado — inversiones **más** efectivo, que es justo lo que persigue el
    objetivo — contra el objetivo del jugador (``goal`` en su ``player.json``,
    14.000 por defecto).

    El objetivo está **en euros** y la cartera se valora en la divisa del
    extracto (dólares, para los valores de EE. UU.), así que hay que convertir:
    sin hacerlo, una cartera de 5.895 $ salía al 42 % de 14.000 € cuando en
    realidad va por el 36 %. ``fx`` trae el cambio a euros por divisa (ver
    :mod:`trader.fx`); si falta el de este jugador se devuelve
    ``{\"noFx\": True}`` — el módulo dirá que no hay cambio en vez de enseñar un
    porcentaje equivocado.

    Como el porcentaje deja adivinar el importe de la cartera, solo se publica
    si el jugador lo activa con ``\"show_goal\": true``; el importe exacto,
    además, sigue necesitando ``\"show_amounts\": true``. Sin ``show_goal`` esta
    función devuelve ``None`` y el jugador aparece en el módulo sin barra.
    """
    if not player.show_goal or not series or player.goal <= 0:
        return None
    goal = {"target": round(player.goal, 2)}
    currency = (player.currency or "EUR").upper()
    rate = (fx or {}).get(currency)
    if rate is None:
        goal["noFx"] = True
        goal["currency"] = currency
        return goal
    value = max(series[-1].end_value, 0.0) * rate   # en euros
    goal["pct"] = round(value / player.goal * 100, 2)
    if currency != "EUR":
        goal["currency"] = currency
    if player.show_amounts:
        goal["value"] = round(value, 2)
    return goal


def _player_months(rows: list[DayResult]) -> list[dict]:
    """Rentabilidad mes a mes de un jugador, del más reciente al más antiguo.

    Es lo que pinta el **detalle mensual**: ``ret`` es la composición de los %
    diarios dentro del mes (∏(1+rₙ)−1, igual que el acumulado) y ``cum`` el
    acumulado desde el inicio al cierre del mes. Solo rentabilidad: aquí no
    viaja ningún importe, ni siquiera de quien publica los suyos.
    """
    by_month: dict[tuple[int, int], list[DayResult]] = {}
    for row in rows:
        by_month.setdefault((row.day.year, row.day.month), []).append(row)

    out = []
    for (year, month), items in sorted(by_month.items(), reverse=True):
        factor = 1.0
        for row in items:
            factor *= 1.0 + row.daily_return
        out.append({
            "month": month,
            "month_year": year,
            "ret": round((factor - 1.0) * 100, 4),
            "cum": round(max(items, key=lambda r: r.day).cumulative_return * 100, 4),
        })
    return out


def _prev_month(year: int, month: int) -> tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


def _month_best(computed: list[tuple[Player, list[DayResult]]],
                year: int, month: int, order: dict[str, int]) -> dict | None:
    """Mejor jugador de un mes concreto (composición de sus % diarios).

    Solo cuentan los días de la competición (``day >= COMPETITION_START``). Si
    nadie tiene datos ese mes devuelve ``None`` (el widget no se pinta).

    Además del ganador se publica la evolución de *todos* los jugadores dentro
    del mes (``dates`` + ``series``), para que el widget dibuje la gráfica
    completa —cada jugador con su color— y no solo la del campeón. Cada entrada
    de ``series`` trae su acumulado alineado con ``dates`` (``None`` en los días
    en los que ese jugador no tiene jornada) y llega ordenada de mejor a peor.

    ``treat`` es el peldaño de :data:`TREAT_TIERS` que le toca pagar al ganador:
    cuanto mejor sea el mes, más caro el restaurante (ver :func:`treat_tier`).
    """
    tracks = []
    for player, series in computed:
        rows = sorted(
            (r for r in series
             if r.day.year == year and r.day.month == month
             and r.day >= COMPETITION_START),
            key=lambda r: r.day)
        if not rows:
            continue
        factor = 1.0
        points = {}
        for r in rows:
            factor *= 1.0 + r.daily_return
            points[r.day.isoformat()] = round((factor - 1.0) * 100, 4)
        tracks.append({
            "id": player.player_id,
            "name": player.display_name,
            "slot": order[player.player_id],
            "ret": (factor - 1.0) * 100,
            "points": points,
        })
    if not tracks:
        return None

    dates = sorted({d for t in tracks for d in t["points"]})
    # Orden estable: en caso de empate manda el orden de ``computed``, igual que
    # cuando el ganador se elegía con una comparación estricta.
    tracks.sort(key=lambda t: -t["ret"])
    best = tracks[0]
    value = round(best["ret"], 2)
    return {
        "name": best["name"],
        "value": value,
        # Categoría del restaurante que le toca pagar (ver ``TREAT_TIERS``): se
        # calcula sobre el valor ya redondeado, el mismo que canta el widget.
        "treat": treat_tier(value),
        "slot": best["slot"],
        "month": month,
        "month_year": year,
        "dates": dates,
        "series": [{
            "id": t["id"],
            "name": t["name"],
            "slot": t["slot"],
            "value": round(t["ret"], 2),
            "cum": [t["points"].get(d) for d in dates],
        } for t in tracks],
    }


def _monthly_bests(computed: list[tuple[Player, list[DayResult]]],
                   today: date, order: dict[str, int]) -> dict:
    """Mejor de este mes y del mes pasado (``None`` si no hay datos)."""
    py, pm = _prev_month(today.year, today.month)
    return {
        "current": _month_best(computed, today.year, today.month, order),
        "previous": _month_best(computed, py, pm, order),
    }


def _daily_winners(computed: list[tuple[Player, list[DayResult]]],
                   year: int, month: int, order: dict[str, int]) -> list[dict]:
    """Ganador de cada día del mes: mayor rentabilidad diaria (con empates).

    Solo cuentan los días de la competición (``day >= COMPETITION_START``). La
    lista sale ordenada de más reciente a más antigua para que el día de hoy
    quede arriba en la tabla.
    """
    by_day: dict[date, list[tuple[str, str, int, float]]] = {}
    for player, series in computed:
        for r in series:
            if (r.day.year == year and r.day.month == month
                    and r.day >= COMPETITION_START):
                by_day.setdefault(r.day, []).append(
                    (player.player_id, player.display_name,
                     order[player.player_id], r.daily_return))

    out = []
    for day in sorted(by_day, reverse=True):
        best = max(ret for _id, _n, _s, ret in by_day[day])
        winners = sorted((name, pid, slot)
                         for pid, name, slot, ret in by_day[day] if ret == best)
        out.append({
            "date": day.isoformat(),
            "names": [n for n, _pid, _s in winners],
            "ids": [pid for _n, pid, _s in winners],
            "slot": winners[0][2] if len(winners) == 1 else None,
            "value": round(best * 100, 2),
        })
    return out


def _drop_weekends(
    computed: list[tuple[Player, list[DayResult]]],
) -> list[tuple[Player, list[DayResult]]]:
    """Elimina sábados y domingos de cada serie.

    Los mercados cierran el fin de semana: no hay competición esos días (la
    rentabilidad diaria sería ~0), así que no deben mostrarse en ninguna vista
    (tablas, gráficas del mes, «mejor del día» ni «campeón de cada día»). El acumulado
    de cada jornada hábil ya es correcto, así que basta con descartar las filas
    del fin de semana sin recomponer nada.
    """
    return [(player, [r for r in series if r.day.weekday() < 5])
            for player, series in computed]


def _recent_operations(computed: list[tuple[Player, list[DayResult]]],
                       order: dict[str, int], limit: int = 8) -> list[dict]:
    """Las últimas ``limit`` operaciones (compras/ventas) de toda la liga.

    Solo compras y ventas de un valor concreto (los ingresos, retiradas,
    dividendos, comisiones y splits no son «operaciones» que interesen al
    widget). No expone importes ni cantidades: solo fecha, jugador, si fue
    compra o venta y el ticker — el mismo nivel de detalle que ya publica la
    web con las carteras por jugador.

    Se ordena por el instante de la operación (el CSV de Revolut trae la hora)
    y, cuando no hay hora —el PDF de cuenta solo da el día—, por el orden del
    extracto: las filas de más abajo son las más recientes. El desempate por
    posición solo vale dentro del extracto de un jugador, así que sin hora dos
    operaciones del mismo día de jugadores distintos quedan en un orden
    arbitrario pero estable.
    """
    ops: list[tuple[date, datetime, int, str, str, int, str, str]] = []
    for player, _series in computed:
        for seq, ev in enumerate(player.events):
            if ev.kind in (BUY, SELL) and ev.ticker:
                ops.append((ev.day, ev.at or datetime.combine(ev.day, time.min),
                            seq, player.player_id, player.display_name,
                            order[player.player_id], ev.kind, ev.ticker))
    ops.sort(key=lambda o: (o[0], o[1], o[2]), reverse=True)
    return [{"date": day.isoformat(), "id": pid, "name": name,
             "slot": slot, "kind": kind, "ticker": ticker}
            for day, _at, _seq, pid, name, slot, kind, ticker in ops[:limit]]


def _day_breakdown(contrib: dict[str, float] | None, denom: float) -> list[dict]:
    """Convierte la descomposición por ticker de una jornada a porcentajes.

    Recibe ``{ticker: contribución}`` (en importe) y la base del día
    (``inicio + flujo/2``, el mismo denominador de Dietz) y devuelve una lista
    ``[{\"ticker\", \"pct\"}]`` ordenada por magnitud, donde la suma de los ``pct``
    es el «% del día». No expone importes: solo el reparto porcentual de la
    rentabilidad diaria por valor (``CASH_KEY`` -> efectivo/comisiones).
    """
    if not contrib or denom <= 1e-9:
        return []
    out = [{"ticker": ticker, "pct": round(value / denom * 100, 4)}
           for ticker, value in contrib.items()]
    # Solo se oculta el «ruido» insignificante del efectivo/comisiones
    # (``CASH_KEY``). Una posición real del jugador se mantiene siempre en el
    # desglose, aunque su aportación redondee a 0,00 %: un valor que apenas se
    # movió ese día sigue formando parte de la cartera, y omitirlo daba la falsa
    # impresión de que no se tenía en cuenta.
    out = [d for d in out
           if d["ticker"] != CASH_KEY or abs(d["pct"]) >= 0.005]
    out.sort(key=lambda d: abs(d["pct"]), reverse=True)
    return out


def build_payload(computed: list[tuple[Player, list[DayResult]]],
                  last_days: int = 0,
                  price_days: int = 30,
                  pending: list[dict] | None = None,
                  allocation: dict[str, float] | None = None,
                  holdings: dict[str, dict[str, float]] | None = None,
                  prices: dict[str, list[tuple]] | None = None,
                  analysts: dict[str, dict] | None = None,
                  extended: dict[str, dict] | None = None,
                  news: dict[str, list[dict]] | None = None,
                  contributions: dict[str, dict[date, dict[str, float]]] | None = None,
                  badges: dict | None = None,
                  fx: dict[str, float] | None = None,
                  today: date | None = None,
                  now: datetime | None = None) -> dict:
    """Datos embebidos en la página. Respeta show_amounts por jugador.

    La liga se juega **desde el inicio**: por defecto (``last_days=0``) se
    publica la serie completa de cada jugador, así que la clasificación (con la
    diferencia de cada uno con el primero) y el detalle mensual
    (``players[].months``, la serie diaria resumida mes a mes) cubren toda la
    competición. Los
    campeones del mes actual y del anterior son parciales y se calculan aparte
    (``monthly``), sin recortar esta serie. ``last_days > 0`` recorta a esa
    ventana (útil en pruebas). El ``% acumulado`` de cada día es siempre el de
    siempre (desde el inicio real), y ``since`` guarda la fecha de inicio real
    que se enseña en la ficha de cada jugador.

    ``price_days`` es otra cosa: la ventana de la mini-serie de precios del
    detalle de cada ticker (contexto de mercado del valor, no de la liga).

    ``allocation`` es el valor de mercado agregado por ticker de toda la liga;
    se publica solo como pesos (%) para el widget de cartera de la liga, sin
    importes. ``holdings`` es el mismo valor de mercado por ticker pero
    desglosado por jugador (``{id: {ticker: valor}}``): se publica también solo
    como pesos (%) para la sección «Carteras», que muestra el reparto de cada
    jugador sin revelar importes.

    ``goal`` es el objetivo de la liga (importe y cuenta atrás al próximo 1 de
    agosto), y cada jugador que lo publica (``show_goal``) lleva su propio
    avance en ``players[].goal``; ver :func:`_goal_progress`. ``fx`` es el
    cambio a euros por divisa (:mod:`trader.fx`), que hace falta porque el
    objetivo está en euros y las carteras se valoran en la divisa del extracto.

    ``extended`` es la cotización fuera de horario por ticker (pre-market /
    after-hours, ver :mod:`trader.extended`): precios públicos de mercado, foto
    del momento del build, que alimentan la tarjeta de sesión extendida del
    dashboard y el detalle de cada valor.

    ``news`` son los titulares por ticker (:mod:`trader.news`) de los valores
    que tienen los participantes: viajan con su valor y la ficha de cada
    jugador reúne los de su cartera. Son enlaces y titulares públicos, así que
    no revelan nada de nadie.

    ``treatScale`` es la escala del restaurante que paga el ganador del mes
    (:data:`TREAT_TIERS`), con el precio orientativo y los ejemplos de Madrid de
    cada peldaño; cada mes de ``monthly`` lleva su ``treat`` (el índice que le
    toca).
    """
    today = today or date.today()
    now = now or datetime.now(timezone.utc)
    holdings = holdings or {}
    analysts = analysts or {}
    extended = extended or {}
    contributions = contributions or {}
    computed = _drop_weekends(computed)
    players = []
    # Slot de color por orden alfabético de id: estable aunque cambie el ranking
    order = {p.player_id: i for i, p in enumerate(
        sorted((p for p, _ in computed), key=lambda p: p.player_id))}
    names = {p.player_id: p.display_name for p, _ in computed}
    for player, series in computed:
        if not series:
            continue
        window = series[-last_days:] if last_days else series
        player_contrib = contributions.get(player.player_id, {})
        days = []
        for row in window:
            day = {
                "date": row.day.isoformat(),
                "day": round(row.daily_return * 100, 4),
                "cum": round(row.cumulative_return * 100, 4),
            }
            breakdown = _day_breakdown(player_contrib.get(row.day),
                                       row.start_value + row.external_flow / 2.0)
            if breakdown:
                day["bd"] = breakdown
            if player.show_amounts:
                day.update({
                    "start": round(row.start_value, 2),
                    "end": round(row.end_value, 2),
                    "flow": round(row.external_flow, 2),
                    "pnl": round(row.pnl, 2),
                })
            days.append(day)
        holdings_w = _allocation_weights(holdings.get(player.player_id))
        entry = {
            "id": player.player_id,
            "name": player.display_name,
            "slot": order[player.player_id],
            "amounts": player.show_amounts,
            "since": series[0].day.isoformat(),
            "days": days,
            "months": _player_months(window),
            "holdings": holdings_w,
        }
        suggestion = _buy_sell_suggestion(holdings_w, analysts)
        if suggestion:
            entry["suggestion"] = suggestion
        goal = _goal_progress(player, window, fx)
        if goal:
            entry["goal"] = goal
        players.append(entry)
    deadline = _goal_deadline(today)
    # El cambio aplicado es de la liga, no de cada jugador: es un precio de
    # mercado público, así que se publica aunque nadie enseñe su avance (si
    # colgara de los jugadores, con todos en privado desaparecería de la web
    # justo el dato que explica cómo se cuenta el objetivo).
    goal_fx = {currency: round(rate, 6)
               for currency, rate in sorted((fx or {}).items())
               if currency != "EUR"
               and currency in {(p.currency or "EUR").upper() for p, _ in computed}}
    return {"players": players, "pending": pending or [],
            "goal": {"target": DEFAULT_GOAL,
                     "deadline": deadline.isoformat(),
                     "days": (deadline - today).days,
                     "fx": goal_fx},
            "operations": _recent_operations(computed, order),
            "allocation": _allocation_weights(allocation),
            "market": _market_snapshot(allocation, extended,
                                       int(now.timestamp())),
            "tickers": _ticker_details(allocation, holdings, order, names,
                                       prices, price_days, analysts, extended,
                                       news),
            "monthly": _monthly_bests(computed, today, order),
            # Escala del restaurante: viaja entera (con sus precios y sus
            # ejemplos de Madrid) para que la página pinte la tabla de la
            # leyenda sin repetir el baremo en el cliente.
            "treatScale": TREAT_TIERS,
            "dailyWinners": {
                "month": today.month,
                "month_year": today.year,
                "rows": _daily_winners(computed, today.year, today.month, order),
            },
            "badges": badges or {}}


def _updated_stamp(today: date | None) -> str:
    """Sello de «actualizado» con fecha y hora (zona de Madrid, si está).

    El build corre en UTC (GitHub Actions); mostramos la hora de Madrid para
    la liga, con respaldo a UTC si no hay base de datos de zonas horaria. Si se
    pasa ``today`` (builds reproducibles) se respeta esa fecha y se le añade la
    hora actual.
    """
    tz = None
    try:  # zoneinfo necesita tzdata; si falta, caemos a UTC
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("Europe/Madrid")
    except Exception:
        tz = timezone.utc
    now = datetime.now(tz)
    day = today or now.date()
    return f"{day.isoformat()} {now:%H:%M}"


def write_index(
    computed: list[tuple[Player, list[DayResult]]],
    out_path: str = "docs/index.html",
    today: date | None = None,
    last_days: int = 0,
    price_days: int = 30,
    pending: list[dict] | None = None,
    allocation: dict[str, float] | None = None,
    holdings: dict[str, dict[str, float]] | None = None,
    prices: dict[str, list[tuple]] | None = None,
    analysts: dict[str, dict] | None = None,
    extended: dict[str, dict] | None = None,
    news: dict[str, list[dict]] | None = None,
    contributions: dict[str, dict[date, dict[str, float]]] | None = None,
    badges: dict | None = None,
    fx: dict[str, float] | None = None,
) -> str:
    payload = json.dumps(
        build_payload(computed, last_days=last_days, price_days=price_days,
                      pending=pending,
                      allocation=allocation, holdings=holdings,
                      prices=prices, analysts=analysts, extended=extended,
                      news=news,
                      contributions=contributions, badges=badges, fx=fx,
                      today=today or date.today()),
        ensure_ascii=False)
    payload = payload.replace("</", "<\\/")  # nunca cerrar el <script> desde los datos
    html = (_TEMPLATE
            .replace("__UPDATED__", _updated_stamp(today))
            .replace("__DATA__", payload))
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(html)
    return out_path
