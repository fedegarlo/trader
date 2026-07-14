"""Genera docs/index.html: dashboard estático para GitHub Pages.

Autocontenido (datos embebidos, sin CDNs): tabla de ranking + gráfica de
rentabilidad acumulada por jugador con crosshair y tooltip. El color se
asigna a cada jugador por orden alfabético de id (estable: no cambia si
cambia su posición en el ranking).
"""

from __future__ import annotations

import json
import os
from datetime import date

from .players import Player
from .portfolio import DayResult

_TEMPLATE = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>🏆 Ranking de rentabilidad</title>
<style>
  :root {
    color-scheme: light;
    --page: #f9f9f7; --surface: #fcfcfb;
    --ink: #0b0b0b; --ink-2: #52514e; --muted: #898781;
    --grid: #e1e0d9; --baseline: #c3c2b7; --ring: rgba(11,11,11,0.10);
    --up: #006300; --down: #d03b3b;
    --s1: #2a78d6; --s2: #1baf7a; --s3: #eda100; --s4: #008300;
    --s5: #4a3aa7; --s6: #e34948; --s7: #e87ba4; --s8: #eb6834;
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      color-scheme: dark;
      --page: #0d0d0d; --surface: #1a1a19;
      --ink: #ffffff; --ink-2: #c3c2b7; --muted: #898781;
      --grid: #2c2c2a; --baseline: #383835; --ring: rgba(255,255,255,0.10);
      --up: #0ca30c; --down: #e66767;
      --s1: #3987e5; --s2: #199e70; --s3: #c98500; --s4: #008300;
      --s5: #9085e9; --s6: #e66767; --s7: #d55181; --s8: #d95926;
    }
  }
  :root[data-theme="dark"] {
    color-scheme: dark;
    --page: #0d0d0d; --surface: #1a1a19;
    --ink: #ffffff; --ink-2: #c3c2b7; --muted: #898781;
    --grid: #2c2c2a; --baseline: #383835; --ring: rgba(255,255,255,0.10);
    --up: #0ca30c; --down: #e66767;
    --s1: #3987e5; --s2: #199e70; --s3: #c98500; --s4: #008300;
    --s5: #9085e9; --s6: #e66767; --s7: #d55181; --s8: #d95926;
  }
  * { box-sizing: border-box; margin: 0; }
  body {
    background: var(--page); color: var(--ink);
    font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif;
    padding: 24px 16px 48px;
  }
  main { max-width: 880px; margin: 0 auto; display: grid; gap: 20px; }
  h1 { font-size: 24px; }
  .sub { color: var(--ink-2); font-size: 13px; margin-top: 2px; }
  .card {
    background: var(--surface); border: 1px solid var(--ring);
    border-radius: 12px; padding: 20px;
  }
  .card h2 { font-size: 15px; font-weight: 600; margin-bottom: 12px; }
  table { border-collapse: collapse; width: 100%; }
  th, td { padding: 7px 10px; text-align: right; font-variant-numeric: tabular-nums; }
  th { color: var(--muted); font-size: 12px; font-weight: 500; border-bottom: 1px solid var(--grid); }
  td { border-bottom: 1px solid var(--grid); }
  tr:last-child td { border-bottom: none; }
  th:first-child, td:first-child, th.name, td.name { text-align: left; }
  .key { display: inline-block; width: 14px; height: 3px; border-radius: 2px;
         vertical-align: middle; margin-right: 7px; }
  .pos { color: var(--up); } .neg { color: var(--down); }
  .big { font-weight: 600; }
  .chartwrap { position: relative; }
  svg { display: block; width: 100%; height: auto; }
  .legend { display: flex; flex-wrap: wrap; gap: 6px 16px; margin-top: 10px;
            font-size: 13px; color: var(--ink-2); }
  .legend span { display: inline-flex; align-items: center; }
  .tip {
    position: absolute; pointer-events: none; display: none; z-index: 2;
    background: var(--surface); border: 1px solid var(--ring); border-radius: 8px;
    padding: 8px 10px; font-size: 12.5px; box-shadow: 0 2px 10px rgba(0,0,0,.12);
    min-width: 150px;
  }
  .tip .d { color: var(--muted); margin-bottom: 4px; }
  .tip .row { display: flex; align-items: center; gap: 7px; justify-content: space-between; }
  .tip .row b { font-variant-numeric: tabular-nums; }
  .tip .row .nm { color: var(--ink-2); display: inline-flex; align-items: center; }
  details { border-top: 1px solid var(--grid); }
  details:first-of-type { border-top: none; }
  summary { cursor: pointer; padding: 10px 0; font-weight: 600; font-size: 14px; }
  .overx { overflow-x: auto; }
  footer { color: var(--muted); font-size: 12.5px; max-width: 880px; margin: 24px auto 0; }
