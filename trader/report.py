"""Generación de informes: JSON por jugador y ranking en Markdown."""

from __future__ import annotations

import json
import os
from datetime import date

from .players import Player
from .portfolio import DayResult


def _pct(value: float) -> str:
    return f"{value * 100:+.2f}%"


def _money(value: float, currency: str) -> str:
    symbol = {"USD": "$", "EUR": "€", "GBP": "£"}.get(currency, currency + " ")
    return f"{symbol}{value:,.2f}"


def player_public_data(player: Player, series: list[DayResult]) -> dict:
    """Datos que se publican en claro. Si show_amounts es False, solo %."""
    days = []
    for row in series:
        entry = {
            "date": row.day.isoformat(),
            "daily_return_pct": round(row.daily_return * 100, 4),
            "cumulative_return_pct": round(row.cumulative_return * 100, 4),
        }
        if player.show_amounts:
            entry.update({
                "start_value": round(row.start_value, 2),
                "end_value": round(row.end_value, 2),
                "external_flow": round(row.external_flow, 2),
                "pnl": round(row.pnl, 2),
            })
        days.append(entry)
    return {
        "player": player.player_id,
        "display_name": player.display_name,
        "currency": player.currency,
        "show_amounts": player.show_amounts,
        "days": days,
    }


def write_player_json(player: Player, series: list[DayResult], out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{player.player_id}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(player_public_data(player, series), fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    return path


def player_daily_table(player: Player, series: list[DayResult], last_n: int = 14) -> str:
    """Tabla Markdown con los últimos días del jugador."""
    lines = []
    if player.show_amounts:
        lines.append("| Fecha | Inicio | Fin | Flujo ext. | P&L día | % día | % acumulado |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|")
        for row in series[-last_n:]:
            lines.append(
                f"| {row.day.isoformat()} | {_money(row.start_value, player.currency)} "
                f"| {_money(row.end_value, player.currency)} "
                f"| {_money(row.external_flow, player.currency)} "
                f"| {_money(row.pnl, player.currency)} "
                f"| {_pct(row.daily_return)} | {_pct(row.cumulative_return)} |"
            )
    else:
        lines.append("| Fecha | % día | % acumulado |")
        lines.append("|---|---:|---:|")
        for row in series[-last_n:]:
            lines.append(
                f"| {row.day.isoformat()} | {_pct(row.daily_return)} | {_pct(row.cumulative_return)} |"
            )
    return "\n".join(lines)


def daily_winners(
    computed: list[tuple[Player, list[DayResult]]],
    year: int,
    month: int,
) -> list[tuple[date, list[str], float]]:
    """Ganador de cada día del mes indicado.

    Para cada fecha con datos dentro de ``year``/``month`` devuelve el jugador
    (o jugadores, en caso de empate) con mayor rentabilidad del día, junto con
    ese porcentaje. La lista sale ordenada por fecha ascendente.
    """
    by_day: dict[date, list[tuple[str, float]]] = {}
    for player, series in computed:
        for row in series:
            if row.day.year == year and row.day.month == month:
                by_day.setdefault(row.day, []).append(
                    (player.display_name, row.daily_return)
                )

    winners = []
    for day in sorted(by_day):
        best = max(ret for _name, ret in by_day[day])
        names = [name for name, ret in by_day[day] if ret == best]
        winners.append((day, names, best))
    return winners


def daily_winners_table(
    computed: list[tuple[Player, list[DayResult]]],
    year: int,
    month: int,
) -> str:
    """Tabla Markdown con el ganador de cada día del mes indicado."""
    lines = [
        "| Fecha | Ganador | % del día |",
        "|---|---|---:|",
    ]
    winners = daily_winners(computed, year, month)
    if not winners:
        lines.append("| — | _todavía no hay datos este mes_ | |")
        return "\n".join(lines)
    for day, names, best in winners:
        lines.append(
            f"| {day.isoformat()} | 🏅 {', '.join(names)} | {_pct(best)} |"
        )
    return "\n".join(lines)


def write_ranking(
    computed: list[tuple[Player, list[DayResult]]],
    out_path: str = "docs/ranking.md",
    today: date | None = None,
) -> str:
    """Ranking global ordenado por rentabilidad acumulada."""
    today = today or date.today()
    scored = []
    for player, series in computed:
        if not series:
            continue
        last = series[-1]
        scored.append((player, series, last))
    scored.sort(key=lambda item: item[2].cumulative_return, reverse=True)

    medals = ["🥇", "🥈", "🥉"]
    lines = [
        "# 🏆 Ranking de rentabilidad",
        "",
        f"_Actualizado: {today.isoformat()}_",
        "",
        "| # | Jugador | % acumulado | % último día | Desde |",
        "|---|---|---:|---:|---|",
    ]
    for idx, (player, series, last) in enumerate(scored):
        medal = medals[idx] if idx < len(medals) else str(idx + 1)
        lines.append(
            f"| {medal} | {player.display_name} | **{_pct(last.cumulative_return)}** "
            f"| {_pct(last.daily_return)} | {series[0].day.isoformat()} |"
        )

    if not scored:
        lines.append("| — | _todavía no hay jugadores con datos_ | | | |")

    meses = [
        "", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
        "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    ]
    lines += [
        "",
        f"## 🏅 Ganador de cada día ({meses[today.month]} {today.year})",
        "",
        daily_winners_table(computed, today.year, today.month),
    ]

    for player, series, _last in scored:
        lines += [
            "",
            f"## {player.display_name}",
            "",
            player_daily_table(player, series),
        ]
        if player.warnings:
            lines += ["", "> [!WARNING]"]
            lines += [f"> {w}" for w in player.warnings]

    lines += [
        "",
        "---",
        "_Rentabilidad diaria calculada con Dietz simple (los ingresos y retiradas",
        "de efectivo no cuentan como ganancia). Acumulado = composición geométrica",
        "de las rentabilidades diarias (time-weighted return)._",
        "",
    ]

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    content = "\n".join(lines)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return content
