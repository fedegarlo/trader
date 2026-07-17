"""Genera docs/index.html: dashboard estático para GitHub Pages.

Autocontenido (datos embebidos, sin CDNs): tarjetas tipo widget al estilo
Revolut (fondo aurora, gráficas de área con degradado, tipografía compacta),
tabla de ranking + gráfica de rentabilidad acumulada por jugador con crosshair
y tooltip. El color se asigna a cada jugador por orden alfabético de id
(estable: no cambia si cambia su posición en el ranking).
"""

from __future__ import annotations

import json
import os
from datetime import date

from .players import Player
from .portfolio import DayResult

# La competición oficial empezó este día: los días anteriores (pruebas o
# histórico previo) no cuentan. Todos los jugadores se comparan desde esta
# fecha (incluida), rebasando la rentabilidad acumulada al inicio real de la
# competición (ver ``rebase_from`` en portfolio.py), y también acota los
# widgets de «mejor del mes».
COMPETITION_START = date(2026, 7, 14)

_MONTHS_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

_TEMPLATE = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#efeaf8" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#0e0d13" media="(prefers-color-scheme: dark)">
<title>🏆 Liga Trader</title>
<style>
  :root {
    color-scheme: light;
    --ink: #0b0a10; --ink-2: #5b5966; --muted: #918f9d;
    --surface: rgba(255,255,255,0.66);
    --surface-2: rgba(255,255,255,0.42);
    --card-solid: #f6f4fb;
    --grid: rgba(11,10,16,0.08); --baseline: rgba(11,10,16,0.20);
    --ring: rgba(11,10,16,0.07); --hair: rgba(11,10,16,0.06);
    --accent: #1f6bff;
    --up: #1667e0; --down: #d61f8f;
    --up-soft: rgba(22,103,224,0.14); --down-soft: rgba(214,31,143,0.14);
    --s1: #2a78d6; --s2: #1baf7a; --s3: #eda100; --s4: #008300;
    --s5: #4a3aa7; --s6: #e34948; --s7: #8a44cc; --s8: #eb6834;
    --aura-1: #ffe4c2; --aura-2: #dcd4ff; --aura-3: #ffd6ea; --aura-base: #efeaf8;
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      color-scheme: dark;
      --ink: #f6f5fb; --ink-2: #b9b6c6; --muted: #86838f;
      --surface: rgba(30,29,38,0.62);
      --surface-2: rgba(30,29,38,0.40);
      --card-solid: #1b1a22;
      --grid: rgba(255,255,255,0.09); --baseline: rgba(255,255,255,0.22);
      --ring: rgba(255,255,255,0.10); --hair: rgba(255,255,255,0.07);
      --accent: #5b9bff;
      --up: #4d94ff; --down: #ff5cbf;
      --up-soft: rgba(77,148,255,0.18); --down-soft: rgba(255,92,191,0.18);
      --s1: #3987e5; --s2: #199e70; --s3: #c98500; --s4: #008300;
      --s5: #9085e9; --s6: #e66767; --s7: #a86fe0; --s8: #d95926;
      --aura-1: #3a2c55; --aura-2: #232c4d; --aura-3: #4a2740; --aura-base: #0e0d13;
    }
  }
  :root[data-theme="dark"] {
    color-scheme: dark;
    --ink: #f6f5fb; --ink-2: #b9b6c6; --muted: #86838f;
    --surface: rgba(30,29,38,0.62);
    --surface-2: rgba(30,29,38,0.40);
    --card-solid: #1b1a22;
    --grid: rgba(255,255,255,0.09); --baseline: rgba(255,255,255,0.22);
    --ring: rgba(255,255,255,0.10); --hair: rgba(255,255,255,0.07);
    --accent: #5b9bff;
    --up: #4d94ff; --down: #ff5cbf;
    --up-soft: rgba(77,148,255,0.18); --down-soft: rgba(255,92,191,0.18);
    --s1: #3987e5; --s2: #199e70; --s3: #c98500; --s4: #008300;
    --s5: #9085e9; --s6: #e66767; --s7: #a86fe0; --s8: #d95926;
    --aura-1: #3a2c55; --aura-2: #232c4d; --aura-3: #4a2740; --aura-base: #0e0d13;
  }
  * { box-sizing: border-box; margin: 0; }
  html {
    -webkit-text-size-adjust: 100%;
    min-height: 100%;
    background: var(--aura-base);
  }
  body {
    color: var(--ink);
    font: 15px/1.5 -apple-system, BlinkMacSystemFont, "SF Pro Display",
          system-ui, "Segoe UI", Roboto, sans-serif;
    letter-spacing: -0.01em;
    padding:
      calc(20px + env(safe-area-inset-top))
      calc(14px + env(safe-area-inset-right))
      calc(40px + env(safe-area-inset-bottom))
      calc(14px + env(safe-area-inset-left));
    min-height: 100vh;
    min-height: 100dvh;
    background: transparent;
  }
  main { max-width: 760px; margin: 0 auto; display: grid; gap: 12px; }
  main > * { min-width: 0; }

  /* header */
  header { padding: 4px 6px 6px; }
  .eyebrow { color: var(--ink-2); font-size: 13px; font-weight: 600; }
  .hrow { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: 6px; }
  h1 { font-size: clamp(30px, 9vw, 40px); font-weight: 800; letter-spacing: -0.035em; line-height: 1.02; }
  .upload {
    flex: none; text-decoration: none; color: #fff; background: var(--accent);
    width: 46px; height: 46px; border-radius: 999px; display: grid; place-items: center;
    box-shadow: 0 8px 18px -6px color-mix(in srgb, var(--accent) 75%, transparent);
  }
  .upload svg { display: block; }
  .upload:active { transform: translateY(1px); }
  .hbtns { flex: none; display: flex; align-items: center; gap: 10px; }
  .refresh {
    flex: none; border: 0; cursor: pointer; color: var(--accent);
    background: color-mix(in srgb, var(--accent) 14%, transparent);
    width: 46px; height: 46px; border-radius: 999px; display: grid; place-items: center;
  }
  .refresh svg { display: block; }
  .refresh:active { transform: translateY(1px); }
  .refresh.spin svg { animation: spin 0.6s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .hbar { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-top: 14px; }
  .chip { font-weight: 700; font-size: 15px; color: var(--ink); }
  .chip .caret { color: var(--muted); font-size: 12px; }
  .period { font-weight: 700; font-size: 15px; color: var(--accent); }

  /* tarjetas */
  .card {
    background: var(--surface);
    -webkit-backdrop-filter: blur(24px) saturate(150%);
    backdrop-filter: blur(24px) saturate(150%);
    border: 1px solid var(--ring);
    border-radius: 26px; padding: 18px;
    box-shadow: 0 1px 1px rgba(11,10,16,0.03), 0 12px 28px -22px rgba(11,10,16,0.30);
  }
  .card h2 { font-size: 15px; font-weight: 700; letter-spacing: -0.02em; }
  .card.warn { border-color: color-mix(in srgb, var(--s3) 55%, var(--ring)); background: color-mix(in srgb, var(--s3) 10%, var(--surface)); }

  /* widgets */
  .widget { position: relative; overflow: hidden; padding-bottom: 0; }
  .wlabel { color: var(--ink-2); font-size: 14px; font-weight: 600; }
  .wbig { font-size: clamp(26px, 8vw, 34px); font-weight: 800; letter-spacing: -0.035em; line-height: 1.1; margin-top: 3px; display: flex; align-items: baseline; flex-wrap: wrap; gap: 4px 10px; }
  .wbig.sm { font-size: clamp(22px, 6.6vw, 28px); white-space: nowrap; }
  .num { font-variant-numeric: tabular-nums; }
  .delta { font-size: 15px; font-weight: 700; letter-spacing: -0.01em; }
  .live { align-items: center; gap: 6px; margin-top: 8px; font-size: 13px; font-weight: 700; }
  .live .dot { width: 7px; height: 7px; border-radius: 999px; background: currentColor;
               animation: pulse 1.8s ease-out infinite; }
  .live .tag { color: var(--muted); font-weight: 600; font-size: 11.5px; }
  @keyframes pulse {
    0% { box-shadow: 0 0 0 0 color-mix(in srgb, currentColor 55%, transparent); }
    70% { box-shadow: 0 0 0 6px transparent; }
    100% { box-shadow: 0 0 0 0 transparent; }
  }
  .wsub { color: var(--ink-2); font-size: 13.5px; font-weight: 600; margin-top: 4px; }
  .bestname { color: var(--ink); font-size: 18px; font-weight: 700; margin-top: 8px; display: flex; align-items: center; gap: 6px; }
  .bestname .medal { font-size: 20px; line-height: 1; }
  .wsub.muted { color: var(--muted); font-weight: 500; }
  .sparkwrap { margin: 12px -18px 0; height: 116px; }
  .sparkwrap.sm { height: 58px; margin-top: 10px; }
  svg.spark { display: block; width: 100%; height: 100%; }
  .wrow { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .wrow .card { padding-bottom: 18px; display: flex; flex-direction: column; }
  .wrow .card.widget { padding-bottom: 0; }

  /* widget de cartera: gráfico de tarta (cada porción = su peso real) */
  .donut-wrap { display: flex; align-items: center; gap: 18px; margin-top: 16px; }
  .donut { flex: none; display: block; }
  .donut-legend { flex: 1 1 0; min-width: 0; list-style: none;
                  display: flex; flex-direction: column; gap: 9px; }
  .dl { display: flex; align-items: center; gap: 9px; font-size: 13.5px; }
  .dl .dot { width: 10px; height: 10px; border-radius: 3px; flex: none; }
  .dl .tk { font-weight: 700; color: var(--ink); letter-spacing: -0.01em;
            overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .dl .w { margin-left: auto; font-weight: 700; color: var(--ink-2); font-variant-numeric: tabular-nums; }
  .donut-center { fill: var(--ink); font-weight: 800; letter-spacing: -0.02em; }
  .donut-sub { fill: var(--muted); font-weight: 600; }
  .alloc-insight { margin-top: 16px; font-size: 13.5px; font-weight: 700; color: var(--accent); }
  .alloc-insight .muted { color: var(--muted); font-weight: 500; }

  /* carteras por jugador */
  .wallet { border-top: 1px solid var(--hair); padding: 14px 0 4px; }
  .wallet:first-child { border-top: none; padding-top: 4px; }
  .whead { display: flex; align-items: center; gap: 8px; font-weight: 700; font-size: 14px; }
  .whead .top { margin-left: auto; font-size: 12.5px; font-weight: 600; color: var(--muted); font-variant-numeric: tabular-nums; }
  .wallet .donut-wrap { margin-top: 12px; }

  .pos { color: var(--up); } .neg { color: var(--down); }

  /* insights generados por IA */
  .ai-head { display: flex; align-items: center; gap: 9px; }
  .ai-badge {
    font-size: 11px; font-weight: 800; letter-spacing: 0.06em; color: #fff;
    padding: 3px 8px; border-radius: 999px;
    background: linear-gradient(120deg, var(--s7), var(--accent));
    box-shadow: 0 5px 14px -6px color-mix(in srgb, var(--accent) 70%, transparent);
  }
  .ai-title { font-size: 15px; font-weight: 700; letter-spacing: -0.02em; }
  .ai-live { margin-left: auto; display: inline-flex; align-items: center; gap: 6px;
             color: var(--muted); font-size: 11.5px; font-weight: 600; }
  .ai-live .dot { width: 6px; height: 6px; border-radius: 999px; background: var(--s2);
                  animation: pulse 1.8s ease-out infinite; }
  .insights { display: grid; gap: 10px; margin-top: 14px; }
  .insight {
    display: flex; gap: 11px; align-items: flex-start;
    font-size: 14.5px; font-weight: 600; color: var(--ink);
    padding: 12px 13px; border-radius: 16px;
    background: var(--surface-2); border: 1px solid var(--hair);
    transition: opacity 0.45s ease;
  }
  .insight .ic { flex: none; font-size: 17px; line-height: 1.35; }
  .insight .tx { min-width: 0; }
  .insight b { font-weight: 800; letter-spacing: -0.01em; }

  /* tabla ranking */
  table { border-collapse: collapse; width: 100%; }
  th, td { padding: 9px 10px; text-align: right; font-variant-numeric: tabular-nums; }
  th { color: var(--muted); font-size: 12px; font-weight: 600; border-bottom: 1px solid var(--hair); }
  td { border-bottom: 1px solid var(--hair); }
  tr:last-child td { border-bottom: none; }
  th:first-child, td:first-child, th.name, td.name { text-align: left; }
  td.rank { font-weight: 700; font-size: 15px; color: var(--muted); }
  .key { display: inline-block; width: 9px; height: 9px; border-radius: 999px;
         vertical-align: middle; margin-right: 8px; }
  .big { font-weight: 700; }

  /* gráfica multilínea */
  .chartwrap { position: relative; margin-top: 12px; }
  svg#chart { display: block; width: 100%; height: auto; touch-action: pan-y; }
  .legend { display: flex; flex-wrap: wrap; gap: 8px 14px; margin-top: 12px;
            font-size: 13px; font-weight: 600; color: var(--ink-2); }
  .legend span { display: inline-flex; align-items: center; }
  .tip {
    position: absolute; pointer-events: none; display: none; z-index: 2;
    background: var(--card-solid); border: 1px solid var(--ring); border-radius: 14px;
    padding: 9px 11px; font-size: 12.5px; box-shadow: 0 8px 24px -8px rgba(11,10,16,.35);
    min-width: 152px;
  }
  .tip .d { color: var(--muted); margin-bottom: 5px; font-weight: 600; }
  .tip .row { display: flex; align-items: center; gap: 7px; justify-content: space-between; }
  .tip .row b { font-variant-numeric: tabular-nums; font-weight: 700; }
  .tip .row .nm { color: var(--ink-2); display: inline-flex; align-items: center; font-weight: 500; }

  /* detalle */
  details { border-top: 1px solid var(--hair); }
  details:first-of-type { border-top: none; }
  summary { cursor: pointer; padding: 12px 2px; font-weight: 700; font-size: 14px;
            list-style: none; display: flex; align-items: center; }
  summary::-webkit-details-marker { display: none; }
  summary::after { content: "⌄"; margin-left: auto; color: var(--muted); font-size: 16px; transform: translateY(-3px); }
  details[open] summary::after { transform: translateY(1px) rotate(180deg); }
  .overx { overflow-x: auto; -webkit-overflow-scrolling: touch; }
  .overx table { white-space: nowrap; }
  footer { color: var(--muted); font-size: 12.5px; max-width: 760px; margin: 20px auto 0; padding: 0 6px; }

  @media (min-width: 620px) {
    main { gap: 14px; }
    .card { padding: 22px; }
    .sparkwrap { margin: 14px -22px 0; }
  }
</style>
</head>
<body>
<main>
  <header>
    <div class="eyebrow">🏆 Competición · Revolut · actualizado __UPDATED__</div>
    <div class="hrow">
      <h1>Liga Trader</h1>
      <div class="hbtns">
        <button class="refresh" id="refresh-btn" type="button" aria-label="Refrescar ranking" title="Refrescar ranking">
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor"
               stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M21 12a9 9 0 1 1-2.64-6.36"/><path d="M21 3v6h-6"/>
          </svg>
        </button>
        <a class="upload" id="upload-mail" href="mailto:ligatrader26@gmail.com" aria-label="Enviar posiciones" title="Enviar posiciones">
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor"
               stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M12 16V4"/><path d="M7 9l5-5 5 5"/><path d="M5 20h14"/>
          </svg>
        </a>
      </div>
    </div>
    <div class="hbar">
      <span class="chip" id="hchip">Todos los jugadores <span class="caret">▾</span></span>
      <span class="period">Últimos 30 días</span>
    </div>
  </header>

  <section class="card warn" id="pending-card" style="display:none">
    <h2>⏳ Pendiente de clave</h2>
    <div class="wsub" id="pending" style="margin-top:6px"></div>
  </section>

  <div id="widgets" style="display:grid;gap:12px">
    <section class="card widget" id="hero-card">
      <div class="wlabel">Líder · <span id="hero-name"></span></div>
      <div class="wbig"><span class="num" id="hero-val"></span><span class="delta" id="hero-delta"></span></div>
      <div class="live" id="hero-live" style="display:none"></div>
      <div class="sparkwrap" id="hero-spark"></div>
    </section>
    <div class="wrow">
      <section class="card widget" id="best-card">
        <div class="wlabel">Mejor del día</div>
        <div class="wbig"><span class="num" id="best-val"></span></div>
        <div class="bestname" id="best-name"></div>
      </section>
      <section class="card" id="gap-card">
        <div class="wlabel">Diferencia 1º–último</div>
        <div class="wbig sm"><span class="num" id="gap-val"></span></div>
        <div style="margin-top:auto">
          <div class="wsub" id="gap-top"></div>
          <div class="wsub muted" id="gap-bot"></div>
        </div>
      </section>
    </div>
    <div class="wrow" id="month-row" style="display:none">
      <section class="card widget" id="month-cur-card">
        <div class="wlabel">Mejor de este mes · <span id="month-cur-name"></span></div>
        <div class="wbig sm"><span class="num" id="month-cur-val"></span></div>
        <div class="wsub" id="month-cur-player"></div>
        <div class="sparkwrap sm" id="month-cur-spark"></div>
      </section>
      <section class="card widget" id="month-prev-card">
        <div class="wlabel">Mejor del mes pasado · <span id="month-prev-name"></span></div>
        <div class="wbig sm"><span class="num" id="month-prev-val"></span></div>
        <div class="wsub" id="month-prev-player"></div>
        <div class="sparkwrap sm" id="month-prev-spark"></div>
      </section>
    </div>
  </div>

  <section class="card" id="insights-card" style="display:none">
    <div class="ai-head">
      <span class="ai-badge">IA</span>
      <span class="ai-title">Insights de la liga</span>
      <span class="ai-live"><span class="dot"></span>análisis automático</span>
    </div>
    <div class="insights" id="insights"></div>
  </section>

  <section class="card">
    <h2>Clasificación</h2>
    <div class="overx" style="margin-top:6px"><table id="ranking"></table></div>
  </section>

  <section class="card" id="alloc-card" style="display:none">
    <div class="wlabel">Cartera de la liga</div>
    <div id="alloc-bars"></div>
    <div class="alloc-insight" id="alloc-insight"></div>
  </section>

  <section class="card" id="wallets-card" style="display:none">
    <h2>Carteras por jugador</h2>
    <div id="wallets" style="margin-top:4px"></div>
  </section>

  <section class="card">
    <h2>Rentabilidad acumulada · últimos 30 días</h2>
    <div class="chartwrap">
      <svg id="chart" viewBox="0 0 860 360" role="img"
           aria-label="Evolución de la rentabilidad acumulada por jugador"></svg>
      <div class="tip" id="tip"></div>
    </div>
    <div class="legend" id="legend"></div>
  </section>

  <section class="card">
    <h2>Detalle diario · últimos 30 días</h2>
    <div id="detail" style="margin-top:4px"></div>
  </section>
</main>
<footer>
  Rentabilidad diaria con Dietz simple (ingresos y retiradas no cuentan como
  ganancia); acumulado por composición geométrica (time-weighted return).
  Datos: extractos de Revolut cifrados · precios de cierre de Yahoo Finance.
  El indicador «en vivo» valora hoy a precio actual y es provisional: no cuenta
  para la clasificación oficial.
</footer>
<script>
const DATA = __DATA__;
// ---- enlace de envío de posiciones por correo ----
(() => {
  const link = document.getElementById("upload-mail");
  if (!link) return;
  const setHref = () => {
    const now = new Date();
    const p = n => String(n).padStart(2, "0");
    const fecha = p(now.getDate()) + "/" + p(now.getMonth() + 1) + "/" + now.getFullYear()
      + " " + p(now.getHours()) + ":" + p(now.getMinutes());
    const subject = encodeURIComponent(fecha);
    const body = encodeURIComponent("adjunto mis posiciones en formato csv");
    link.href = "mailto:ligatrader26@gmail.com?subject=" + subject + "&body=" + body;
  };
  setHref();
  link.addEventListener("click", setHref);
})();
// ---- refrescar el ranking (recarga la última clasificación publicada) ----
// Actions recalcula solo (al subir un extracto y en el cron diario); aquí basta
// con recargar sin caché para traer esa última versión. Sin token ni permisos.
(() => {
  const btn = document.getElementById("refresh-btn");
  if (!btn) return;
  btn.addEventListener("click", () => {
    btn.classList.add("spin");
    btn.disabled = true;
    location.replace(location.pathname + "?r=" + Date.now());
  });
})();
const SLOTS = ["--s1","--s2","--s3","--s4","--s5","--s6","--s7","--s8"];
const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const colorOf = p => css(SLOTS[p.slot % SLOTS.length]);
const fmtPct = v => (v > 0 ? "+" : "") + v.toFixed(2) + "%";
const fmtDate = iso => { const [y,m,d] = iso.split("-"); return d + "/" + m + "/" + y.slice(2); };
const lastOf = p => p.days[p.days.length - 1];

// ---- clasificación (ordenada por acumulado; el color sigue al jugador) ----
const ranked = [...DATA.players].sort((a, b) => lastOf(b).cum - lastOf(a).cum);
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
    const last = lastOf(p);
    const tr = t.insertRow();
    tr.appendChild(mk("td", "rank", MEDALS[i] || String(i + 1)));
    const name = mk("td", "name");
    const key = mk("span", "key"); key.style.background = colorOf(p);
    name.appendChild(key); name.appendChild(document.createTextNode(p.name));
    tr.appendChild(name);
    tr.appendChild(mk("td", "big " + (last.cum >= 0 ? "pos" : "neg"), fmtPct(last.cum)));
    tr.appendChild(mk("td", last.day >= 0 ? "pos" : "neg", fmtPct(last.day)));
    tr.appendChild(mk("td", "", p.since || p.days[0].date));
  });
}