</style>
</head>
<body>
<main>
  <header>
    <h1>🏆 Ranking de rentabilidad</h1>
    <p class="sub">Actualizado: __UPDATED__ · competición de trading con Revolut</p>
  </header>

  <section class="card">
    <h2>Clasificación</h2>
    <div class="overx"><table id="ranking"></table></div>
  </section>

  <section class="card">
    <h2>Rentabilidad acumulada (%)</h2>
    <div class="chartwrap">
      <svg id="chart" viewBox="0 0 860 360" role="img"
           aria-label="Evolución de la rentabilidad acumulada por jugador"></svg>
      <div class="tip" id="tip"></div>
    </div>
    <div class="legend" id="legend"></div>
  </section>

  <section class="card">
    <h2>Detalle diario</h2>
    <div id="detail"></div>
  </section>
</main>
<footer>
  Rentabilidad diaria con Dietz simple (ingresos y retiradas no cuentan como
  ganancia); acumulado por composición geométrica (time-weighted return).
  Datos: extractos de Revolut cifrados · precios de cierre de Yahoo Finance.
</footer>
<script>
const DATA = __DATA__;
const SLOTS = ["--s1","--s2","--s3","--s4","--s5","--s6","--s7","--s8"];
const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const colorOf = p => css(SLOTS[p.slot % SLOTS.length]);
const fmtPct = v => (v > 0 ? "+" : "") + v.toFixed(2) + "%";
const fmtDate = iso => { const [y,m,d] = iso.split("-"); return d + "/" + m + "/" + y.slice(2); };

// ---- clasificación (ordenada por acumulado; el color sigue al jugador) ----
const ranked = [...DATA.players].sort((a, b) =>
  b.days[b.days.length-1].cum - a.days[a.days.length-1].cum);
const MEDALS = ["🥇","🥈","🥉"];
{
  const t = document.getElementById("ranking");
  const mk = (tag, cls, text) => { const el = document.createElement(tag);
    if (cls) el.className = cls; if (text !== undefined) el.textContent = text; return el; };
  const head = t.insertRow();
  ["#","Jugador","% acumulado","% último día","Desde"].forEach((h, i) => {
    const th = document.createElement("th");
    th.textContent = h; if (i === 1) th.className = "name"; head.appendChild(th);
  });
  ranked.forEach((p, i) => {
    const last = p.days[p.days.length-1];
    const tr = t.insertRow();
    tr.appendChild(mk("td", "", MEDALS[i] || String(i + 1)));
    const name = mk("td", "name");
    const key = mk("span", "key"); key.style.background = colorOf(p);
    name.appendChild(key); name.appendChild(document.createTextNode(p.name));
    tr.appendChild(name);
    tr.appendChild(mk("td", "big " + (last.cum >= 0 ? "pos" : "neg"), fmtPct(last.cum)));
    tr.appendChild(mk("td", last.day >= 0 ? "pos" : "neg", fmtPct(last.day)));
    tr.appendChild(mk("td", "", p.days[0].date));
  });
}

// ---- gráfica de líneas: % acumulado ----
const svg = document.getElementById("chart");
const NS = "http://www.w3.org/2000/svg";
const W = 860, H = 360, M = {t: 16, r: 64, b: 30, l: 52};
const dates = DATA.players.length
  ? DATA.players.map(p => p.days.map(d => d.date)).flat().filter((v,i,a) => a.indexOf(v) === i).sort()
  : [];
const byDate = {};
DATA.players.forEach(p => { byDate[p.id] = {}; p.days.forEach(d => byDate[p.id][d.date] = d.cum); });

let vmin = 0, vmax = 0;
DATA.players.forEach(p => p.days.forEach(d => {
  vmin = Math.min(vmin, d.cum); vmax = Math.max(vmax, d.cum); }));
if (vmax === vmin) { vmax += 1; vmin -= 1; }
const pad = (vmax - vmin) * 0.1; vmax += pad; vmin -= pad;

const x = i => M.l + (dates.length < 2 ? 0.5 : i / (dates.length - 1)) * (W - M.l - M.r);
const y = v => M.t + (1 - (v - vmin) / (vmax - vmin)) * (H - M.t - M.b);
const el = (tag, attrs) => { const e = document.createElementNS(NS, tag);
  for (const k in attrs) e.setAttribute(k, attrs[k]); return e; };

function niceTicks(lo, hi, n) {
  const span = hi - lo, step0 = span / n, mag = Math.pow(10, Math.floor(Math.log10(step0)));
  const step = [1,2,2.5,5,10].map(m => m * mag).find(s => span / s <= n) || 10 * mag;
  const out = []; for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) out.push(v);
  return out;
}

