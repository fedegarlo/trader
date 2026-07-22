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
from datetime import date, datetime, timezone

from .players import Player
from .portfolio import DayResult
from .revolut import BUY, SELL
from .tickers import ticker_meta

# La competición oficial empezó este día: los días anteriores (pruebas o
# histórico previo) no cuentan. Todos los jugadores se comparan desde esta
# fecha (incluida), rebasando la rentabilidad acumulada al inicio real de la
# competición (ver ``rebase_from`` en portfolio.py), y también acota los
# widgets de «mejor del mes».
COMPETITION_START = date(2026, 7, 14)

_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#efeaf8" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#0e0d13" media="(prefers-color-scheme: dark)">
<link rel="apple-touch-icon" href="icon-ios.png">
<link rel="manifest" href="manifest.webmanifest" id="manifest-link">
<meta name="apple-mobile-web-app-title" content="Trader League" id="app-title-meta">
<title>🏆 Trader League</title>
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
  .lang {
    flex: none; border: 0; cursor: pointer; color: var(--accent);
    background: color-mix(in srgb, var(--accent) 14%, transparent);
    min-width: 46px; height: 46px; padding: 0 13px; border-radius: 999px;
    display: grid; place-items: center; font-family: inherit;
    font-weight: 800; font-size: 15px; letter-spacing: 0.01em; line-height: 1;
  }
  .lang:active { transform: translateY(1px); }
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
  /* interrogante: abre el modal que explica cómo se calcula la rentabilidad */
  .whelp { position: absolute; z-index: 3; top: 12px; right: 12px;
           width: 26px; height: 26px; border-radius: 999px; flex: none;
           border: 1px solid var(--hair); background: var(--surface-2);
           color: var(--ink-2); font-size: 15px; font-weight: 800; line-height: 1;
           cursor: pointer; display: grid; place-items: center;
           transition: color .12s ease, border-color .12s ease; }
  .whelp:hover { color: var(--accent); border-color: color-mix(in srgb, var(--accent) 45%, var(--hair)); }
  .whelp:active { transform: translateY(1px); }
  #hero-card .wlabel { padding-right: 34px; }
  .wlabel { color: var(--ink-2); font-size: 14px; font-weight: 600; }
  .wbig { font-size: clamp(26px, 8vw, 34px); font-weight: 800; letter-spacing: -0.035em; line-height: 1.1; margin-top: 3px; display: flex; align-items: baseline; flex-wrap: wrap; gap: 4px 10px; }
  .wbig.sm { font-size: clamp(22px, 6.6vw, 28px); white-space: nowrap; }
  .num { font-variant-numeric: tabular-nums; }
  .num.closed { color: var(--ink-2); }
  .delta { font-size: 15px; font-weight: 700; letter-spacing: -0.01em; }
  @keyframes pulse {
    0% { box-shadow: 0 0 0 0 color-mix(in srgb, currentColor 55%, transparent); }
    70% { box-shadow: 0 0 0 6px transparent; }
    100% { box-shadow: 0 0 0 0 transparent; }
  }
  .wsub { color: var(--ink-2); font-size: 13.5px; font-weight: 600; margin-top: 4px; }
  .bestname { color: var(--ink); font-size: 18px; font-weight: 700; margin-top: 8px; display: flex; align-items: center; gap: 6px; }
  .bestname .medal { font-size: 20px; line-height: 1; }
  .winnername { color: var(--ink); font-size: clamp(20px, 5.5vw, 24px); font-weight: 800;
                letter-spacing: -0.02em; line-height: 1.15; margin-top: 6px;
                display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
  .winnername .trophy { font-size: 22px; line-height: 1; }
  .wsub.muted { color: var(--muted); font-weight: 500; }
  .wsub.treat { color: var(--ink-2); font-weight: 700; margin-top: 6px; }
  .sparkwrap { margin: 12px -18px 0; height: 116px; }
  .sparkwrap.sm { height: 58px; margin-top: 10px; }
  svg.spark { display: block; width: 100%; height: 100%; }
  .wrow { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .wrow .card { padding-bottom: 18px; display: flex; flex-direction: column; }
  .wrow .card.widget { padding-bottom: 0; }

  /* banners promocionales (solo versión japonesa): anuncios ficticios al
     estilo de los folletos japoneses, intercalados entre los widgets, con
     enlace a webs reales de Japón. Colores propios del banner (fijos en
     claro/oscuro); la etiqueta «広告» deja claro que son anuncios. */
  .jp-banner { position: relative; display: flex; align-items: center; gap: 13px;
               margin: 10px 0; padding: 14px 16px; border-radius: 22px; text-decoration: none;
               color: #1a1a1a; overflow: hidden;
               border: 1px solid rgba(11,10,16,0.06);
               box-shadow: 0 1px 1px rgba(11,10,16,0.05), 0 14px 30px -24px rgba(11,10,16,0.55); }
  .jp-banner:active { transform: translateY(1px); }
  .jp-banner .bicon { flex: none; width: 52px; height: 52px; border-radius: 14px;
                      display: grid; place-items: center; font-size: 29px; line-height: 1;
                      background: rgba(255,255,255,0.94); box-shadow: 0 2px 6px rgba(0,0,0,0.12); }
  .jp-banner .btext { flex: 1 1 0; min-width: 0; }
  .jp-banner .btop { font-size: 12.5px; font-weight: 700; opacity: 0.9; letter-spacing: 0.01em;
                     display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .jp-banner .bmain { font-size: 19px; font-weight: 800; letter-spacing: 0.01em; line-height: 1.2;
                      margin-top: 1px; display: block; }
  .jp-banner .btag { display: inline-block; margin-top: 5px; font-size: 10px; font-weight: 800;
                     background: rgba(255,255,255,0.9); color: #1f6bff; padding: 1px 7px; border-radius: 999px; }
  .jp-banner .barrow { flex: none; font-size: 16px; font-weight: 800; opacity: 0.65; }
  .jp-b1 { background: linear-gradient(180deg, #ffe873, #ffe04c); color: #333; }   /* amarillo */
  .jp-b1 .bhi { color: #0b63d6; }
  .jp-b2 { background: linear-gradient(180deg, #cdecff, #8fd3f7); color: #0b3a5b; }   /* celeste */
  .jp-b3 { background: linear-gradient(180deg, #3a9bff, #1f6bff); color: #fff; }   /* azul */

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

  /* widget de últimas operaciones (fecha · compra/venta · ticker · jugador) */
  .op-row { display: flex; align-items: center; gap: 10px; padding: 11px 4px;
            border-top: 1px solid var(--hair); }
  .op-row:first-child { border-top: none; }
  .op-tk { flex: none; display: inline-flex; align-items: center; gap: 9px;
           font-weight: 700; letter-spacing: -0.01em; }
  .op-tk .logo, .op-tk .mono { width: 30px; height: 30px; }
  .op-tk .sym { white-space: nowrap; }
  .op-act { flex: none; font-size: 11px; font-weight: 800; letter-spacing: 0.03em;
            text-transform: uppercase; padding: 3px 9px; border-radius: 999px; }
  .op-act.buy { background: rgba(22,163,74,0.15); color: #16a34a; }
  .op-act.sell { background: rgba(225,29,72,0.15); color: #e11d48; }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) .op-act.buy { background: rgba(34,197,94,0.20); color: #4ade80; }
    :root:not([data-theme="light"]) .op-act.sell { background: rgba(244,63,94,0.20); color: #fb7185; }
  }
  :root[data-theme="dark"] .op-act.buy { background: rgba(34,197,94,0.20); color: #4ade80; }
  :root[data-theme="dark"] .op-act.sell { background: rgba(244,63,94,0.20); color: #fb7185; }
  .op-name { display: inline-flex; align-items: center; margin-left: auto;
             color: var(--ink-2); font-weight: 600; font-size: 13.5px; min-width: 0; }
  .op-name .nm { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .op-date { flex: none; color: var(--muted); font-weight: 600; font-size: 12.5px;
             font-variant-numeric: tabular-nums; }
  .op-tk.clk:hover .sym, .op-name.clk:hover .nm { color: var(--accent); }

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

  /* elementos abribles (ticker / jugador) */
  .clk { cursor: pointer; }
  .dl.clk:hover .tk, tr.clk:hover .nm, tr.clk:hover td.name { color: var(--accent); }
  .legend span.clk:hover { color: var(--accent); }

  /* logo / monograma */
  .logo, .mono {
    flex: none; border-radius: 9px; display: grid; place-items: center;
    object-fit: cover; background: var(--surface-2); overflow: hidden;
  }
  .mono { color: #fff; font-weight: 800; letter-spacing: -0.02em; line-height: 1;
          border-radius: 999px; }
  .logo { border: 1px solid var(--hair); }

  /* overlay de detalle */
  .modal {
    position: fixed; inset: 0; z-index: 50; display: none;
    align-items: flex-end; justify-content: center;
    background: color-mix(in srgb, #05040a 52%, transparent);
    -webkit-backdrop-filter: blur(3px); backdrop-filter: blur(3px);
    padding: 0;
  }
  .modal.open { display: flex; }
  .sheet {
    position: relative;
    width: 100%; max-width: 620px; max-height: 92vh; max-height: 92dvh;
    overflow-y: auto; -webkit-overflow-scrolling: touch;
    overscroll-behavior: contain; touch-action: pan-y; will-change: transform;
    background: var(--card-solid);
    border: 1px solid var(--ring); border-bottom: none;
    border-radius: 22px 22px 0 0;
    padding: calc(6px + env(safe-area-inset-top)) 18px
             calc(24px + env(safe-area-inset-bottom));
    box-shadow: 0 -18px 50px -20px rgba(5,4,10,0.6);
    animation: sheetin 0.30s cubic-bezier(0.2,0.85,0.25,1);
  }
  @keyframes sheetin { from { transform: translateY(100%); } to { transform: none; } }
  .sheet.closing { animation: sheetout 0.22s ease-in forwards; }
  @keyframes sheetout { from { transform: translateY(0); } to { transform: translateY(100%); } }
  /* zona de agarre: ocupa el ancho para poder arrastrar y cerrar de un toque */
  .grab { position: sticky; top: 0; z-index: 2; margin: 0 -18px 8px; padding: 9px 0 7px;
          background: var(--card-solid); cursor: grab; touch-action: none; }
  .grab::before { content: ""; display: block; width: 40px; height: 5px; border-radius: 999px;
                  background: var(--baseline); opacity: 0.5; margin: 0 auto; }
  .mhead { display: flex; align-items: center; gap: 13px; padding-right: 42px; }
  .mhead .mtitle { min-width: 0; }
  .mhead .mtitle .t1 { font-size: 20px; font-weight: 800; letter-spacing: -0.02em;
                       display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
  .mhead .mtitle .t2 { color: var(--ink-2); font-size: 13.5px; font-weight: 600; margin-top: 2px; }
  .mclose {
    position: absolute; z-index: 4;
    top: calc(14px + env(safe-area-inset-top)); right: 16px;
    flex: none; border: 0; cursor: pointer; color: var(--ink-2);
    background: var(--surface-2); width: 34px; height: 34px; border-radius: 999px;
    font-size: 18px; line-height: 1; display: grid; place-items: center;
  }
  .mbadge { font-size: 12px; font-weight: 800; padding: 2px 9px; border-radius: 999px;
            background: var(--up-soft); color: var(--up); }
  .mbadge.neg { background: var(--down-soft); color: var(--down); }
  .mbadge.rank { background: color-mix(in srgb, var(--accent) 15%, transparent); color: var(--accent); }

  .tiles { display: grid; grid-template-columns: repeat(3, 1fr); gap: 9px; margin-top: 16px; }
  .tile { background: var(--surface-2); border: 1px solid var(--hair); border-radius: 15px;
          padding: 11px 12px; min-width: 0; }
  .tile .k { color: var(--muted); font-size: 11.5px; font-weight: 600; }
  .tile .v { font-size: 18px; font-weight: 800; letter-spacing: -0.02em; margin-top: 3px;
             font-variant-numeric: tabular-nums; }
  .msec { margin-top: 18px; }
  .msec > .h { font-size: 13px; font-weight: 700; color: var(--ink-2); margin-bottom: 9px;
               display: flex; align-items: center; gap: 7px; }
  .mspark { height: 120px; margin: 0 -4px; }
  .holder-row, .mini-row { display: flex; align-items: center; gap: 10px; padding: 9px 4px;
                           border-top: 1px solid var(--hair); font-size: 14px; }
  .holder-row:first-child, .mini-row:first-child { border-top: none; }
  .holder-row .nm { font-weight: 700; display: inline-flex; align-items: center; gap: 8px; }
  .holder-row .w, .mini-row .v { margin-left: auto; font-weight: 700;
                                 font-variant-numeric: tabular-nums; }
  .mini-row .dt { color: var(--muted); font-size: 12.5px; font-weight: 600; }
  .news { display: flex; flex-wrap: wrap; gap: 8px; }
  .news a {
    display: inline-flex; align-items: center; gap: 6px; text-decoration: none;
    font-size: 13px; font-weight: 700; color: var(--ink);
    background: var(--surface-2); border: 1px solid var(--hair);
    padding: 8px 12px; border-radius: 12px;
  }
  .news a:hover { border-color: color-mix(in srgb, var(--accent) 45%, var(--hair)); color: var(--accent); }
  .news a .ext { color: var(--muted); font-size: 11px; }
  /* operar en Revolut: botones comprar/vender que abren la app en el detalle del valor */
  .revolut { display: flex; gap: 10px; }
  .rev-btn {
    flex: 1; display: inline-flex; align-items: center; justify-content: center; gap: 8px;
    text-decoration: none; font-size: 14px; font-weight: 800; letter-spacing: -0.01em;
    padding: 12px 14px; border-radius: 14px; border: 1px solid transparent;
    transition: filter .12s ease, transform .12s ease;
  }
  .rev-btn:active { transform: translateY(1px); }
  .rev-btn:hover { filter: brightness(1.05); }
  .rev-btn .ic { font-size: 11px; opacity: .9; }
  .rev-btn.buy { background: #16a34a; color: #fff; }
  .rev-btn.sell { background: #e11d48; color: #fff; }
  .rev-note { color: var(--muted); font-size: 11.5px; margin-top: 8px; }
  .mnote { color: var(--muted); font-size: 11.5px; margin-top: 14px; }
  /* párrafo explicativo y fórmulas del modal «cómo se calcula» */
  .mtext { color: var(--ink-2); font-size: 14px; font-weight: 500; line-height: 1.5; }
  .mtext + .mtext { margin-top: 9px; }
  .mtext b { color: var(--ink); font-weight: 700; }
  .formula { font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
             font-size: 13.5px; font-weight: 600; color: var(--ink);
             background: var(--surface-2); border: 1px solid var(--hair);
             border-radius: 12px; padding: 11px 13px; overflow-x: auto;
             white-space: nowrap; font-variant-numeric: tabular-nums; }
  .formula + .formula { margin-top: 8px; }
  .formula .lbl { color: var(--muted); font-weight: 700; margin-right: 8px; }
  .chips { display: flex; flex-wrap: wrap; gap: 8px; }
  .chip-tk { display: inline-flex; align-items: center; gap: 7px; cursor: pointer;
             background: var(--surface-2); border: 1px solid var(--hair);
             padding: 6px 11px 6px 6px; border-radius: 999px; font-weight: 700; font-size: 13px; }
  .chip-tk:hover { border-color: color-mix(in srgb, var(--accent) 45%, var(--hair)); }
  .chip-tk .w { color: var(--muted); font-weight: 600; }

  /* consenso de analistas */
  .consensus { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
  .cbadge { font-size: 14px; font-weight: 800; letter-spacing: -0.01em;
            padding: 5px 12px; border-radius: 999px;
            background: var(--up-soft); color: var(--up); }
  .cbadge.neg { background: var(--down-soft); color: var(--down); }
  .cbadge.neutral { background: var(--surface-2); color: var(--ink-2); }
  .cmeta { color: var(--ink-2); font-size: 13px; font-weight: 600; }
  .distbar { display: flex; height: 12px; border-radius: 999px; overflow: hidden;
             margin-top: 13px; background: var(--surface-2); }
  .distbar > span { min-width: 2px; }
  .distlegend { display: flex; flex-wrap: wrap; gap: 6px 14px; margin-top: 10px;
                font-size: 12px; font-weight: 600; color: var(--ink-2); }
  .distlegend .k { display: inline-flex; align-items: center; gap: 6px; }
  .distlegend .sw { width: 9px; height: 9px; border-radius: 3px; flex: none; }
  .target { margin-top: 13px; font-size: 14px; font-weight: 700; }
  .target .up { font-variant-numeric: tabular-nums; }
  .target .rng { color: var(--muted); font-weight: 600; font-size: 12.5px; }

  /* próximo paso (sugerencia sobre la cartera del jugador) */
  .nextstep { border: 1px solid color-mix(in srgb, var(--accent) 30%, var(--hair));
              background: color-mix(in srgb, var(--accent) 8%, var(--surface-2));
              border-radius: 16px; padding: 13px 14px; }
  .nextstep.clk { cursor: pointer; }
  .nextstep.clk:hover { border-color: color-mix(in srgb, var(--accent) 55%, var(--hair)); }
  .nextstep .top { display: flex; align-items: center; gap: 9px; }
  .nextstep .act { font-size: 11px; font-weight: 800; letter-spacing: 0.04em; text-transform: uppercase;
                   padding: 3px 8px; border-radius: 999px; background: var(--up-soft); color: var(--up); }
  .nextstep .act.neg { background: var(--down-soft); color: var(--down); }
  .nextstep .ttl { font-weight: 800; font-size: 15px; letter-spacing: -0.01em; }
  .nextstep .body { font-size: 13.5px; color: var(--ink-2); font-weight: 600; margin-top: 7px; }
  .nextstep .dis { color: var(--muted); font-size: 11px; margin-top: 8px; line-height: 1.4; }

  @media (min-width: 620px) {
    main { gap: 14px; }
    .card { padding: 22px; }
    .sparkwrap { margin: 14px -22px 0; }
    .modal { align-items: center; padding: 20px; }
    .sheet { border-radius: 24px; border-bottom: 1px solid var(--ring);
             padding-top: 18px; touch-action: auto;
             animation: popin 0.22s cubic-bezier(0.2,0.85,0.25,1); }
    .sheet.closing { animation: none; opacity: 0; }
    .mclose { top: 18px; }
    .grab { display: none; }
  }
  @keyframes popin { from { transform: translateY(14px); opacity: 0.4; } to { transform: none; opacity: 1; } }
  @media (prefers-reduced-motion: reduce) {
    .sheet, .sheet.closing { animation: none; }
  }
</style>
</head>
<body>
<main>
  <header>
    <div class="eyebrow" id="eyebrow"></div>
    <div class="hrow">
      <h1 data-i18n="appTitle">Trader League</h1>
      <div class="hbtns">
        <button class="lang" id="lang-btn" type="button"><span id="lang-label"></span></button>
        <a class="upload" id="upload-mail" href="mailto:ligatrader26@gmail.com" data-i18n-title="sendPositions">
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor"
               stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M12 16V4"/><path d="M7 9l5-5 5 5"/><path d="M5 20h14"/>
          </svg>
        </a>
      </div>
    </div>
    <div class="hbar">
      <span class="chip" id="hchip"><span data-i18n="allPlayers"></span> <span class="caret">▾</span></span>
      <span class="period" data-i18n="period30"></span>
    </div>
  </header>

  <section class="card warn" id="pending-card" style="display:none">
    <h2 data-i18n="pendingTitle"></h2>
    <div class="wsub" id="pending" style="margin-top:6px"></div>
  </section>

  <div id="widgets" style="display:grid;gap:12px">
    <section class="card widget" id="hero-card">
      <button class="whelp" id="hero-help" type="button" data-i18n-title="calcHelpAria">?</button>
      <div class="wlabel"><span data-i18n="leader"></span> · <span id="hero-name"></span></div>
      <div class="wbig"><span class="num" id="hero-val"></span><span class="delta" id="hero-delta"></span></div>
      <div class="sparkwrap" id="hero-spark"></div>
    </section>
    <div class="wrow">
      <section class="card widget" id="best-card">
        <div class="wlabel"><span data-i18n="bestOfDay"></span><span id="best-date"></span></div>
        <div class="wbig"><span class="num" id="best-val"></span></div>
        <div class="bestname" id="best-name"></div>
      </section>
      <section class="card" id="gap-card">
        <div class="wlabel" data-i18n="gapTitle"></div>
        <div class="wbig sm"><span class="num" id="gap-val"></span></div>
        <div style="margin-top:auto">
          <div class="wsub" id="gap-top"></div>
          <div class="wsub muted" id="gap-bot"></div>
        </div>
      </section>
    </div>
    <div class="wrow" id="month-row" style="display:none">
      <section class="card widget" id="month-cur-card">
        <div class="wlabel" id="month-cur-label"></div>
        <div class="winnername"><span id="month-cur-player"></span><span class="trophy">🏆</span></div>
        <div class="wbig sm"><span class="num" id="month-cur-val"></span></div>
        <div class="wsub treat" id="month-cur-note"></div>
        <div class="sparkwrap sm" id="month-cur-spark"></div>
      </section>
      <section class="card widget" id="month-prev-card">
        <div class="wlabel" id="month-prev-label"></div>
        <div class="winnername"><span id="month-prev-player"></span><span class="trophy">🏆</span></div>
        <div class="wbig sm"><span class="num" id="month-prev-val"></span></div>
        <div class="sparkwrap sm" id="month-prev-spark"></div>
      </section>
    </div>
  </div>

  <section class="card" id="ops-card" style="display:none">
    <div class="wlabel" data-i18n="recentOps"></div>
    <div id="ops-list" style="margin-top:8px"></div>
  </section>

  <section class="card" id="insights-card" style="display:none">
    <div class="ai-head">
      <span class="ai-badge" data-i18n="aiBadge"></span>
      <span class="ai-title" data-i18n="insightsTitle"></span>
      <span class="ai-live"><span class="dot"></span><span data-i18n="aiLive"></span></span>
    </div>
    <div class="insights" id="insights"></div>
  </section>

  <section class="card">
    <h2 data-i18n="ranking"></h2>
    <div class="overx" style="margin-top:6px"><table id="ranking"></table></div>
  </section>

  <section class="card" id="daily-card" style="display:none">
    <h2 id="daily-title"></h2>
    <div class="overx" style="margin-top:6px"><table id="daily"></table></div>
  </section>

  <section class="card" id="alloc-card" style="display:none">
    <div class="wlabel" data-i18n="leagueWallet"></div>
    <div id="alloc-bars"></div>
    <div class="alloc-insight" id="alloc-insight"></div>
  </section>

  <section class="card" id="wallets-card" style="display:none">
    <h2 data-i18n="walletsTitle"></h2>
    <div id="wallets" style="margin-top:4px"></div>
  </section>

  <section class="card">
    <h2 data-i18n="cumTitle"></h2>
    <div class="chartwrap">
      <svg id="chart" viewBox="0 0 860 360" role="img" data-i18n-aria="cumChartAria"></svg>
      <div class="tip" id="tip"></div>
    </div>
    <div class="legend" id="legend"></div>
  </section>

  <section class="card">
    <h2 data-i18n="dailyDetailTitle"></h2>
    <div id="detail" style="margin-top:4px"></div>
  </section>
</main>
<div class="modal" id="modal" aria-hidden="true">
  <div class="sheet" id="sheet" role="dialog" aria-modal="true" data-i18n-aria="detailAria">
    <div class="grab"></div>
    <div id="modal-body"></div>
  </div>
</div>
<footer data-i18n-html="footer"></footer>
<script>
const DATA = __DATA__;
const UPDATED = "__UPDATED__";

// ==== idioma: inglés por defecto, japonés opcional ====================
// La selección se recuerda por dispositivo en localStorage. El toggle solo
// guarda la preferencia y recarga: toda la interfaz se pinta según ``LANG``.
const LANG = (() => {
  try { const s = localStorage.getItem("lang"); if (s === "en" || s === "ja") return s; }
  catch (e) {}
  return "en";
})();
document.documentElement.lang = LANG;

const NBSP = String.fromCharCode(160);
const MONTHS = {
  en: ["January","February","March","April","May","June","July","August",
       "September","October","November","December"],
  ja: ["1月","2月","3月","4月","5月","6月","7月","8月","9月","10月","11月","12月"],
};
const monthLabel = (m, y) => LANG === "ja"
  ? y + "年" + MONTHS.ja[m - 1]
  : MONTHS.en[m - 1] + " " + y;

const I18N = {
  en: {
    appTitle: "Trader League",
    eyebrow: "🏆 League · Revolut · updated " + UPDATED,
    sendPositions: "Send positions",
    mailBody: "attached are my positions in csv format",
    langBtnLabel: "日本語",
    langBtnAria: "Switch to Japanese",
    allPlayers: "All players",
    period30: "Last 30 days",
    pendingTitle: "⏳ Awaiting passphrase",
    pendingText: n => n + " — the statement is uploaded but couldn't be decrypted. " +
      "The passphrase is probably not the league's: please re-upload with the correct one.",
    leader: "Leader",
    calcHelpAria: "How the ranking is calculated",
    calc: {
      title: "How the ranking is calculated",
      subtitle: "Time-weighted return — fair across different amounts",
      qa: [
        ["Are sales taken into account?",
         "Yes — every buy and sell is processed — but a sale on its own doesn't change your return. Selling just turns shares into cash at their market price, so your portfolio is worth the same the instant before and after (bar fees). Whatever you had already earned stays locked in."],
        ["If I sell, do I keep my profitability?",
         "Yes. Your accumulated return is preserved: selling never resets it. From then on your cash simply stops moving — idle cash scores 0% per day — so you hold your position but stop climbing until you buy back in."],
        ["What actually moves the score, then?",
         "Only how your holdings change in value day to day: share prices and dividends. Buys and sells reshuffle money between cash and shares without adding or removing any gains."],
        ["Do deposits or withdrawals help?",
         "No. Paying in or taking out money is neutralised (simple Dietz), so adding cash never inflates your score. Everyone is compared on <b>percentage return</b>, not on how much they invested."],
      ],
      formulaLabel: "The formulas",
      dailyLbl: "Day",
      dailyFormula: "r = (end − start − flow) / (start + flow/2)",
      cumLbl: "Total",
      cumFormula: "∏ (1 + rₙ) − 1",
      note: "That's why someone with €100 and someone with €10,000 compete on equal terms: what counts is the percentage, not the amount.",
    },
    bestOfDay: "Best of the day",
    recentOps: "Latest trades",
    opBuy: "Buy", opSell: "Sell",
    marketClosed: "Market closed",
    gapTitle: "1st–last gap",
    winnerOf: ml => "Winner of " + ml,
    lunchNote: "🍽️ Their turn to buy lunch",
    aiBadge: "AI",
    insightsTitle: "League insights",
    aiLive: "automatic analysis",
    ranking: "Standings",
    rankCols: ["#", "Player", "Cumulative %", "Last day %", "Since"],
    dailyTitle: ml => "🏅 Daily champion · " + ml,
    dailyCols: ["Date", "Champion", "Day %"],
    leagueWallet: "League portfolio",
    walletsTitle: "Portfolios by player",
    cumTitle: "Cumulative return · last 30 days",
    cumChartAria: "Cumulative return over time by player",
    dailyDetailTitle: "Daily detail · last 30 days",
    detailAria: "Detail",
    footer: "Daily return with simple Dietz (deposits and withdrawals don't count " +
      "as gains); cumulative by geometric compounding (time-weighted return). " +
      "Data: encrypted Revolut statements · closing prices from Yahoo Finance · " +
      "logos by <a href=\\"https://logo.dev\\" target=\\"_blank\\" rel=\\"noopener noreferrer\\">Logo.dev</a>.",
    pp: "\\u00a0pp",
    assets: n => n === 1 ? "asset" : "assets",
    others: "Others",
    donutAria: "Portfolio breakdown by weight",
    allocInsight: (tk, w) => "📊 Largest position · " + tk +
      ' <span class="muted">· ' + w + " of total</span>",
    walletTop: (tk, w) => "Largest · " + tk + " " + w,
    noPlayers: "No players with data yet",
    noPlayersDot: "No players with data yet.",
    detailColsFull: ["Date","Start","End","Ext. flow","Day P&L","Day %","Cumulative %"],
    detailColsSimple: ["Date","Day %","Cumulative %"],
    buy: "Buy", sell: "Sell",
    recBuckets: ["Strong buy","Buy","Hold","Sell","Strong sell"],
    analystRec: "Analyst recommendation",
    analysts: n => n + (n === 1 ? " analyst" : " analysts"),
    avg: v => "avg " + v + "/5",
    priceTarget: m => "🎯 Price target " + m,
    rangeLabel: (lo, hi) => "· range " + lo + "–" + hi,
    relatedTickers: "Related tickers",
    nextBuy: "Buy", nextTrim: "Trim",
    nextTitle: (tk, buy) => buy ? "Add to " + tk : "Trim " + tk,
    consensusBit: l => "consensus " + l.toLowerCase(),
    targetBit: pct => "target " + pct,
    ofPortfolio: w => w + " of their portfolio",
    nextDisclaimer: "💡 Suggested step based on analyst consensus (Yahoo Finance). " +
      "Not investment advice.",
    close: "Close",
    weightInLeague: "League weight",
    heldBy: "Held by",
    playersCount: n => n + (n === 1 ? " player" : " players"),
    variation: "Change",
    tradeOnRevolut: "Trade on Revolut",
    revNote: tk => "Open " + tk + "'s page in the Revolut app to buy or sell.",
    priceRange: (a, b) => "Price · " + a + " → " + b,
    whoHasIt: "Who holds it",
    news: "News",
    tickerNote: 'Logo: <a href="https://logo.dev" target="_blank" rel="noopener noreferrer">logo.dev</a> · ' +
      "prices and analyst consensus: Yahoo Finance · informational, not investment advice.",
    since: d => "Since " + d,
    nextStep: "Next step",
    cumPct: "Cumulative %",
    bestDayTile: "Best day",
    worstDayTile: "Worst day",
    lastDayPct: "Last day %",
    streak: "Streak",
    streakLabel: (sign, n) => sign > 0 ? (n === 1 ? "day green" : "days green")
      : (sign < 0 ? (n === 1 ? "day red" : "days red") : "streak"),
    sessions: "Sessions",
    cumLastN: n => "Cumulative return · last " + n + " days",
    portfolioCount: n => "Portfolio (" + n + (n === 1 ? " holding)" : " holdings)"),
    recentSessions: "Recent sessions",
    portfolioNews: "Portfolio news",
    points: v => Math.abs(v).toFixed(2) + NBSP + "points",
    ins: {
      leaderFire: (a, g, b) => a + " is on fire — " + g + " ahead of " + b + ".",
      leaderPullAway: a => a + " is pulling away at the top.",
      leaderLeads: (a, p) => a + " leads the league with " + p + " cumulative.",
      leaderHelm: a => a + " is in command and won't let go of the helm.",
      leaderUnstoppable: (a, p) => "No one is stopping " + a + " today — " + p + " on the session.",
      leaderPerfect: (a, p) => "A perfect day for " + a + ": also the best session (" + p + ").",
      leaderGreenStreak: (a, s) => a + " strings together " + s + " straight days in the green.",
      raceFinish: (a, g, b) => "If this were a race, " + a + " would already see the finish line: " + g + " over " + b + ".",
      overallGap: (a, b, g) => "From " + a + " to " + b + " there are " + g + " in the overall standings.",
      leaderDefends: (a, b) => a + " defends the lead while " + b + " pushes from behind.",
      pulse: (a, b) => "The duel between " + a + " and " + b + " keeps the league alive.",
      bestSession: (a, p) => a + " posts the league's best session: " + p + ".",
      worstDrop: (a, p) => a + " takes the day's biggest hit: " + p + ".",
      allRed: () => "A session to forget: the whole league closes in the red today.",
      allGreen: () => "Tailwind: the whole league closes in the green today.",
      surprise: (a, p) => a + " is the day's surprise, soaring " + p + ".",
      deflate: (a, p) => a + " deflates today: " + p + " on the session.",
      backToGreen: (a, p) => a + " returns to green after a rough patch: " + p + ".",
      duelTop: (a, b, g) => "Duel at the top: " + a + " and " + b + " separated by just " + g + ".",
      photoFinish: (a, b, g) => "Photo finish between " + a + " and " + b + ": " + g + " apart.",
      cutsGround: (lo, up, g) => lo + " gains ground on " + up + ": " + g + " today.",
      redStreak: (a, s) => a + " strings together " + s + " days in the red. Time to bounce back.",
      holdsFirm: (a, s) => a + " holds firm: " + s + " straight days positive.",
      onARoll: (a, g) => a + " is on a roll: " + g + " since the window opened.",
      sharp: (a, g, k) => a + " is sharp: " + g + " of the last " + k + " days green.",
      needsReact: (a, p) => a + " needs to react: " + p + " cumulative.",
      signsOfLife: (a, p) => a + " shows signs of life: " + p + " today from the bottom.",
      bottomEarly: a => a + " sits at the bottom, but the league has only just begun.",
      rollercoaster: (a, g) => a + " is on a rollercoaster: " + g + " of swing in the window.",
      allIn: (a, tk) => a + " is all in on " + tk + ": 100% of the portfolio.",
      concentrates: (a, w, tk) => a + " concentrates risk: " + w + " in " + tk + ".",
      mostDiversified: (a, n) => a + " is the most diversified: " + n + " holdings.",
      leagueLoaded: (tk, w) => "The whole league is loaded on " + tk + ": " + w + " of the aggregate.",
    },
  },
  ja: {
    appTitle: "トレーダーリーグ",
    eyebrow: "🏆 リーグ · Revolut · 更新 " + UPDATED,
    sendPositions: "ポジションを送信",
    mailBody: "csv形式のポジションを添付します",
    langBtnLabel: "EN",
    langBtnAria: "英語に切り替え",
    allPlayers: "全プレイヤー",
    period30: "直近30日",
    pendingTitle: "⏳ パスフレーズ待ち",
    pendingText: n => n + " — 明細はアップロード済みですが復号できませんでした。" +
      "パスフレーズがリーグのものと異なる可能性があります。正しいもので再アップロードしてください。",
    leader: "首位",
    calcHelpAria: "順位の計算方法",
    calc: {
      title: "順位の計算方法",
      subtitle: "時間加重収益率 — 金額が違っても公平に比較",
      qa: [
        ["売却は反映されますか？",
         "はい、売買はすべて処理されます。ただし売却そのものでは収益率は変わりません。売却は保有株を時価で現金に換えるだけなので、直前と直後でポートフォリオの価値は同じです（手数料を除く）。それまでに得た利益はそのまま確定されます。"],
        ["売却したら、その収益率は維持されますか？",
         "はい。積み上げた収益率は保たれ、売却でリセットされることはありません。以降は現金が動かなくなるだけです。遊んでいる現金の日次収益は0%なので、買い直すまでは順位を保ちつつ、それ以上は伸びなくなります。"],
        ["では何がスコアを動かすのですか？",
         "保有資産の価値が日々どう変わるかだけです。株価と配当です。売買は現金と株の間で資金を組み替えるだけで、利益を足したり引いたりはしません。"],
        ["入金や出金は有利になりますか？",
         "いいえ。入金・出金は中立化されます（シンプル・ディーツ法）。現金を足してもスコアは上がりません。全員が投資額ではなく<b>収益率（％）</b>で比較されます。"],
      ],
      formulaLabel: "計算式",
      dailyLbl: "日次",
      dailyFormula: "r = (終値 − 始値 − 資金流入) / (始値 + 資金流入/2)",
      cumLbl: "累積",
      cumFormula: "∏ (1 + rₙ) − 1",
      note: "だからこそ100ユーロの人と1万ユーロの人が対等に競えます。重要なのは金額ではなく割合です。",
    },
    bestOfDay: "本日のベスト",
    recentOps: "最新の取引",
    opBuy: "買い", opSell: "売り",
    marketClosed: "市場は休場",
    gapTitle: "首位と最下位の差",
    winnerOf: ml => ml + "の優勝者",
    lunchNote: "🍽️ ランチをおごる番",
    aiBadge: "AI",
    insightsTitle: "リーグのインサイト",
    aiLive: "自動分析",
    ranking: "順位表",
    rankCols: ["#", "プレイヤー", "累積%", "前日比%", "開始"],
    dailyTitle: ml => "🏅 デイリー王者 · " + ml,
    dailyCols: ["日付", "王者", "当日%"],
    leagueWallet: "リーグのポートフォリオ",
    walletsTitle: "プレイヤー別ポートフォリオ",
    cumTitle: "累積リターン · 直近30日",
    cumChartAria: "プレイヤー別の累積リターン推移",
    dailyDetailTitle: "日次詳細 · 直近30日",
    detailAria: "詳細",
    footer: "日次リターンはシンプルDietz法（入出金は損益に含めない）、累積は幾何連鎖" +
      "（時間加重収益率）。データ：暗号化されたRevolut明細 · Yahoo Financeの終値 · " +
      "ロゴは <a href=\\"https://logo.dev\\" target=\\"_blank\\" rel=\\"noopener noreferrer\\">Logo.dev</a>。",
    pp: "\\u00a0pp",
    assets: n => "銘柄",
    others: "その他",
    donutAria: "重み付けによるポートフォリオ内訳",
    allocInsight: (tk, w) => "📊 最大保有 · " + tk +
      ' <span class="muted">· 合計の' + w + "</span>",
    walletTop: (tk, w) => "最大 · " + tk + " " + w,
    noPlayers: "データのあるプレイヤーはまだいません",
    noPlayersDot: "データのあるプレイヤーはまだいません。",
    detailColsFull: ["日付","開始","終了","外部フロー","当日損益","当日%","累積%"],
    detailColsSimple: ["日付","当日%","累積%"],
    buy: "買う", sell: "売る",
    recBuckets: ["強い買い","買い","中立","売り","強い売り"],
    analystRec: "アナリスト評価",
    analysts: n => n + "名のアナリスト",
    avg: v => "平均 " + v + "/5",
    priceTarget: m => "🎯 目標株価 " + m,
    rangeLabel: (lo, hi) => "· レンジ " + lo + "–" + hi,
    relatedTickers: "関連銘柄",
    nextBuy: "買い", nextTrim: "削減",
    nextTitle: (tk, buy) => buy ? tk + "を買い増し" : tk + "を削減",
    consensusBit: l => "コンセンサス " + l,
    targetBit: pct => "目標 " + pct,
    ofPortfolio: w => "ポートフォリオの" + w,
    nextDisclaimer: "💡 アナリストのコンセンサス（Yahoo Finance）に基づく参考ステップ。" +
      "投資助言ではありません。",
    close: "閉じる",
    weightInLeague: "リーグ内比率",
    heldBy: "保有者",
    playersCount: n => n + "名",
    variation: "変動",
    tradeOnRevolut: "Revolutで取引",
    revNote: tk => "Revolutアプリで" + tk + "の詳細を開いて売買。",
    priceRange: (a, b) => "価格 · " + a + " → " + b,
    whoHasIt: "保有者",
    news: "ニュース",
    tickerNote: 'ロゴ：<a href="https://logo.dev" target="_blank" rel="noopener noreferrer">logo.dev</a> · ' +
      "株価とアナリスト評価：Yahoo Finance · 参考情報であり投資助言ではありません。",
    since: d => d + "から",
    nextStep: "次の一手",
    cumPct: "累積%",
    bestDayTile: "最高の日",
    worstDayTile: "最悪の日",
    lastDayPct: "前日比%",
    streak: "連続",
    streakLabel: (sign, n) => sign > 0 ? "連続プラス" : (sign < 0 ? "連続マイナス" : "連続"),
    sessions: "取引日数",
    cumLastN: n => "累積リターン · 直近" + n + "日",
    portfolioCount: n => "ポートフォリオ（" + n + "銘柄）",
    recentSessions: "直近の取引日",
    portfolioNews: "ポートフォリオのニュース",
    points: v => Math.abs(v).toFixed(2) + NBSP + "ポイント",
    ins: {
      leaderFire: (a, g, b) => a + "が絶好調。" + b + "に" + g + "の差。",
      leaderPullAway: a => a + "がトップで差を広げている。",
      leaderLeads: (a, p) => a + "が累積" + p + "でリーグ首位。",
      leaderHelm: a => a + "が主導権を握って離さない。",
      leaderUnstoppable: (a, p) => "今日は" + a + "を止められない。当日" + p + "。",
      leaderPerfect: (a, p) => a + "にとって完璧な一日。当日ベストも記録（" + p + "）。",
      leaderGreenStreak: (a, s) => a + "が" + s + "日連続でプラス。",
      raceFinish: (a, g, b) => "これがレースなら" + a + "はゴールが見えている。" + b + "に" + g + "。",
      overallGap: (a, b, g) => a + "から" + b + "まで総合で" + g + "の差。",
      leaderDefends: (a, b) => a + "がリードを守り、" + b + "が背後から追う。",
      pulse: (a, b) => a + "と" + b + "の競り合いがリーグを盛り上げる。",
      bestSession: (a, p) => a + "がリーグ最高の当日成績：" + p + "。",
      worstDrop: (a, p) => a + "が当日最大の下げ：" + p + "。",
      allRed: () => "忘れたい一日。リーグ全員が今日マイナスで終了。",
      allGreen: () => "追い風。リーグ全員が今日プラスで終了。",
      surprise: (a, p) => a + "が本日のサプライズ。" + p + "の急騰。",
      deflate: (a, p) => a + "が本日失速：当日" + p + "。",
      backToGreen: (a, p) => a + "が不調を脱してプラス回復：" + p + "。",
      duelTop: (a, b, g) => "首位争い：" + a + "と" + b + "の差はわずか" + g + "。",
      photoFinish: (a, b, g) => a + "と" + b + "の大接戦：差は" + g + "。",
      cutsGround: (lo, up, g) => lo + "が" + up + "を追い上げ：本日" + g + "上回る。",
      redStreak: (a, s) => a + "が" + s + "日連続でマイナス。巻き返しの時。",
      holdsFirm: (a, s) => a + "が持ちこたえる：" + s + "日連続プラス。",
      onARoll: (a, g) => a + "が好調：期間開始から" + g + "。",
      sharp: (a, g, k) => a + "が絶好調：直近" + k + "日中" + g + "日プラス。",
      needsReact: (a, p) => a + "は立て直しが必要：累積" + p + "。",
      signsOfLife: (a, p) => a + "が最下位から反撃：本日" + p + "。",
      bottomEarly: a => a + "が最下位だが、リーグは始まったばかり。",
      rollercoaster: (a, g) => a + "はジェットコースター状態：期間中" + g + "の変動。",
      allIn: (a, tk) => a + "は" + tk + "に全賭け：ポートフォリオの100%。",
      concentrates: (a, w, tk) => a + "はリスク集中：" + tk + "に" + w + "。",
      mostDiversified: (a, n) => a + "が最も分散：" + n + "銘柄保有。",
      leagueLoaded: (tk, w) => "リーグ全体が" + tk + "を保有：合計の" + w + "。",
    },
  },
};
const T = I18N[LANG];

// ---- textos estáticos: se aplican por atributos data-i18n ----
(() => {
  document.querySelectorAll("[data-i18n]").forEach(el => {
    const v = T[el.dataset.i18n]; if (v != null) el.textContent = v;
  });
  document.querySelectorAll("[data-i18n-html]").forEach(el => {
    const v = T[el.dataset.i18nHtml]; if (v != null) el.innerHTML = v;
  });
  document.querySelectorAll("[data-i18n-aria]").forEach(el => {
    const v = T[el.dataset.i18nAria]; if (v != null) el.setAttribute("aria-label", v);
  });
  document.querySelectorAll("[data-i18n-title]").forEach(el => {
    const v = T[el.dataset.i18nTitle];
    if (v != null) { el.title = v; el.setAttribute("aria-label", v); }
  });
  const eb = document.getElementById("eyebrow");
  if (eb) eb.textContent = T.eyebrow;
  // título de la pestaña y de la app instalada según el idioma
  document.title = "🏆 " + T.appTitle;
  const titleMeta = document.getElementById("app-title-meta");
  if (titleMeta) titleMeta.setAttribute("content", T.appTitle);
  // el nombre de la app instalada (Android) sale del manifest: en japonés se
  // apunta a un manifest propio con el nombre traducido
  if (LANG === "ja") {
    const ml = document.getElementById("manifest-link");
    if (ml) ml.setAttribute("href", "manifest-ja.webmanifest");
  }
})();

// ---- toggle de idioma (reemplaza al botón de refresco): guarda la ----
// preferencia por dispositivo en localStorage y recarga para repintar todo.
(() => {
  const btn = document.getElementById("lang-btn");
  if (!btn) return;
  const label = document.getElementById("lang-label");
  if (label) label.textContent = T.langBtnLabel;
  btn.title = T.langBtnAria;
  btn.setAttribute("aria-label", T.langBtnAria);
  btn.addEventListener("click", () => {
    const next = LANG === "ja" ? "en" : "ja";
    try { localStorage.setItem("lang", next); } catch (e) {}
    location.reload();
  });
})();

// ---- banners promocionales (solo japonés) ---------------------------
// Anuncios ficticios al estilo de los folletos japoneses, intercalados
// entre los widgets. Enlazan a webs reales de Japón y se abren en una
// pestaña nueva; la etiqueta «広告» (publicidad) deja claro que son
// anuncios. Solo se pintan cuando la interfaz está en japonés.
(() => {
  if (LANG !== "ja") return;
  const wrap = document.getElementById("widgets");
  if (!wrap) return;
  const mk = (b) => {
    const a = document.createElement("a");
    a.className = "jp-banner " + b.cls;
    a.href = b.href;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.setAttribute("aria-label", "広告：" + b.aria);
    a.innerHTML =
      '<span class="bicon" aria-hidden="true">' + b.icon + "</span>" +
      '<span class="btext">' +
        '<span class="btop">' + b.top + "</span>" +
        '<span class="bmain">' + b.main + "</span>" +
        '<span class="btag">広告</span>' +
      "</span>" +
      '<span class="barrow" aria-hidden="true">↗</span>';
    return a;
  };
  const after = (node, el) => {
    if (node && node.parentNode) node.parentNode.insertBefore(el, node.nextSibling);
  };
  // Repartidos hacia abajo y bien espaciados: debajo del bloque de
  // widgets, tras el ranking y tras la gráfica acumulada.
  const closestCard = (id) => {
    const el = document.getElementById(id);
    return el ? el.closest(".card") : null;
  };
  const rankingCard = closestCard("ranking");
  const chartCard = closestCard("chart");
  after(wrap, mk({
    cls: "jp-b1", icon: "🐧", top: "パート・アルバイト",
    main: '<span class="bhi">採用情報</span>', aria: "ドン・キホーテ 採用情報",
    href: "https://www.donki.com/",
  }));
  after(rankingCard, mk({
    cls: "jp-b2", icon: "🐸", top: "当店のお得情報をいち早くお届け！",
    main: "シュフーチラシアプリ", aria: "シュフー チラシアプリ",
    href: "https://www.shufoo.net/",
  }));
  after(chartCard, mk({
    cls: "jp-b3", icon: "📈", top: "日本株・米国株の取引はこちら",
    main: "楽天証券", aria: "楽天証券",
    href: "https://www.rakuten-sec.co.jp/",
  }));
})();

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
    const body = encodeURIComponent(T.mailBody);
    link.href = "mailto:ligatrader26@gmail.com?subject=" + subject + "&body=" + body;
  };
  setHref();
  link.addEventListener("click", setHref);
})();
const SLOTS = ["--s1","--s2","--s3","--s4","--s5","--s6","--s7","--s8"];
const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const colorOf = p => css(SLOTS[p.slot % SLOTS.length]);
const fmtPct = v => (v > 0 ? "+" : "") + v.toFixed(2) + "%";
const fmtDate = iso => { const [y,m,d] = iso.split("-"); return d + "/" + m + "/" + y.slice(2); };
const money = v => "$" + Number(v).toLocaleString("en-US", {minimumFractionDigits: 2, maximumFractionDigits: 2});
const lastOf = p => p.days[p.days.length - 1];

// ---- índices para las vistas de detalle (ticker / jugador) ----
const TICKERS = {}; (DATA.tickers || []).forEach(t => TICKERS[t.ticker] = t);
const PLAYERS = {}; DATA.players.forEach(p => PLAYERS[p.id] = p);

// ---- clasificación (ordenada por acumulado; el color sigue al jugador) ----
const ranked = [...DATA.players].sort((a, b) => lastOf(b).cum - lastOf(a).cum);
const MEDALS = ["🥇","🥈","🥉"];
{
  const t = document.getElementById("ranking");
  const mk = (tag, cls, text) => { const el = document.createElement(tag);
    if (cls) el.className = cls; if (text !== undefined) el.textContent = text; return el; };
  const head = t.insertRow();
  T.rankCols.forEach((h, i) => {
    const th = document.createElement("th");
    th.textContent = h; if (i === 1) th.className = "name"; head.appendChild(th);
  });
  ranked.forEach((p, i) => {
    const last = lastOf(p);
    const tr = t.insertRow();
    tr.classList.add("clk"); tr.dataset.player = p.id;
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
  document.getElementById("pending").textContent = T.pendingText(names);
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
  document.getElementById("hero-spark").innerHTML =
    sparkSVG(leader.days.map(d => d.cum), lc.cum >= 0 ? upC : downC, "hero", {baseline0: true});

  // mejor del día (los fines de semana la última jornada ya es la del viernes;
  // si hay empate en el % del día, desempata la rentabilidad acumulada)
  const best = [...DATA.players].sort((a, b) =>
    (lastOf(b).day - lastOf(a).day) || (lastOf(b).cum - lastOf(a).cum))[0];
  const bd = lastOf(best);
  const bestCard = document.getElementById("best-card");
  const bDate = document.getElementById("best-date");
  const bv = document.getElementById("best-val");
  const bn = document.getElementById("best-name");
  // Si todos los jugadores empatan a 0 en la jornada, el «mejor del día» no
  // aporta nada (sería alguien con +0,00%): se oculta el widget y la diferencia
  // 1º–último ocupa toda la fila.
  const allZeroDay = DATA.players.every(p => Math.abs(lastOf(p).day) < 0.005);
  if (allZeroDay) {
    bestCard.style.display = "none";
    document.querySelector(".wrow").style.gridTemplateColumns = "1fr";
  } else {
    bestCard.style.display = "";
    // El mejor del día perdura toda la tarde y noche hasta la medianoche de
    // Madrid: solo se muestra «mercado cerrado» en la madrugada/mañana de un
    // día laborable, antes de que abra el mercado de EE. UU. (~15:30 en Madrid)
    // y mientras no haya jornada de hoy. Todo se calcula en hora de Madrid para
    // que el corte sea exactamente la medianoche local (con DST correcto). Los
    // fines de semana y tras el cierre —con la jornada del día ya publicada— se
    // sigue mostrando el mejor.
    const mp = new Intl.DateTimeFormat("en-GB", {
      timeZone: "Europe/Madrid", weekday: "short",
      year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit", hourCycle: "h23",
    }).formatToParts(new Date());
    const gp = t => (mp.find(x => x.type === t) || {}).value;
    const madridDate = gp("year") + "-" + gp("month") + "-" + gp("day");
    const isWeekday = gp("weekday") !== "Sat" && gp("weekday") !== "Sun";
    const hh = +gp("hour"), mm = +gp("minute");
    const preOpen = hh < 15 || (hh === 15 && mm < 30);
    const marketClosed = isWeekday && preOpen && bd.date !== madridDate;
    if (marketClosed) {
      bDate.textContent = "";
      bv.textContent = "🚧"; bv.className = "num closed";
      bn.textContent = T.marketClosed;
    } else {
      bDate.textContent = " · " + bd.date.slice(5).split("-").reverse().join("/");
      bv.textContent = fmtPct(bd.day); bv.className = "num " + (bd.day >= 0 ? "pos" : "neg");
      bn.innerHTML = '<span class="medal">🥇</span>';
      bn.appendChild(document.createTextNode(best.name));
    }
  }

  // diferencia 1º - último
  const gapCard = document.getElementById("gap-card");
  if (ranked.length < 2) {
    gapCard.style.display = "none";
    document.querySelector(".wrow").style.gridTemplateColumns = "1fr";
    return;
  }
  const last = ranked[ranked.length - 1];
  const gap = lastOf(ranked[0]).cum - lastOf(last).cum;
  document.getElementById("gap-val").textContent = "+" + gap.toFixed(2) + T.pp;
  document.getElementById("gap-top").textContent = "🥇 " + ranked[0].name + " · " + fmtPct(lastOf(ranked[0]).cum);
  document.getElementById("gap-bot").textContent = last.name + " · " + fmtPct(lastOf(last).cum);
}
paintWidgets();

// ---- widgets «mejor del mes»: este mes y el mes pasado (si hay datos) ----
function paintMonthly() {
  const m = DATA.monthly || {};
  const upC = css("--up"), downC = css("--down");
  const paint = (info, key, spark0) => {
    const card = document.getElementById(key + "-card");
    if (!info) { card.style.display = "none"; return false; }
    card.style.display = "";
    document.getElementById(key + "-label").textContent =
      T.winnerOf(monthLabel(info.month, info.month_year));
    const val = document.getElementById(key + "-val");
    val.textContent = fmtPct(info.value);
    val.className = "num " + (info.value >= 0 ? "pos" : "neg");
    document.getElementById(key + "-player").textContent = info.name;
    const note = document.getElementById(key + "-note");
    if (note) note.textContent = T.lunchNote;
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

// ---- campeón de cada día del mes actual (mayor % del día) ----
function paintDaily() {
  const dw = DATA.dailyWinners || {};
  const rows = dw.rows || [];
  const card = document.getElementById("daily-card");
  if (!rows.length) { card.style.display = "none"; return; }
  card.style.display = "";
  document.getElementById("daily-title").textContent =
    T.dailyTitle(monthLabel(dw.month, dw.month_year));
  const t = document.getElementById("daily");
  t.innerHTML = "";
  const head = t.insertRow();
  T.dailyCols.forEach((h, i) => {
    const th = document.createElement("th");
    th.textContent = h; if (i === 1) th.className = "name"; head.appendChild(th);
  });
  const slotColor = s => css(SLOTS[s % SLOTS.length]);
  rows.forEach(r => {
    const tr = t.insertRow();
    const fecha = tr.insertCell(); fecha.textContent = fmtDate(r.date);
    const name = tr.insertCell(); name.className = "name";
    name.appendChild(document.createTextNode("🏅 "));
    if (r.slot !== null && r.slot !== undefined) {
      const key = document.createElement("span");
      key.className = "key"; key.style.background = slotColor(r.slot);
      name.appendChild(key);
    }
    name.appendChild(document.createTextNode(r.names.join(", ")));
    const val = tr.insertCell();
    val.className = r.value >= 0 ? "pos" : "neg";
    val.textContent = fmtPct(r.value);
  });
}
paintDaily();

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
  return all.slice(0, 5).concat([{ticker: T.others, w: Math.round(rest * 100) / 100, other: true}]);
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
        'font-size="10.5">' + T.assets(count) + '</text>'
    : "";
  return '<svg class="donut" width="' + S + '" height="' + S + '" viewBox="0 0 ' + S + ' ' + S +
    '" role="img" aria-label="' + T.donutAria + '">' +
    '<g transform="rotate(-90 ' + cx + ' ' + cy + ')">' + segs + '</g>' + center + '</svg>';
}
function donutLegendHTML(items) {
  return '<ul class="donut-legend">' + items.map(x => {
    const col = x.other ? css("--muted") : badgeColor(x.ticker);
    const openable = !x.other && TICKERS[x.ticker];
    const attrs = openable ? ' class="dl clk" data-ticker="' + x.ticker + '"' : ' class="dl"';
    return '<li' + attrs + '><span class="dot" style="background:' + col + '"></span>' +
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
    T.allocInsight(top.ticker, fmtW(top.w));
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
    const head = document.createElement("div"); head.className = "whead clk";
    head.dataset.player = p.id;
    const key = document.createElement("span"); key.className = "key";
    key.style.background = colorOf(p);
    head.appendChild(key); head.appendChild(document.createTextNode(p.name));
    const top = document.createElement("span"); top.className = "top";
    top.textContent = T.walletTop(p.holdings[0].ticker, fmtW(p.holdings[0].w));
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
  const lastp = p => p.days[p.days.length - 1];
  const ranked = [...ps].sort((a, b) => lastp(b).cum - lastp(a).cum);
  const byDay = [...ps].sort((a, b) => lastp(b).day - lastp(a).day);
  const n = ps.length;
  const leader = ranked[0], second = ranked[1], tail = ranked[n - 1];
  const bestDay = byDay[0], worstDay = byDay[n - 1];
  const who = p => '<b style="color:' + colorOf(p) + '">' + p.name + '</b>';
  const pts = v => T.points(v);
  const I = T.ins;
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
      add(9.5, "🔥", I.leaderFire(who(leader), pts(g), who(second)));
    if (g > 3)
      add(6.7, "🧱", I.leaderPullAway(who(leader)));
  }
  add(6.0, lastp(leader).cum >= 0 ? "👑" : "🏳️",
    I.leaderLeads(who(leader), fmtPct(lastp(leader).cum)));
  add(4.6, "🧭", I.leaderHelm(who(leader)));
  if (lastp(leader).day > 0)
    add(6.9, "🛰️", I.leaderUnstoppable(who(leader), fmtPct(lastp(leader).day)));
  if (leader === bestDay && lastp(leader).day > 0)
    add(8.5, "🚀", I.leaderPerfect(who(leader), fmtPct(lastp(leader).day)));
  { const s = streak(leader, true); if (s >= 2)
    add(7.0, "📈", I.leaderGreenStreak(who(leader), s)); }
  if (n >= 2) {
    const g = lastp(leader).cum - lastp(tail).cum;
    if (g > 5)
      add(6.5, "🏁", I.raceFinish(who(leader), pts(g), who(tail)));
    add(4.8, "📐", I.overallGap(who(leader), who(tail), pts(g)));
    add(4.4, "🛡️", I.leaderDefends(who(leader), who(tail)));
    add(4.2, "🎙️", I.pulse(who(leader), who(second)));
  }

  // ---- movimientos del día ----
  if (bestDay && lastp(bestDay).day > 0)
    add(7.5, "⚡", I.bestSession(who(bestDay), fmtPct(lastp(bestDay).day)));
  if (n >= 2 && lastp(worstDay).day < 0)
    add(6.5, "🧊", I.worstDrop(who(worstDay), fmtPct(lastp(worstDay).day)));
  if (n >= 2 && allNeg)
    add(7.2, "📉", I.allRed());
  if (n >= 2 && allPos)
    add(7.2, "🟢", I.allGreen());
  ps.forEach(p => { if (p !== leader && lastp(p).day >= 2)
    add(6.6, "✨", I.surprise(who(p), fmtPct(lastp(p).day))); });
  ps.forEach(p => { if (p !== worstDay && lastp(p).day <= -2)
    add(5.6, "🪂", I.deflate(who(p), fmtPct(lastp(p).day))); });
  ps.forEach(p => { if (recovered(p))
    add(5.7, "🌤️", I.backToGreen(who(p), fmtPct(lastp(p).day))); });

  // ---- duelos y adelantamientos ----
  if (n >= 2) { const g = lastp(ranked[0]).cum - lastp(ranked[1]).cum;
    if (g >= 0 && g < 1.5)
      add(8.0, "🥊", I.duelTop(who(ranked[0]), who(ranked[1]), pts(g))); }
  for (let i = 0; i < n - 1; i++) { const g = lastp(ranked[i]).cum - lastp(ranked[i + 1]).cum;
    if (g >= 0 && g < 0.3)
      add(7.0, "📸", I.photoFinish(who(ranked[i]), who(ranked[i + 1]), pts(g))); }
  for (let i = 0; i < n - 1; i++) { const up = ranked[i], lo = ranked[i + 1];
    const g = lastp(up).cum - lastp(lo).cum, diff = lastp(lo).day - lastp(up).day;
    if (diff > 0.5 && g < 6)
      add(6.8, "🔀", I.cutsGround(who(lo), who(up), pts(diff))); }

  // ---- rachas, remontadas y momentum ----
  ps.forEach(p => { const s = streak(p, false); if (s >= 2)
    add(6.0 + s * 0.2, "🌧️", I.redStreak(who(p), s)); });
  ps.forEach(p => { if (p === leader) return; const s = streak(p, true); if (s >= 3)
    add(6.4, "🔋", I.holdsFirm(who(p), s)); });
  ps.forEach(p => { const d = windowDelta(p); if (d > 3)
    add(6.0 + Math.min(d, 10) / 10, "🛫", I.onARoll(who(p), pts(d))); });
  ps.forEach(p => { const k = Math.min(5, p.days.length); if (k >= 4 && greenCount(p, k) >= 4)
    add(5.8, "✅", I.sharp(who(p), greenCount(p, k), k)); });
  ps.forEach(p => { if (lastp(p).cum <= -2)
    add(5.2, "🧯", I.needsReact(who(p), fmtPct(lastp(p).cum))); });
  if (n >= 2 && lastp(tail).day > 0)
    add(5.5, "🌱", I.signsOfLife(who(tail), fmtPct(lastp(tail).day)));
  if (n >= 2)
    add(4.0, "⏳", I.bottomEarly(who(tail)));
  ps.forEach(p => { if (p.days.length >= 3 && range(p) >= 6)
    add(5.2, "🎢", I.rollercoaster(who(p), pts(range(p)))); });

  // ---- carteras (solo pesos, sin importes) ----
  ps.forEach(p => { const h = p.holdings; if (!h || !h.length) return;
    if (h.length === 1)
      add(6.2, "🎯", I.allIn(who(p), h[0].ticker));
    else if (h[0].w >= 40)
      add(6.0, "⚠️", I.concentrates(who(p), fmtW(h[0].w), h[0].ticker)); });
  { const withH = ps.filter(p => p.holdings && p.holdings.length);
    if (withH.length) {
      const div = withH.slice().sort((a, b) => b.holdings.length - a.holdings.length)[0];
      if (div.holdings.length >= 4)
        add(5.4, "🧩", I.mostDiversified(who(div), div.holdings.length)); } }
  if (DATA.allocation && DATA.allocation.length) { const top = DATA.allocation[0];
    if (top.w >= 20)
      add(5.0, "📊", I.leagueLoaded(top.ticker, fmtW(top.w))); }

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
    t.textContent = T.noPlayers;
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
    s.className = "clk"; s.dataset.player = p.id;
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
    const cols = p.amounts ? T.detailColsFull : T.detailColsSimple;
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
  if (!ranked.length) box.textContent = T.noPlayersDot;
}

// ==== vistas de detalle: ticker y jugador ==============================
// Overlay que se rellena en cliente desde los datos ya embebidos. Los logos se
// piden a logo.dev por dominio con respaldo a un monograma de color (si el
// servicio no responde), y las noticias son enlaces de búsqueda por símbolo:
// la página sigue siendo estática y no expone importes ni operaciones.
const modal = document.getElementById("modal");
const modalBody = document.getElementById("modal-body");
const sheet = document.getElementById("sheet");
const h = (tag, cls, html) => { const e = document.createElement(tag);
  if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; };

function monoEl(text, size, bg) {
  const m = document.createElement("span");
  m.className = "mono";
  m.style.width = m.style.height = size + "px";
  m.style.fontSize = Math.round(size * 0.4) + "px";
  m.style.background = bg;
  m.textContent = (text || "?").slice(0, 2).toUpperCase();
  return m;
}
// Token publicable de logo.dev (pensado para el frontend; puede ir en el HTML).
const LOGO_TOKEN = "pk_cgMPtdfzT5GGEORKN4rMDA";
// Logo de empresa (por ticker) con respaldo a monograma si la imagen falla.
function tickerLogoEl(t, size) {
  const bg = badgeColor(t.ticker);
  if (!t.ticker) return monoEl(t.ticker, size, bg);
  const img = document.createElement("img");
  img.className = "logo"; img.width = img.height = size; img.alt = "";
  img.loading = "lazy"; img.referrerPolicy = "no-referrer";
  img.src = "https://img.logo.dev/ticker/" + encodeURIComponent(t.ticker) +
    "?token=" + LOGO_TOKEN + "&size=" + size + "&retina=true&format=png";
  img.onerror = () => img.replaceWith(monoEl(t.ticker, size, bg));
  return img;
}

// ---- últimas operaciones de la liga (fecha · compra/venta · ticker · jugador) ----
// Va aquí, tras definir ``h`` y ``tickerLogoEl``, porque los usa al pintar. No
// expone importes: solo qué se compró/vendió, de qué valor y qué día. El ticker
// abre su ficha y el jugador la suya (si son abribles).
function paintOperations() {
  const ops = DATA.operations || [];
  const card = document.getElementById("ops-card");
  if (!ops.length) { card.style.display = "none"; return; }
  card.style.display = "";
  const box = document.getElementById("ops-list");
  box.innerHTML = "";
  ops.forEach(o => {
    const row = h("div", "op-row");

    const tk = h("span", "op-tk");
    if (TICKERS[o.ticker]) { tk.classList.add("clk"); tk.dataset.ticker = o.ticker; }
    tk.appendChild(tickerLogoEl({ticker: o.ticker}, 30));
    const sym = h("span", "sym"); sym.textContent = o.ticker;
    tk.appendChild(sym);
    row.appendChild(tk);

    const act = h("span", "op-act " + (o.kind === "BUY" ? "buy" : "sell"));
    act.textContent = o.kind === "BUY" ? T.opBuy : T.opSell;
    row.appendChild(act);

    const name = h("span", "op-name");
    if (o.id && PLAYERS[o.id]) { name.classList.add("clk"); name.dataset.player = o.id; }
    const key = h("span", "key"); key.style.background = css(SLOTS[o.slot % SLOTS.length]);
    name.appendChild(key);
    const nm = h("span", "nm"); nm.textContent = o.name;
    name.appendChild(nm);
    row.appendChild(name);

    row.appendChild(h("span", "op-date", fmtDate(o.date)));
    box.appendChild(row);
  });
}
paintOperations();

function newsRow(sym) {
  const q = encodeURIComponent(sym + " stock");
  const links = [
    ["Yahoo Finance", "https://finance.yahoo.com/quote/" + encodeURIComponent(sym)],
    ["Google News", "https://news.google.com/search?q=" + q],
    ["Finviz", "https://finviz.com/quote.ashx?t=" + encodeURIComponent(sym)],
  ];
  const box = h("div", "news");
  links.forEach(([label, href]) => {
    const a = document.createElement("a");
    a.href = href; a.target = "_blank"; a.rel = "noopener noreferrer";
    a.innerHTML = label + ' <span class="ext">↗</span>';
    box.appendChild(a);
  });
  return box;
}
// Botones «Comprar»/«Vender» que abren la app de Revolut en el detalle del
// valor. Ambos llevan al mismo detalle; desde ahí se elige comprar o vender.
function revolutRow(sym) {
  const href = "https://revolut.com/app/trading/stocks/" + encodeURIComponent(sym);
  const box = h("div", "revolut");
  [[T.buy, "buy", "▲"], [T.sell, "sell", "▼"]].forEach(([label, cls, ico]) => {
    const a = document.createElement("a");
    a.href = href;
    a.className = "rev-btn " + cls;
    a.innerHTML = '<span class="ic">' + ico + "</span>" + label;
    box.appendChild(a);
  });
  return box;
}
function sectionEl(title, node) {
  const s = h("div", "msec");
  s.appendChild(h("div", "h", title));
  s.appendChild(node);
  return s;
}
function tileEl(k, v, cls) {
  const t = h("div", "tile");
  t.appendChild(h("div", "k", k));
  t.appendChild(h("div", "v" + (cls ? " " + cls : ""), v));
  return t;
}

// Reparto de opiniones: buckets de compra→venta con color propio (verde→rojo),
// independiente del azul/rosa de subida/bajada de la liga.
const REC_BUCKETS = [
  ["strongBuy", T.recBuckets[0], "#15a34a"],
  ["buy", T.recBuckets[1], "#22c55e"],
  ["hold", T.recBuckets[2], "#9aa0ac"],
  ["sell", T.recBuckets[3], "#f59e0b"],
  ["strongSell", T.recBuckets[4], "#ef4444"],
];
// El análisis (label) llega en español desde el backend (derivado de la media
// de recomendación); se traduce al idioma activo mapeando a los buckets.
const REC_LABEL_MAP = {"Compra fuerte": 0, "Comprar": 1, "Mantener": 2, "Vender": 3, "Venta fuerte": 4};
const recLabel = l => { const i = REC_LABEL_MAP[l]; return i == null ? l : T.recBuckets[i]; };
function analystSectionEl(a) {
  const wrap = h("div", "msec");
  wrap.appendChild(h("div", "h", T.analystRec +
    (a.asOf ? ' <span style="color:var(--muted);font-weight:600">· ' + fmtDate(a.asOf) + "</span>" : "")));
  const cons = h("div", "consensus");
  if (a.label) cons.appendChild(h("span", "cbadge " + (a.tone || "neutral"), recLabel(a.label)));
  const meta = [];
  if (a.count) meta.push(T.analysts(a.count));
  if (a.mean != null) meta.push(T.avg(a.mean.toFixed(1)));
  if (meta.length) cons.appendChild(h("span", "cmeta", meta.join(" · ")));
  wrap.appendChild(cons);
  if (a.dist) {
    const total = REC_BUCKETS.reduce((s, [k]) => s + (a.dist[k] || 0), 0);
    if (total > 0) {
      const bar = h("div", "distbar");
      const leg = h("div", "distlegend");
      REC_BUCKETS.forEach(([k, lbl, col]) => {
        const n = a.dist[k] || 0; if (!n) return;
        const seg = document.createElement("span");
        seg.style.background = col; seg.style.width = (n / total * 100) + "%";
        seg.title = lbl + ": " + n; bar.appendChild(seg);
        const item = h("span", "k");
        const sw = document.createElement("span"); sw.className = "sw"; sw.style.background = col;
        item.appendChild(sw); item.appendChild(document.createTextNode(lbl + " " + n));
        leg.appendChild(item);
      });
      wrap.appendChild(bar); wrap.appendChild(leg);
    }
  }
  if (a.target != null) {
    const t = h("div", "target");
    let html = T.priceTarget(money(a.target));
    if (a.upside != null)
      html += ' <span class="up ' + (a.upside >= 0 ? "pos" : "neg") + '">(' + fmtPct(a.upside) + ")</span>";
    if (a.targetLow != null && a.targetHigh != null)
      html += ' <span class="rng">' + T.rangeLabel(money(a.targetLow), money(a.targetHigh)) + "</span>";
    t.innerHTML = html;
    wrap.appendChild(t);
  }
  return wrap;
}
function peersSectionEl(peers) {
  const chips = h("div", "chips");
  peers.forEach(p => {
    const known = !!TICKERS[p.ticker];
    let chip;
    if (known) { chip = h("div", "chip-tk clk"); chip.dataset.ticker = p.ticker; }
    else {
      chip = document.createElement("a"); chip.className = "chip-tk";
      chip.href = "https://revolut.com/app/trading/stocks/" + encodeURIComponent(p.ticker);
      chip.target = "_blank"; chip.rel = "noopener noreferrer";
      chip.style.textDecoration = "none"; chip.style.color = "inherit";
    }
    chip.appendChild(tickerLogoEl(p, 22));
    chip.appendChild(document.createTextNode(p.ticker));
    if (!known) chip.appendChild(h("span", "w", "↗"));
    chips.appendChild(chip);
  });
  return sectionEl(T.relatedTickers, chips);
}
function nextStepEl(s) {
  const card = h("div", "nextstep");
  if (TICKERS[s.ticker]) { card.classList.add("clk"); card.dataset.ticker = s.ticker; }
  const isBuy = s.action !== "trim";
  const top = h("div", "top");
  top.appendChild(tickerLogoEl(s, 26));
  top.appendChild(h("span", "act" + (isBuy ? "" : " neg"), isBuy ? T.nextBuy : T.nextTrim));
  top.appendChild(h("span", "ttl", T.nextTitle(s.ticker, isBuy)));
  card.appendChild(top);
  const bits = [];
  if (s.label) bits.push(T.consensusBit(recLabel(s.label)));
  if (s.count) bits.push(T.analysts(s.count));
  if (s.upside != null) bits.push(T.targetBit(fmtPct(s.upside)));
  bits.push(T.ofPortfolio(fmtW(s.w)));
  card.appendChild(h("div", "body", bits.join(" · ")));
  card.appendChild(h("div", "dis", T.nextDisclaimer));
  return card;
}

let closingTimer = null;
function hideModal() {
  clearTimeout(closingTimer);
  modal.classList.remove("open");
  sheet.classList.remove("closing");
  sheet.style.transform = ""; sheet.style.transition = ""; sheet.style.opacity = "";
  modal.setAttribute("aria-hidden", "true");
  document.body.style.overflow = "";
}
function closeModal() {
  if (!modal.classList.contains("open")) return;
  sheet.classList.add("closing");        // desliza la hoja hacia abajo y oculta
  clearTimeout(closingTimer);
  closingTimer = setTimeout(hideModal, 240);
}
function showModal(node) {
  clearTimeout(closingTimer);
  sheet.classList.remove("closing");
  sheet.style.transform = ""; sheet.style.transition = ""; sheet.style.opacity = "";
  modalBody.innerHTML = "";
  const close = h("button", "mclose", "✕");
  close.setAttribute("aria-label", T.close);
  close.addEventListener("click", closeModal);
  node.appendChild(close);               // ✕ fijado arriba a la derecha (absolute)
  modalBody.appendChild(node);
  modal.classList.add("open");
  modal.setAttribute("aria-hidden", "false");
  document.body.style.overflow = "hidden";
  sheet.scrollTop = 0;
}

// ---- cómo se calcula la rentabilidad (interrogante del widget líder) ----
function openLeaderHelp() {
  const c = T.calc;
  const root = document.createElement("div");

  const head = h("div", "mhead");
  const title = h("div", "mtitle");
  title.appendChild(h("div", "t1", c.title));
  title.appendChild(h("div", "t2", c.subtitle));
  head.appendChild(title);
  root.appendChild(head);

  // preguntas y respuestas (la venta, mantener la rentabilidad, los flujos…)
  c.qa.forEach(([q, a]) => {
    root.appendChild(sectionEl(q, h("div", "mtext", a)));
  });

  // fórmulas: rentabilidad diaria (Dietz simple) y acumulada (geométrica)
  const fsec = h("div", "msec");
  fsec.appendChild(h("div", "h", c.formulaLabel));
  const f1 = h("div", "formula");
  f1.appendChild(h("span", "lbl", c.dailyLbl));
  f1.appendChild(document.createTextNode(c.dailyFormula));
  fsec.appendChild(f1);
  const f2 = h("div", "formula");
  f2.appendChild(h("span", "lbl", c.cumLbl));
  f2.appendChild(document.createTextNode(c.cumFormula));
  fsec.appendChild(f2);
  root.appendChild(fsec);

  root.appendChild(h("div", "mnote", c.note));
  showModal(root);
}
const heroHelp = document.getElementById("hero-help");
if (heroHelp) heroHelp.addEventListener("click", openLeaderHelp);

// ---- detalle de ticker ----
function openTicker(sym) {
  const t = TICKERS[sym];
  if (!t) return;
  const upC = css("--up"), downC = css("--down");
  const root = document.createElement("div");

  const head = h("div", "mhead");
  head.appendChild(tickerLogoEl(t, 46));
  const title = h("div", "mtitle");
  const t1 = h("div", "t1");
  t1.appendChild(document.createTextNode(t.ticker));
  if (t.ret != null) {
    const b = h("span", "mbadge" + (t.ret >= 0 ? "" : " neg"), fmtPct(t.ret));
    t1.appendChild(b);
  }
  title.appendChild(t1);
  title.appendChild(h("div", "t2", t.name));
  head.appendChild(title);
  root.appendChild(head);

  const tiles = h("div", "tiles");
  tiles.appendChild(tileEl(T.weightInLeague, fmtW(t.w)));
  tiles.appendChild(tileEl(T.heldBy, T.playersCount(t.holders.length)));
  tiles.appendChild(tileEl(T.variation, t.ret == null ? "—" : fmtPct(t.ret),
    t.ret == null ? "" : (t.ret >= 0 ? "pos" : "neg")));
  root.appendChild(tiles);

  const revSec = sectionEl(T.tradeOnRevolut, revolutRow(t.ticker));
  revSec.appendChild(h("div", "rev-note", T.revNote(t.ticker)));
  root.appendChild(revSec);

  if (t.analyst) root.appendChild(analystSectionEl(t.analyst));

  if (t.prices && t.prices.length >= 2) {
    const vals = t.prices.map(p => p.close);
    const spark = h("div", "mspark", sparkSVG(vals, t.ret >= 0 ? upC : downC, "tk"));
    const from = t.prices[0].date, to = t.prices[t.prices.length - 1].date;
    const sec = sectionEl(T.priceRange(fmtDate(from), fmtDate(to)), spark);
    root.appendChild(sec);
  }

  if (t.holders.length) {
    const list = document.createElement("div");
    t.holders.forEach(hd => {
      const row = h("div", "holder-row clk");
      row.dataset.player = playerIdByName(hd.name) || "";
      const nm = h("span", "nm");
      const key = h("span", "key"); key.style.background = css(SLOTS[hd.slot % SLOTS.length]);
      nm.appendChild(key); nm.appendChild(document.createTextNode(hd.name));
      row.appendChild(nm);
      row.appendChild(h("span", "w", T.ofPortfolio(fmtW(hd.w))));
      list.appendChild(row);
    });
    root.appendChild(sectionEl(T.whoHasIt, list));
  }

  if (t.peers && t.peers.length) root.appendChild(peersSectionEl(t.peers));

  root.appendChild(sectionEl(T.news, newsRow(t.ticker)));
  root.appendChild(h("div", "mnote", T.tickerNote));
  showModal(root);
}

function playerIdByName(name) {
  const p = DATA.players.find(x => x.name === name);
  return p ? p.id : null;
}

// ---- detalle de jugador ----
function openPlayer(pid) {
  const p = PLAYERS[pid];
  if (!p) return;
  const upC = css("--up"), downC = css("--down");
  const days = p.days || [];
  const last = days[days.length - 1] || {cum: 0, day: 0};
  const rankIdx = ranked.findIndex(x => x.id === pid);
  const bestDay = days.reduce((a, d) => d.day > a.day ? d : a, days[0] || {day: 0});
  const worstDay = days.reduce((a, d) => d.day < a.day ? d : a, days[0] || {day: 0});
  let streak = 0, sign = 0;
  for (let i = days.length - 1; i >= 0; i--) {
    const s = Math.sign(days[i].day);
    if (i === days.length - 1) { sign = s; streak = s !== 0 ? 1 : 0; }
    else if (s === sign && s !== 0) streak++;
    else break;
  }
  const root = document.createElement("div");

  const head = h("div", "mhead");
  head.appendChild(monoEl(p.name, 46, colorOf(p)));
  const title = h("div", "mtitle");
  const t1 = h("div", "t1");
  t1.appendChild(document.createTextNode(p.name));
  if (rankIdx >= 0)
    t1.appendChild(h("span", "mbadge rank", (MEDALS[rankIdx] || "#" + (rankIdx + 1))));
  title.appendChild(t1);
  title.appendChild(h("div", "t2", T.since(p.since ? fmtDate(p.since) : (days[0] || {}).date || "")));
  head.appendChild(title);
  root.appendChild(head);

  if (p.suggestion) root.appendChild(sectionEl(T.nextStep, nextStepEl(p.suggestion)));

  const tiles = h("div", "tiles");
  tiles.appendChild(tileEl(T.cumPct, fmtPct(last.cum), last.cum >= 0 ? "pos" : "neg"));
  tiles.appendChild(tileEl(T.bestDayTile, fmtPct(bestDay.day), "pos"));
  tiles.appendChild(tileEl(T.worstDayTile, fmtPct(worstDay.day), worstDay.day < 0 ? "neg" : ""));
  root.appendChild(tiles);

  const tiles2 = h("div", "tiles");
  tiles2.appendChild(tileEl(T.lastDayPct, fmtPct(last.day), last.day >= 0 ? "pos" : "neg"));
  tiles2.appendChild(tileEl(T.streak, String(streak), sign > 0 ? "pos" : (sign < 0 ? "neg" : "")));
  tiles2.children[1].querySelector(".k").textContent = T.streakLabel(sign, streak);
  tiles2.appendChild(tileEl(T.sessions, String(days.length)));
  root.appendChild(tiles2);

  if (days.length >= 2) {
    const spark = h("div", "mspark",
      sparkSVG(days.map(d => d.cum), last.cum >= 0 ? upC : downC, "pl", {baseline0: true}));
    root.appendChild(sectionEl(T.cumLastN(days.length), spark));
  }

  if (p.holdings && p.holdings.length) {
    const chips = h("div", "chips");
    p.holdings.forEach(hh => {
      const meta = TICKERS[hh.ticker] || {ticker: hh.ticker, domain: "", name: hh.ticker};
      const chip = h("div", "chip-tk" + (TICKERS[hh.ticker] ? " clk" : ""));
      if (TICKERS[hh.ticker]) chip.dataset.ticker = hh.ticker;
      chip.appendChild(tickerLogoEl(meta, 22));
      chip.appendChild(document.createTextNode(hh.ticker));
      chip.appendChild(h("span", "w", fmtW(hh.w)));
      chips.appendChild(chip);
    });
    root.appendChild(sectionEl(T.portfolioCount(p.holdings.length), chips));
  }

  const recent = days.slice(-6).reverse();
  if (recent.length) {
    const list = document.createElement("div");
    recent.forEach(d => {
      const row = h("div", "mini-row");
      row.appendChild(h("span", "dt", fmtDate(d.date)));
      row.appendChild(h("span", "v " + (d.day >= 0 ? "pos" : "neg"), fmtPct(d.day)));
      list.appendChild(row);
    });
    root.appendChild(sectionEl(T.recentSessions, list));
  }

  if (p.holdings && p.holdings.length) {
    root.appendChild(sectionEl(T.portfolioNews, newsRow(p.holdings[0].ticker)));
  }
  showModal(root);
}

// ---- apertura por delegación + cierre (backdrop / ✕ / Esc) ----
document.addEventListener("click", ev => {
  const tk = ev.target.closest("[data-ticker]");
  if (tk && tk.dataset.ticker) { openTicker(tk.dataset.ticker); return; }
  const pl = ev.target.closest("[data-player]");
  if (pl && pl.dataset.player) { openPlayer(pl.dataset.player); return; }
});
modal.addEventListener("click", ev => { if (ev.target === modal) closeModal(); });
document.addEventListener("keydown", ev => {
  if (ev.key === "Escape" && modal.classList.contains("open")) closeModal();
});

// ---- arrastrar hacia abajo para cerrar (bottom sheet nativo en móvil) ----
(function () {
  let startY = 0, dy = 0, dragging = false;
  const start = e => {
    if (sheet.scrollTop > 0) { dragging = false; return; }  // deja hacer scroll interno
    startY = e.touches[0].clientY; dy = 0; dragging = true;
    sheet.style.transition = "none";
  };
  const move = e => {
    if (!dragging) return;
    dy = e.touches[0].clientY - startY;
    if (dy <= 0 || sheet.scrollTop > 0) { sheet.style.transform = ""; sheet.style.opacity = ""; return; }
    if (e.cancelable) e.preventDefault();       // captura el gesto, no hace scroll
    sheet.style.transform = "translateY(" + dy + "px)";
    sheet.style.opacity = String(Math.max(0.5, 1 - dy / 640));
  };
  const end = () => {
    if (!dragging) return;
    dragging = false;
    sheet.style.transition = "";
    if (dy > 110) {                             // umbral: continúa el gesto y cierra
      sheet.style.transition = "transform .2s ease-in, opacity .2s ease-in";
      sheet.style.transform = "translateY(100%)"; sheet.style.opacity = "0";
      clearTimeout(closingTimer);
      closingTimer = setTimeout(hideModal, 200);
    } else { sheet.style.transform = ""; sheet.style.opacity = ""; }  // vuelve a su sitio
  };
  sheet.addEventListener("touchstart", start, {passive: true});
  sheet.addEventListener("touchmove", move, {passive: false});
  sheet.addEventListener("touchend", end);
  sheet.addEventListener("touchcancel", end);
  // un toque en la barra de agarre también cierra
  document.querySelector(".grab").addEventListener("click", closeModal);
})();
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


def _ticker_details(
    allocation: dict[str, float] | None,
    holdings: dict[str, dict[str, float]],
    order: dict[str, int],
    names: dict[str, str],
    prices: dict[str, list[tuple]] | None,
    last_days: int,
    analysts: dict[str, dict] | None = None,
) -> list[dict]:
    """Detalle público por ticker para la vista de detalle de la web.

    Para cada valor de la cartera agregada de la liga reúne: nombre y dominio
    (para el logo), peso agregado (%), qué jugadores lo tienen con su peso
    dentro de *su propia* cartera (solo %), y una mini-serie de precio de cierre
    de la ventana visible con su variación. Nada de esto expone importes ni
    operaciones: pesos y precios públicos de mercado.
    """
    weights = _allocation_weights(allocation)
    if not weights:
        return []
    prices = prices or {}
    analysts = analysts or {}
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
        window = raw[-last_days:] if last_days else raw
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
        out.append(entry)
    return out


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
                "month": month,
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


def _daily_winners(computed: list[tuple[Player, list[DayResult]]],
                   year: int, month: int, order: dict[str, int]) -> list[dict]:
    """Ganador de cada día del mes: mayor rentabilidad diaria (con empates).

    Solo cuentan los días de la competición (``day >= COMPETITION_START``). La
    lista sale ordenada de más reciente a más antigua para que el día de hoy
    quede arriba en la tabla.
    """
    by_day: dict[date, list[tuple[str, int, float]]] = {}
    for player, series in computed:
        for r in series:
            if (r.day.year == year and r.day.month == month
                    and r.day >= COMPETITION_START):
                by_day.setdefault(r.day, []).append(
                    (player.display_name, order[player.player_id], r.daily_return))

    out = []
    for day in sorted(by_day, reverse=True):
        best = max(ret for _n, _s, ret in by_day[day])
        winners = sorted((n, s) for n, s, ret in by_day[day] if ret == best)
        out.append({
            "date": day.isoformat(),
            "names": [n for n, _s in winners],
            "slot": winners[0][1] if len(winners) == 1 else None,
            "value": round(best * 100, 2),
        })
    return out


def _drop_weekends(
    computed: list[tuple[Player, list[DayResult]]],
) -> list[tuple[Player, list[DayResult]]]:
    """Elimina sábados y domingos de cada serie.

    Los mercados cierran el fin de semana: no hay competición esos días (la
    rentabilidad diaria sería ~0), así que no deben mostrarse en ninguna vista
    (gráfica, tablas, «mejor del día» ni «campeón de cada día»). El acumulado
    de cada jornada hábil ya es correcto, así que basta con descartar las filas
    del fin de semana sin recomponer nada.
    """
    return [(player, [r for r in series if r.day.weekday() < 5])
            for player, series in computed]


def _recent_operations(computed: list[tuple[Player, list[DayResult]]],
                       order: dict[str, int], limit: int = 3) -> list[dict]:
    """Las últimas ``limit`` operaciones (compras/ventas) de toda la liga.

    Solo compras y ventas de un valor concreto (los ingresos, retiradas,
    dividendos, comisiones y splits no son «operaciones» que interesen al
    widget). No expone importes ni cantidades: solo fecha, jugador, si fue
    compra o venta y el ticker — el mismo nivel de detalle que ya publica la
    web con las carteras por jugador.

    El extracto de Revolut solo trae la fecha (sin hora), así que dentro de un
    mismo día se respeta el orden del CSV (las filas más abajo son las más
    recientes). Se ordena por (fecha, orden en el extracto) de forma
    descendente y se toman las ``limit`` primeras.
    """
    ops: list[tuple[date, int, str, str, int, str, str]] = []
    for player, _series in computed:
        for seq, ev in enumerate(player.events):
            if ev.kind in (BUY, SELL) and ev.ticker:
                ops.append((ev.day, seq, player.player_id,
                            player.display_name, order[player.player_id],
                            ev.kind, ev.ticker))
    ops.sort(key=lambda o: (o[0], o[1]), reverse=True)
    return [{"date": day.isoformat(), "id": pid, "name": name,
             "slot": slot, "kind": kind, "ticker": ticker}
            for day, _seq, pid, name, slot, kind, ticker in ops[:limit]]


def build_payload(computed: list[tuple[Player, list[DayResult]]],
                  last_days: int = 30,
                  pending: list[dict] | None = None,
                  allocation: dict[str, float] | None = None,
                  holdings: dict[str, dict[str, float]] | None = None,
                  prices: dict[str, list[tuple]] | None = None,
                  analysts: dict[str, dict] | None = None,
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
    """
    today = today or date.today()
    holdings = holdings or {}
    analysts = analysts or {}
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
        holdings_w = _allocation_weights(holdings.get(player.player_id))
        entry = {
            "id": player.player_id,
            "name": player.display_name,
            "slot": order[player.player_id],
            "amounts": player.show_amounts,
            "since": series[0].day.isoformat(),
            "days": days,
            "holdings": holdings_w,
        }
        suggestion = _buy_sell_suggestion(holdings_w, analysts)
        if suggestion:
            entry["suggestion"] = suggestion
        players.append(entry)
    return {"players": players, "pending": pending or [],
            "operations": _recent_operations(computed, order),
            "allocation": _allocation_weights(allocation),
            "tickers": _ticker_details(allocation, holdings, order, names,
                                       prices, last_days, analysts),
            "monthly": _monthly_bests(computed, today, order),
            "dailyWinners": {
                "month": today.month,
                "month_year": today.year,
                "rows": _daily_winners(computed, today.year, today.month, order),
            }}


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
    last_days: int = 30,
    pending: list[dict] | None = None,
    allocation: dict[str, float] | None = None,
    holdings: dict[str, dict[str, float]] | None = None,
    prices: dict[str, list[tuple]] | None = None,
    analysts: dict[str, dict] | None = None,
) -> str:
    payload = json.dumps(
        build_payload(computed, last_days=last_days, pending=pending,
                      allocation=allocation, holdings=holdings,
                      prices=prices, analysts=analysts,
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