// ---- pendientes de clave (extracto subido pero no descifrable) ----
if (DATA.pending && DATA.pending.length) {
  const names = DATA.pending.map(p => p.name).join(", ");
  document.getElementById("pending").textContent =
    names + " — su extracto está subido pero no se ha podido descifrar. Seguramente la " +
    "frase de paso no es la de la liga: que lo vuelva a subir con la frase correcta.";
  document.getElementById("pending-card").style.display = "";
}

// ---- widgets tipo Revolut (gráficas de área con degradado) ----
function sparkSVG(values, color, id, opts) {
  const W = 100, H = 40, pad = 3;
  // Con línea base en 0 la magnitud es honesta: una serie casi plana no se
  // estira a toda la altura (evita la falsa «cuesta» con pocos puntos).
  let mn = Math.min(...values), mx = Math.max(...values);
  if (opts && opts.baseline0) { mn = Math.min(0, mn); mx = Math.max(0, mx); }
  if (mx === mn) { mx += 1; mn -= 1; }
  const xs = i => values.length < 2 ? W / 2 : (i / (values.length - 1)) * W;
  const ys = v => pad + (1 - (v - mn) / (mx - mn)) * (H - 2 * pad);
  const line = values.map((v, i) => (i ? "L" : "M") + xs(i).toFixed(2) + " " + ys(v).toFixed(2)).join(" ");
  const area = "M" + xs(0).toFixed(2) + " " + H + " " +
    values.map((v, i) => "L" + xs(i).toFixed(2) + " " + ys(v).toFixed(2)).join(" ") +
    " L" + xs(values.length - 1).toFixed(2) + " " + H + " Z";
  return '<svg class="spark" viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="none" aria-hidden="true">' +
    '<defs><linearGradient id="sg' + id + '" x1="0" y1="0" x2="0" y2="1">' +
    '<stop offset="0" stop-color="' + color + '" stop-opacity="0.34"/>' +
    '<stop offset="1" stop-color="' + color + '" stop-opacity="0"/>' +
    '</linearGradient></defs>' +
    '<path d="' + area + '" fill="url(#sg' + id + ')"/>' +
    '<path d="' + line + '" fill="none" stroke="' + color + '" stroke-width="2.4" ' +
    'vector-effect="non-scaling-stroke" stroke-linejoin="round" stroke-linecap="round"/>' +
    '</svg>';
}
function paintWidgets() {
  if (!DATA.players.length) { document.getElementById("widgets").style.display = "none"; return; }
  const upC = css("--up"), downC = css("--down");
  // héroe: líder
  const leader = ranked[0], lc = lastOf(leader);
  document.getElementById("hero-name").textContent = leader.name;
  const hv = document.getElementById("hero-val");
  hv.textContent = fmtPct(lc.cum); hv.className = "num " + (lc.cum >= 0 ? "pos" : "neg");
  const hd = document.getElementById("hero-delta");
  hd.textContent = (lc.day >= 0 ? "▲ " : "▼ ") + fmtPct(lc.day);
  hd.className = "delta " + (lc.day >= 0 ? "pos" : "neg");
  const hl = document.getElementById("hero-live");
  if (leader.live) {
    hl.style.display = "inline-flex";
    hl.className = "live " + (leader.live.cum >= 0 ? "pos" : "neg");
    hl.innerHTML = '<span class="dot"></span>en vivo ' + fmtPct(leader.live.cum) +
      ' <span class="tag">provisional</span>';
  } else {
    hl.style.display = "none";
  }
  document.getElementById("hero-spark").innerHTML =
    sparkSVG(leader.days.map(d => d.cum), lc.cum >= 0 ? upC : downC, "hero", {baseline0: true});

  // mejor del día
  const best = [...DATA.players].sort((a, b) => lastOf(b).day - lastOf(a).day)[0];
  const bd = lastOf(best);
  const bv = document.getElementById("best-val");
  bv.textContent = fmtPct(bd.day); bv.className = "num " + (bd.day >= 0 ? "pos" : "neg");
  const bn = document.getElementById("best-name");
  bn.innerHTML = '<span class="medal">🥇</span>';
  bn.appendChild(document.createTextNode(best.name));

  // diferencia 1º - último
  const gapCard = document.getElementById("gap-card");
  if (ranked.length < 2) {
    gapCard.style.display = "none";
    document.querySelector(".wrow").style.gridTemplateColumns = "1fr";
    return;
  }
  const last = ranked[ranked.length - 1];
  const gap = lastOf(ranked[0]).cum - lastOf(last).cum;
  document.getElementById("gap-val").textContent = "+" + gap.toFixed(2) + "\\u00a0pp";
  document.getElementById("gap-top").textContent = "🥇 " + ranked[0].name + " · " + fmtPct(lastOf(ranked[0]).cum);
  document.getElementById("gap-bot").textContent = last.name + " · " + fmtPct(lastOf(last).cum);
}
paintWidgets();