function draw() {
  while (svg.firstChild) svg.removeChild(svg.firstChild);
  if (!DATA.players.length) {
    const t = el("text", {x: W/2, y: H/2, "text-anchor": "middle", fill: css("--muted"), "font-size": 14});
    t.textContent = "Todavía no hay jugadores con datos";
    svg.appendChild(t); return;
  }
  // rejilla + eje Y
  niceTicks(vmin, vmax, 6).forEach(v => {
    const isZero = Math.abs(v) < 1e-9;
    svg.appendChild(el("line", {x1: M.l, x2: W - M.r, y1: y(v), y2: y(v),
      stroke: isZero ? css("--baseline") : css("--grid"), "stroke-width": 1}));
    const t = el("text", {x: M.l - 8, y: y(v) + 4, "text-anchor": "end",
      fill: css("--muted"), "font-size": 11.5, style: "font-variant-numeric:tabular-nums"});
    t.textContent = (v > 0 ? "+" : "") + v.toFixed(Math.abs(v) < 10 && v % 1 ? 1 : 0) + "%";
    svg.appendChild(t);
  });
  // eje X: ~6 fechas
  const stepX = Math.max(1, Math.round(dates.length / 6));
  dates.forEach((d, i) => {
    const isLast = i === dates.length - 1;
    // el último siempre; los intermedios solo si no se pegan al último
    if (!isLast && (i % stepX !== 0 || dates.length - 1 - i < stepX * 0.6)) return;
    const t = el("text", {x: x(i), y: H - 8, "text-anchor": "middle",
      fill: css("--muted"), "font-size": 11.5});
    t.textContent = fmtDate(d);
    svg.appendChild(t);
  });
  // líneas + punto final
  DATA.players.forEach(p => {
    const c = colorOf(p);
    const pts = dates.map((d, i) => byDate[p.id][d] === undefined ? null : [x(i), y(byDate[p.id][d])])
      .filter(Boolean);
    svg.appendChild(el("path", {
      d: pts.map((pt, i) => (i ? "L" : "M") + pt[0].toFixed(1) + " " + pt[1].toFixed(1)).join(""),
      fill: "none", stroke: c, "stroke-width": 2,
      "stroke-linejoin": "round", "stroke-linecap": "round"}));
    const end = pts[pts.length - 1];
    svg.appendChild(el("circle", {cx: end[0], cy: end[1], r: 4, fill: c,
      stroke: css("--surface"), "stroke-width": 2}));
  });
  // etiquetas directas al final (solo si no chocan; la leyenda siempre está)
  if (DATA.players.length <= 4) {
    const ends = DATA.players.map(p => {
      const lastDate = p.days[p.days.length-1].date;
      return {v: p.days[p.days.length-1].cum, yy: y(byDate[p.id][lastDate])};
    }).sort((a, b) => a.yy - b.yy);
    const collide = ends.some((e, i) => i && e.yy - ends[i-1].yy < 14);
    if (!collide) ends.forEach(e => {
      const t = el("text", {x: W - M.r + 4, y: e.yy + 4, fill: css("--ink-2"),
        "font-size": 11.5, style: "font-variant-numeric:tabular-nums"});
      t.textContent = fmtPct(e.v);
      svg.appendChild(t);
    });
  }
  // capa de crosshair
  svg.appendChild(el("line", {id: "xhair", x1: 0, x2: 0, y1: M.t, y2: H - M.b,
    stroke: css("--baseline"), "stroke-width": 1, visibility: "hidden"}));
}
draw();
const mq = window.matchMedia("(prefers-color-scheme: dark)");
if (mq.addEventListener) mq.addEventListener("change", draw);

// ---- leyenda ----
{
  const lg = document.getElementById("legend");
  if (DATA.players.length >= 2) DATA.players.forEach(p => {
    const s = document.createElement("span");
    const key = document.createElement("span");
    key.className = "key"; key.style.background = colorOf(p);
    s.appendChild(key); s.appendChild(document.createTextNode(p.name));
    lg.appendChild(s);
  });
}