// ---- widgets «mejor del mes»: este mes y el mes pasado (si hay datos) ----
function paintMonthly() {
  const m = DATA.monthly || {};
  const upC = css("--up"), downC = css("--down");
  const cap = s => s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
  const paint = (info, key, spark0) => {
    const card = document.getElementById(key + "-card");
    if (!info) { card.style.display = "none"; return false; }
    card.style.display = "";
    document.getElementById(key + "-name").textContent =
      cap(info.month_name) + " " + info.month_year;
    const val = document.getElementById(key + "-val");
    val.textContent = fmtPct(info.value);
    val.className = "num " + (info.value >= 0 ? "pos" : "neg");
    document.getElementById(key + "-player").textContent = info.name;
    document.getElementById(key + "-spark").innerHTML =
      sparkSVG(info.spark, info.value >= 0 ? upC : downC, spark0, {baseline0: true});
    return true;
  };
  const hasCur = paint(m.current, "month-cur", "mcur");
  const hasPrev = paint(m.previous, "month-prev", "mprev");
  const row = document.getElementById("month-row");
  if (!hasCur && !hasPrev) { row.style.display = "none"; return; }
  row.style.display = "grid";
  row.style.gridTemplateColumns = (hasCur && hasPrev) ? "1fr 1fr" : "1fr";
}
paintMonthly();

// ---- widgets de cartera: asignación por ticker (solo pesos, sin importes) ----
function badgeColor(t) {
  let h = 0; for (let i = 0; i < t.length; i++) h = (h * 31 + t.charCodeAt(i)) >>> 0;
  return "hsl(" + (h % 360) + " 58% 52%)";
}
const fmtW = w => w.toFixed(w < 10 ? 1 : 0) + "%";
// Agrupa la cola en «Otros» cuando hay más de 6 posiciones (misma regla que
// usa la cartera de la liga), para que las barras no se aprieten.
function allocItems(all) {
  if (all.length <= 6) return all;
  const rest = all.slice(5).reduce((s, x) => s + x.w, 0);
  return all.slice(0, 5).concat([{ticker: "Otros", w: Math.round(rest * 100) / 100, other: true}]);
}
// Gráfico de tarta (donut): el ángulo de cada porción es su peso real en la
// cartera, así que la superficie refleja el % verdadero (no relativo al mayor,
// como hacían las barras). Se dibuja con arcos de una circunferencia via
// stroke-dasharray; un hueco de 2px separa las porciones. En el centro, el
// número de posiciones. ``count`` es el total real de tickers (antes de
// agrupar la cola en «Otros»), no el número de porciones.
function donutSVG(items, count, size) {
  const S = size || 132, sw = S < 120 ? 16 : 20;
  const cx = S / 2, cy = S / 2, r = (S - sw) / 2 - 1, C = 2 * Math.PI * r;
  const drawn = items.filter(x => x.w > 0);
  const gap = drawn.length > 1 ? 2 : 0;
  let acc = 0;
  const segs = drawn.map(x => {
    const col = x.other ? css("--muted") : badgeColor(x.ticker);
    const frac = x.w / 100;
    const len = Math.max(0.5, frac * C - gap);
    const dash = len.toFixed(2) + " " + (C - len).toFixed(2);
    const off = (-acc * C).toFixed(2);
    acc += frac;
    return '<circle cx="' + cx + '" cy="' + cy + '" r="' + r.toFixed(2) +
      '" fill="none" stroke="' + col + '" stroke-width="' + sw +
      '" stroke-dasharray="' + dash + '" stroke-dashoffset="' + off + '">' +
      '<title>' + x.ticker + ' · ' + fmtW(x.w) + '</title></circle>';
  }).join("");
  const big = S < 120 ? 20 : 24;
  const center = count
    ? '<text x="' + cx + '" y="' + (cy - 1) + '" text-anchor="middle" class="donut-center" ' +
        'font-size="' + big + '">' + count + '</text>' +
      '<text x="' + cx + '" y="' + (cy + 14) + '" text-anchor="middle" class="donut-sub" ' +
        'font-size="10.5">' + (count === 1 ? "activo" : "activos") + '</text>'
    : "";
  return '<svg class="donut" width="' + S + '" height="' + S + '" viewBox="0 0 ' + S + ' ' + S +
    '" role="img" aria-label="Reparto de la cartera por peso">' +
    '<g transform="rotate(-90 ' + cx + ' ' + cy + ')">' + segs + '</g>' + center + '</svg>';
}
function donutLegendHTML(items) {
  return '<ul class="donut-legend">' + items.map(x => {
    const col = x.other ? css("--muted") : badgeColor(x.ticker);
    return '<li class="dl"><span class="dot" style="background:' + col + '"></span>' +
      '<span class="tk">' + x.ticker + '</span><span class="w">' + fmtW(x.w) + '</span></li>';
  }).join("") + '</ul>';
}
// Tarta + leyenda. ``all`` es la lista completa de posiciones (peso ya en %);
// se agrupa la cola en «Otros» para no fragmentar la tarta, pero el contador
// central refleja el número real de activos.
function donutHTML(all, size) {
  const items = allocItems(all);
  return '<div class="donut-wrap">' + donutSVG(items, all.length, size) +
    donutLegendHTML(items) + '</div>';
}
function paintAllocation() {
  const all = DATA.allocation || [];
  const card = document.getElementById("alloc-card");
  if (!all.length) { card.style.display = "none"; return; }
  card.style.display = "";
  document.getElementById("alloc-bars").innerHTML = donutHTML(all);
  const top = all[0];
  document.getElementById("alloc-insight").innerHTML =
    "📊 Mayor posición · " + top.ticker +
    ' <span class="muted">· ' + fmtW(top.w) + " del total</span>";
}
paintAllocation();