// ---- tooltip con crosshair ----
const tip = document.getElementById("tip");
const wrap = document.querySelector(".chartwrap");
function onMove(ev) {
  if (!DATA.players.length) return;
  const rect = svg.getBoundingClientRect();
  const px = (ev.clientX - rect.left) * (W / rect.width);
  const frac = (px - M.l) / (W - M.l - M.r);
  const idx = Math.max(0, Math.min(dates.length - 1, Math.round(frac * (dates.length - 1))));
  const d = dates[idx];
  const xh = svg.querySelector("#xhair");
  xh.setAttribute("x1", x(idx)); xh.setAttribute("x2", x(idx));
  xh.setAttribute("visibility", "visible");

  while (tip.firstChild) tip.removeChild(tip.firstChild);
  const head = document.createElement("div"); head.className = "d";
  head.textContent = fmtDate(d); tip.appendChild(head);
  [...DATA.players].sort((a, b) => (byDate[b.id][d] ?? -1e9) - (byDate[a.id][d] ?? -1e9))
    .forEach(p => {
      const v = byDate[p.id][d];
      if (v === undefined) return;
      const row = document.createElement("div"); row.className = "row";
      const nm = document.createElement("span"); nm.className = "nm";
      const key = document.createElement("span"); key.className = "key";
      key.style.background = colorOf(p);
      nm.appendChild(key); nm.appendChild(document.createTextNode(p.name));
      const val = document.createElement("b"); val.textContent = fmtPct(v);
      row.appendChild(nm); row.appendChild(val); tip.appendChild(row);
    });
  tip.style.display = "block";
  const wr = wrap.getBoundingClientRect();
  const tx = (x(idx) / W) * wr.width;
  tip.style.left = Math.min(tx + 14, wr.width - tip.offsetWidth - 4) + "px";
  tip.style.top = Math.max(0, ev.clientY - wr.top - tip.offsetHeight - 12) + "px";
}
svg.addEventListener("pointermove", onMove);
svg.addEventListener("pointerleave", () => {
  tip.style.display = "none";
  const xh = svg.querySelector("#xhair");
  if (xh) xh.setAttribute("visibility", "hidden");
});

// ---- detalle diario (vista de tabla: los valores nunca dependen del hover) ----
{
  const box = document.getElementById("detail");
  ranked.forEach(p => {
    const det = document.createElement("details");
    const sum = document.createElement("summary");
    const key = document.createElement("span"); key.className = "key";
    key.style.background = colorOf(p);
    sum.appendChild(key); sum.appendChild(document.createTextNode(p.name));
    det.appendChild(sum);
    const over = document.createElement("div"); over.className = "overx";
    const t = document.createElement("table");
    const cols = p.amounts
      ? ["Fecha","Inicio","Fin","Flujo ext.","P&L día","% día","% acumulado"]
      : ["Fecha","% día","% acumulado"];
    const head = t.insertRow();
    cols.forEach(c => { const th = document.createElement("th"); th.textContent = c; head.appendChild(th); });
    const money = v => "$" + v.toLocaleString("en-US", {minimumFractionDigits: 2, maximumFractionDigits: 2});
    [...p.days].reverse().forEach(dy => {
      const tr = t.insertRow();
      const cells = p.amounts
        ? [dy.date, money(dy.start), money(dy.end), money(dy.flow), money(dy.pnl), fmtPct(dy.day), fmtPct(dy.cum)]
        : [dy.date, fmtPct(dy.day), fmtPct(dy.cum)];
      cells.forEach((c, i) => {
        const td = tr.insertCell(); td.textContent = c;
        const isPct = i >= cells.length - 2;
        if (isPct) td.className = c.startsWith("+") ? "pos" : (c.startsWith("-") ? "neg" : "");
      });
    });
    over.appendChild(t); det.appendChild(over); box.appendChild(det);
  });
  if (!ranked.length) box.textContent = "Todavía no hay jugadores con datos.";
}
</script>
</body>
</html>
"""


def build_payload(computed: list[tuple[Player, list[DayResult]]]) -> dict:
    """Datos embebidos en la página. Respeta show_amounts por jugador."""
    players = []
    # Slot de color por orden alfabético de id: estable aunque cambie el ranking
    order = {p.player_id: i for i, p in enumerate(
        sorted((p for p, _ in computed), key=lambda p: p.player_id))}
    for player, series in computed:
        if not series:
            continue
        days = []
        for row in series:
            day = {
                "date": row.day.isoformat(),
                "day": round(row.daily_return * 100, 4),
                "cum": round(row.cumulative_return * 100, 4),
            }
            if player.show_amounts:
                day.update({
                    "start": round(row.start_value, 2),
                    "end": round(row.end_value, 2),
                    "flow": round(row.external_flow, 2),
                    "pnl": round(row.pnl, 2),
                })
            days.append(day)
        players.append({
            "id": player.player_id,
            "name": player.display_name,
            "slot": order[player.player_id],
            "amounts": player.show_amounts,
            "days": days,
        })
    return {"players": players}


def write_index(
    computed: list[tuple[Player, list[DayResult]]],
    out_path: str = "docs/index.html",
    today: date | None = None,
) -> str:
    payload = json.dumps(build_payload(computed), ensure_ascii=False)
    payload = payload.replace("</", "<\\/")  # nunca cerrar el <script> desde los datos
    html = (_TEMPLATE
            .replace("__UPDATED__", (today or date.today()).isoformat())
            .replace("__DATA__", payload))
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(html)
    return out_path