// ---- carteras por jugador: reparto por ticker de cada uno (solo pesos) ----
function paintWallets() {
  const withHoldings = ranked.filter(p => p.holdings && p.holdings.length);
  const card = document.getElementById("wallets-card");
  if (!withHoldings.length) { card.style.display = "none"; return; }
  card.style.display = "";
  const box = document.getElementById("wallets");
  box.innerHTML = "";
  withHoldings.forEach(p => {
    const wrap = document.createElement("div"); wrap.className = "wallet";
    const head = document.createElement("div"); head.className = "whead";
    const key = document.createElement("span"); key.className = "key";
    key.style.background = colorOf(p);
    head.appendChild(key); head.appendChild(document.createTextNode(p.name));
    const top = document.createElement("span"); top.className = "top";
    top.textContent = "Mayor · " + p.holdings[0].ticker + " " + fmtW(p.holdings[0].w);
    head.appendChild(top);
    const chart = document.createElement("div");
    chart.innerHTML = donutHTML(p.holdings, 108);
    wrap.appendChild(head); wrap.appendChild(chart.firstChild);
    box.appendChild(wrap);
  });
}
paintWallets();

// ---- insights «IA»: 30+ plantillas con hueco para el/los jugador(es) ----
// Cada plantilla lleva su condición y solo se muestra «según corresponda»
// (ranking, % del día/acumulado, rachas, carteras). De todas las aplicables se
// pintan tres y van rotando, para que la lectura parezca un análisis vivo.
function computeInsights() {
  const ps = DATA.players.filter(p => p.days && p.days.length);
  if (!ps.length) return [];
  const NBSP = String.fromCharCode(160);
  const lastp = p => p.days[p.days.length - 1];
  const ranked = [...ps].sort((a, b) => lastp(b).cum - lastp(a).cum);
  const byDay = [...ps].sort((a, b) => lastp(b).day - lastp(a).day);
  const n = ps.length;
  const leader = ranked[0], second = ranked[1], tail = ranked[n - 1];
  const bestDay = byDay[0], worstDay = byDay[n - 1];
  const who = p => '<b style="color:' + colorOf(p) + '">' + p.name + '</b>';
  const pts = v => Math.abs(v).toFixed(2) + NBSP + "puntos";
  const streak = (p, positive) => { let c = 0; for (let i = p.days.length - 1; i >= 0; i--) {
    const d = p.days[i].day; if (positive ? d > 0 : d < 0) c++; else break; } return c; };
  const greenCount = (p, k) => p.days.slice(-k).filter(d => d.day > 0).length;
  const windowDelta = p => lastp(p).cum - p.days[0].cum;
  const range = p => { const c = p.days.map(d => d.cum); return Math.max(...c) - Math.min(...c); };
  const recovered = p => p.days.length >= 2 &&
    lastp(p).day > 0 && p.days[p.days.length - 2].day < 0;
  const allNeg = ps.every(p => lastp(p).day < 0);
  const allPos = ps.every(p => lastp(p).day > 0);

  const out = [];
  const add = (prio, icon, html) => out.push({ prio, icon, html });

  // ---- líder y cabeza de la tabla ----
  if (n >= 2) {
    const g = lastp(leader).cum - lastp(second).cum;
    if (g > 0.05)
      add(9.5, "🔥", who(leader) + " está que se sale. Le saca " + pts(g) + " a " + who(second) + ".");
    if (g > 3)
      add(6.7, "🧱", who(leader) + " pone tierra de por medio en lo más alto.");
  }
  add(6.0, lastp(leader).cum >= 0 ? "👑" : "🏳️",
    who(leader) + " lidera la liga con " + fmtPct(lastp(leader).cum) + " acumulado.");
  add(4.6, "🧭", who(leader) + " manda y no piensa soltar el timón.");
  if (lastp(leader).day > 0)
    add(6.9, "🛰️", "Nadie frena hoy a " + who(leader) + ": suma " + fmtPct(lastp(leader).day) + " en la jornada.");
  if (leader === bestDay && lastp(leader).day > 0)
    add(8.5, "🚀", "Día redondo para " + who(leader) + ": también firma la mejor jornada (" + fmtPct(lastp(leader).day) + ").");
  { const s = streak(leader, true); if (s >= 2)
    add(7.0, "📈", who(leader) + " enlaza " + s + " días seguidos en verde."); }
  if (n >= 2) {
    const g = lastp(leader).cum - lastp(tail).cum;
    if (g > 5)
      add(6.5, "🏁", "Si esto fuera una carrera, " + who(leader) + " ya vería la meta: " + pts(g) + " sobre " + who(tail) + ".");
    add(4.8, "📐", "De " + who(leader) + " a " + who(tail) + " hay " + pts(g) + " de diferencia en la general.");
    add(4.4, "🛡️", who(leader) + " defiende el liderato mientras " + who(tail) + " aprieta por detrás.");
    add(4.2, "🎙️", "El pulso entre " + who(leader) + " y " + who(second) + " mantiene viva la liga.");
  }

  // ---- movimientos del día ----
  if (bestDay && lastp(bestDay).day > 0)
    add(7.5, "⚡", who(bestDay) + " firma la mejor jornada de la liga: " + fmtPct(lastp(bestDay).day) + ".");
  if (n >= 2 && lastp(worstDay).day < 0)
    add(6.5, "🧊", who(worstDay) + " sufre la mayor caída del día: " + fmtPct(lastp(worstDay).day) + ".");
  if (n >= 2 && allNeg)
    add(7.2, "📉", "Jornada para olvidar: toda la liga cierra hoy en rojo.");
  if (n >= 2 && allPos)
    add(7.2, "🟢", "Viento a favor: toda la liga cierra hoy en verde.");
  ps.forEach(p => { if (p !== leader && lastp(p).day >= 2)
    add(6.6, "✨", who(p) + " es la sorpresa del día: se dispara " + fmtPct(lastp(p).day) + "."); });
  ps.forEach(p => { if (p !== worstDay && lastp(p).day <= -2)
    add(5.6, "🪂", who(p) + " se desinfla hoy: " + fmtPct(lastp(p).day) + " en la jornada."); });
  ps.forEach(p => { if (recovered(p))
    add(5.7, "🌤️", who(p) + " recupera el verde tras un mal tramo: " + fmtPct(lastp(p).day) + "."); });

  // ---- duelos y adelantamientos ----
  if (n >= 2) { const g = lastp(ranked[0]).cum - lastp(ranked[1]).cum;
    if (g >= 0 && g < 1.5)
      add(8.0, "🥊", "Duelo en la cima: " + who(ranked[0]) + " y " + who(ranked[1]) + " separados por apenas " + pts(g) + "."); }
  for (let i = 0; i < n - 1; i++) { const g = lastp(ranked[i]).cum - lastp(ranked[i + 1]).cum;
    if (g >= 0 && g < 0.3)
      add(7.0, "📸", "Photo-finish entre " + who(ranked[i]) + " y " + who(ranked[i + 1]) + ": los separan " + pts(g) + "."); }
  for (let i = 0; i < n - 1; i++) { const up = ranked[i], lo = ranked[i + 1];
    const g = lastp(up).cum - lastp(lo).cum, diff = lastp(lo).day - lastp(up).day;
    if (diff > 0.5 && g < 6)
      add(6.8, "🔀", who(lo) + " le recorta terreno a " + who(up) + ": hoy le gana " + pts(diff) + "."); }

  // ---- rachas, remontadas y momentum ----
  ps.forEach(p => { const s = streak(p, false); if (s >= 2)
    add(6.0 + s * 0.2, "🌧️", who(p) + " encadena " + s + " días en rojo. Toca remontar."); });
  ps.forEach(p => { if (p === leader) return; const s = streak(p, true); if (s >= 3)
    add(6.4, "🔋", who(p) + " aguanta el tirón: " + s + " días seguidos en positivo."); });
  ps.forEach(p => { const d = windowDelta(p); if (d > 3)
    add(6.0 + Math.min(d, 10) / 10, "🛫", who(p) + " está de dulce: suma " + pts(d) + " desde el arranque de la ventana."); });
  ps.forEach(p => { const k = Math.min(5, p.days.length); if (k >= 4 && greenCount(p, k) >= 4)
    add(5.8, "✅", who(p) + " está fino: " + greenCount(p, k) + " de los últimos " + k + " días en verde."); });
  ps.forEach(p => { if (lastp(p).cum <= -2)
    add(5.2, "🧯", who(p) + " necesita reaccionar: " + fmtPct(lastp(p).cum) + " acumulado."); });
  if (n >= 2 && lastp(tail).day > 0)
    add(5.5, "🌱", who(tail) + " da señales de vida: hoy suma " + fmtPct(lastp(tail).day) + " desde el fondo de la tabla.");
  if (n >= 2)
    add(4.0, "⏳", who(tail) + " cierra la tabla, pero la liga no ha hecho más que empezar.");
  ps.forEach(p => { if (p.days.length >= 3 && range(p) >= 6)
    add(5.2, "🎢", who(p) + " monta en la montaña rusa: " + pts(range(p)) + " de recorrido en la ventana."); });

  // ---- carteras (solo pesos, sin importes) ----
  ps.forEach(p => { const h = p.holdings; if (!h || !h.length) return;
    if (h.length === 1)
      add(6.2, "🎯", who(p) + " lo fía todo a " + h[0].ticker + ": el 100% de su cartera.");
    else if (h[0].w >= 40)
      add(6.0, "⚠️", who(p) + " concentra el riesgo: " + fmtW(h[0].w) + " en " + h[0].ticker + "."); });
  { const withH = ps.filter(p => p.holdings && p.holdings.length);
    if (withH.length) {
      const div = withH.slice().sort((a, b) => b.holdings.length - a.holdings.length)[0];
      if (div.holdings.length >= 4)
        add(5.4, "🧩", who(div) + " es quien más reparte: " + div.holdings.length + " valores en cartera."); } }
  if (DATA.allocation && DATA.allocation.length) { const top = DATA.allocation[0];
    if (top.w >= 20)
      add(5.0, "📊", "La liga entera va cargada de " + top.ticker + ": " + fmtW(top.w) + " del total agregado."); }

  out.sort((a, b) => b.prio - a.prio);
  return out;
}

let insightTimer = null, insightOff = 0;
function paintInsights() {
  const card = document.getElementById("insights-card");
  const box = document.getElementById("insights");
  const items = computeInsights();
  if (!items.length) { card.style.display = "none"; return; }
  card.style.display = "";
  const show = Math.min(3, items.length);
  if (insightOff >= items.length) insightOff = 0;
  const render = () => {
    box.innerHTML = "";
    for (let k = 0; k < show; k++) {
      const it = items[(insightOff + k) % items.length];
      const row = document.createElement("div"); row.className = "insight";
      row.innerHTML = '<span class="ic">' + it.icon + '</span><span class="tx">' + it.html + '</span>';
      box.appendChild(row);
    }
  };
  render();
  clearInterval(insightTimer);
  if (items.length > show) {
    insightTimer = setInterval(() => {
      [...box.children].forEach(c => c.style.opacity = "0");
      setTimeout(() => { insightOff = (insightOff + show) % items.length; render(); }, 450);
    }, 7000);
  }
}
paintInsights();

// ---- gráfica de líneas: % acumulado ----
const svg = document.getElementById("chart");
const wrap = document.querySelector(".chartwrap");
const NS = "http://www.w3.org/2000/svg";
// Dimensiones en unidades del viewBox == px reales del contenedor, para que
// el texto no se encoja al escalar en pantallas estrechas.
let W = 860, H = 360;
const M = {t: 16, r: 64, b: 30, l: 52};
function computeSize() {
  W = Math.max(300, Math.round(wrap.clientWidth || 860));
  const narrow = W < 520;
  H = narrow ? 300 : 360;
  M.r = narrow ? 52 : 64;
  M.l = narrow ? 48 : 52;
  svg.setAttribute("viewBox", "0 0 " + W + " " + H);
}
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
  computeSize();
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
  // eje X: tantas fechas como quepan (~1 cada 120px)
  const nTicks = Math.max(3, Math.round((W - M.l - M.r) / 120));
  const stepX = Math.max(1, Math.round(dates.length / nTicks));
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
      fill: "none", stroke: c, "stroke-width": 2.4,
      "stroke-linejoin": "round", "stroke-linecap": "round"}));
    const end = pts[pts.length - 1];
    svg.appendChild(el("circle", {cx: end[0], cy: end[1], r: 4, fill: c,
      stroke: css("--card-solid"), "stroke-width": 2.5}));
  });
  // etiquetas directas al final (solo si no chocan; la leyenda siempre está)
  if (DATA.players.length <= 4 && W >= 520) {
    const ends = DATA.players.map(p => {
      const lastDate = p.days[p.days.length-1].date;
      return {v: p.days[p.days.length-1].cum, yy: y(byDate[p.id][lastDate])};
    }).sort((a, b) => a.yy - b.yy);
    const collide = ends.some((e, i) => i && e.yy - ends[i-1].yy < 14);
    if (!collide) ends.forEach(e => {
      const t = el("text", {x: W - M.r + 4, y: e.yy + 4, fill: css("--ink-2"),
        "font-size": 11.5, style: "font-variant-numeric:tabular-nums;font-weight:600"});
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
if (mq.addEventListener) mq.addEventListener("change", () => { draw(); paintWidgets(); paintMonthly(); paintAllocation(); paintWallets(); paintInsights(); });
let rafId;
window.addEventListener("resize", () => {
  cancelAnimationFrame(rafId);
  rafId = requestAnimationFrame(draw);
});

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


def _allocation_weights(allocation: dict[str, float] | None) -> list[dict]:
    """Normaliza el valor de mercado agregado por ticker a pesos (%).

    Recibe ``{ticker: valor}`` (agregado de toda la liga) y devuelve una lista
    ordenada de mayor a menor ``[{"ticker", "w"}]`` con el peso en porcentaje.
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


def _prev_month(year: int, month: int) -> tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


def _month_best(computed: list[tuple[Player, list[DayResult]]],
                year: int, month: int, order: dict[str, int]) -> dict | None:
    """Mejor jugador de un mes concreto (composición de sus % diarios).

    Solo cuentan los días de la competición (``day >= COMPETITION_START``). Si
    nadie tiene datos ese mes devuelve ``None`` (el widget no se pinta). El
    ``spark`` es el acumulado intra-mes del ganador, para la mini gráfica.
    """
    best = None
    best_ret = None
    for player, series in computed:
        rows = sorted(
            (r for r in series
             if r.day.year == year and r.day.month == month
             and r.day >= COMPETITION_START),
            key=lambda r: r.day)
        if not rows:
            continue
        factor = 1.0
        spark = []
        for r in rows:
            factor *= 1.0 + r.daily_return
            spark.append(round((factor - 1.0) * 100, 4))
        ret = (factor - 1.0) * 100
        if best_ret is None or ret > best_ret:
            best_ret = ret
            best = {
                "name": player.display_name,
                "value": round(ret, 2),
                "slot": order[player.player_id],
                "month_name": _MONTHS_ES[month - 1],
                "month_year": year,
                "spark": spark,
            }
    return best


def _monthly_bests(computed: list[tuple[Player, list[DayResult]]],
                   today: date, order: dict[str, int]) -> dict:
    """Mejor de este mes y del mes pasado (``None`` si no hay datos)."""
    py, pm = _prev_month(today.year, today.month)
    return {
        "current": _month_best(computed, today.year, today.month, order),
        "previous": _month_best(computed, py, pm, order),
    }


def build_payload(computed: list[tuple[Player, list[DayResult]]],
                  last_days: int = 30,
                  pending: list[dict] | None = None,
                  allocation: dict[str, float] | None = None,
                  holdings: dict[str, dict[str, float]] | None = None,
                  live: dict[str, dict] | None = None,
                  today: date | None = None) -> dict:
    """Datos embebidos en la página. Respeta show_amounts por jugador.

    Solo se incluyen los últimos ``last_days`` días de cada jugador (la gráfica
    y las tablas de detalle muestran esa ventana). El ``% acumulado`` de cada
    día sigue siendo el de siempre (desde el inicio real), y ``since`` guarda la
    fecha de inicio real para la columna «Desde» de la clasificación.

    ``allocation`` es el valor de mercado agregado por ticker de toda la liga;
    se publica solo como pesos (%) para el widget de cartera de la liga, sin
    importes. ``holdings`` es el mismo valor de mercado por ticker pero
    desglosado por jugador (``{id: {ticker: valor}}``): se publica también solo
    como pesos (%) para la sección «Carteras», que muestra el reparto de cada
    jugador sin revelar importes.

    ``live`` es un indicador provisional por jugador (``{id: {"cum","day"}}``)
    con la valoración de hoy a precio en vivo. Es solo informativo: no altera
    la serie oficial ni la clasificación.
    """
    today = today or date.today()
    live = live or {}
    holdings = holdings or {}
    players = []
    # Slot de color por orden alfabético de id: estable aunque cambie el ranking
    order = {p.player_id: i for i, p in enumerate(
        sorted((p for p, _ in computed), key=lambda p: p.player_id))}
    for player, series in computed:
        if not series:
            continue
        window = series[-last_days:] if last_days else series
        days = []
        for row in window:
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
        entry = {
            "id": player.player_id,
            "name": player.display_name,
            "slot": order[player.player_id],
            "amounts": player.show_amounts,
            "since": series[0].day.isoformat(),
            "days": days,
            "holdings": _allocation_weights(holdings.get(player.player_id)),
        }
        if player.player_id in live:
            entry["live"] = live[player.player_id]
        players.append(entry)
    return {"players": players, "pending": pending or [],
            "allocation": _allocation_weights(allocation),
            "monthly": _monthly_bests(computed, today, order)}


def write_index(
    computed: list[tuple[Player, list[DayResult]]],
    out_path: str = "docs/index.html",
    today: date | None = None,
    last_days: int = 30,
    pending: list[dict] | None = None,
    allocation: dict[str, float] | None = None,
    holdings: dict[str, dict[str, float]] | None = None,
    live: dict[str, dict] | None = None,
) -> str:
    payload = json.dumps(
        build_payload(computed, last_days=last_days, pending=pending,
                      allocation=allocation, holdings=holdings, live=live,
                      today=today or date.today()),
        ensure_ascii=False)
    payload = payload.replace("</", "<\\/")  # nunca cerrar el <script> desde los datos
    html = (_TEMPLATE
            .replace("__UPDATED__", (today or date.today()).isoformat())
            .replace("__DATA__", payload))
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(html)
    return out_path
