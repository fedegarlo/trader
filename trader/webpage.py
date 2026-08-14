"""Genera docs/index.html: dashboard estático para GitHub Pages.

Autocontenido (datos embebidos, sin CDNs): tarjetas tipo widget al estilo
Revolut (fondo aurora, gráficas de área con degradado, tipografía compacta) y,
de primero, la clasificación en formato tabla (1º, 2º, 3º… con la diferencia
de cada jugador respecto al líder, como una parrilla de F1 o una tabla de
liga). El color se asigna a cada jugador por orden alfabético de id
(estable: no cambia si cambia su posición en el ranking).
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, time, timezone

from .players import Player
from .portfolio import CASH_KEY, DayResult
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
  /* japonés: el título es más ancho (kana a cuerpo completo); se reduce y se
     fuerza a una sola línea para que no se parta en dos renglones */
  html[lang="ja"] h1 { font-size: clamp(22px, 6.4vw, 30px); white-space: nowrap; }
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
  /* sin ``min-width: 0`` una tabla ancha estiraría su tarjeta y con ella toda
     la página: así la clasificación se desplaza dentro de su propio ``.overx``. */
  #widgets > * { min-width: 0; }
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
  /* «mercado cerrado»: etiqueta junto al ganador de la última jornada, para
     que se vea que el dato es de la sesión ya cerrada y no de hoy. */
  .closed-tag { flex: none; font-size: 11px; font-weight: 800; letter-spacing: 0.03em;
                text-transform: uppercase; padding: 3px 9px; border-radius: 999px;
                background: var(--surface-2); border: 1px solid var(--hair);
                color: var(--ink-2); }
  .delta { font-size: 15px; font-weight: 700; letter-spacing: -0.01em; }
  /* indicador de líder del primer widget: banda tintada con el color del
     jugador que va en cabeza, su nombre y su rentabilidad acumulada. */
  .leader { display: flex; align-items: center; justify-content: space-between; gap: 12px;
            margin-top: 12px; padding: 12px 15px; border-radius: 18px;
            background: linear-gradient(180deg,
              color-mix(in srgb, var(--lead, var(--accent)) 13%, var(--surface-2)),
              color-mix(in srgb, var(--lead, var(--accent)) 6%, var(--surface-2)));
            border: 1px solid color-mix(in srgb, var(--lead, var(--accent)) 26%, var(--ring)); }
  .lead-l { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
  .lead-r { display: flex; flex-direction: column; align-items: flex-end; gap: 1px; flex: none; }
  .lead-tag { display: inline-flex; align-items: center; gap: 5px; font-size: 10.5px; font-weight: 800;
              letter-spacing: 0.09em; text-transform: uppercase; color: var(--ink-2); }
  .lead-trophy { font-size: 12px; line-height: 1; }
  .lead-name { display: inline-flex; align-items: center; gap: 8px; font-size: 19px; font-weight: 800;
               letter-spacing: -0.02em; min-width: 0; }
  .lead-name > span:last-child { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .lead-name .key { width: 11px; height: 11px; flex: none;
                    box-shadow: 0 0 0 3px color-mix(in srgb, var(--lead, var(--accent)) 22%, transparent); }
  .leader .lval { font-size: clamp(24px, 7vw, 30px); font-weight: 800; letter-spacing: -0.035em;
                  line-height: 1.02; }
  .leader .delta { font-size: 13px; font-weight: 700; }
  @keyframes pulse {
    0% { box-shadow: 0 0 0 0 color-mix(in srgb, currentColor 55%, transparent); }
    70% { box-shadow: 0 0 0 6px transparent; }
    100% { box-shadow: 0 0 0 0 transparent; }
  }
  .wsub { color: var(--ink-2); font-size: 13.5px; font-weight: 600; margin-top: 4px; }
  .bestname { color: var(--ink); font-size: 18px; font-weight: 700; margin-top: 8px; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
  .bestname .medal { font-size: 20px; line-height: 1; }
  .winnername { color: var(--ink); font-size: clamp(20px, 5.5vw, 24px); font-weight: 800;
                letter-spacing: -0.02em; line-height: 1.15; margin-top: 6px;
                display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
  .winnername .trophy { font-size: 22px; line-height: 1; }
  .wsub.muted { color: var(--muted); font-weight: 500; }
  .wsub.treat { color: var(--ink-2); font-weight: 700; margin-top: 6px; }
  svg.spark { display: block; width: 100%; height: 100%; }
  /* «mejor del día»: tarjeta a ancho completo (nombre a la izquierda, % a la
     derecha), con el aire de abajo que el resto de widgets deja para su spark. */
  #best-card { padding-bottom: 18px; }
  #best-card .bestname { margin-top: 6px; }

  /* «ganador del mes»: tarjetas a ancho completo con la evolución de todos los
     jugadores dentro del mes (cada uno con su color), no solo la del campeón. */
  .mrow { display: grid; grid-template-columns: 1fr; gap: 12px; }
  .card.widget.month { padding-bottom: 18px; }
  .mhead { display: flex; align-items: flex-end; justify-content: space-between;
           gap: 10px 16px; flex-wrap: wrap; }
  .mhead .mhead-l { min-width: 0; }
  .mhead .wbig { margin-top: 0; }
  .mchart { margin-top: 12px; }
  .mchart svg { display: block; width: 100%; height: auto; }
  .mlegend { margin-top: 10px; gap: 7px 14px; font-size: 12.5px; }
  .mlegend .mval { margin-left: 7px; font-weight: 700; font-variant-numeric: tabular-nums; }
  .mlegend .mtrophy { margin-right: 5px; }

  /* insignias (badges): récord destacado de la liga + rejilla de logros. */
  .card.record { padding-bottom: 18px; }
  .record .record-tk { font-size: 16px; font-weight: 700; color: var(--ink-2); margin-left: 8px; }
  #record-date { color: var(--muted); font-weight: 600; font-size: 13px; margin-left: 8px; }
  .badge-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(158px, 1fr)); gap: 10px; }
  .badge { position: relative; display: flex; align-items: flex-start; gap: 11px;
           padding: 12px 13px; border-radius: 18px; background: var(--surface-2);
           border: 1px solid var(--hair); }
  .badge.prov { border-style: dashed; opacity: 0.9; }
  .badge .bico { font-size: 26px; line-height: 1; flex: 0 0 auto; }
  .badge .btext { min-width: 0; }
  .badge .btitle { font-weight: 700; font-size: 14px; color: var(--ink); line-height: 1.2; }
  .badge .bwho { display: flex; align-items: center; gap: 5px; margin-top: 4px;
                 font-size: 13px; font-weight: 600; color: var(--ink-2); }
  .badge .bmeta { font-size: 11.5px; color: var(--muted); font-weight: 500; margin-top: 3px; }
  .badge .ptag { font-size: 10px; font-weight: 700; letter-spacing: .04em; text-transform: uppercase;
                 color: var(--muted); margin-top: 4px; }
  /* insignias compactas dentro de la ficha del jugador */
  .mbadges { display: flex; flex-wrap: wrap; gap: 8px; }
  .mbadge-chip { display: inline-flex; align-items: center; gap: 7px;
                 background: var(--surface-2); border: 1px solid var(--hair);
                 padding: 6px 12px 6px 8px; border-radius: 999px;
                 font-weight: 700; font-size: 13px; color: var(--ink); }
  .mbadge-chip.prov { border-style: dashed; }
  .mbadge-chip .i { font-size: 17px; line-height: 1; }

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

  /* sesión extendida: pre-market / after-hours valor a valor. La página es
     estática, así que la cabecera lleva siempre la hora de la foto. */
  .ext-head { display: flex; align-items: flex-start; justify-content: space-between;
              gap: 10px 16px; flex-wrap: wrap; }
  .ext-head .wbig { margin-top: 0; }
  .ext-when { display: inline-flex; align-items: center; gap: 5px; margin-left: 8px;
              color: var(--muted); font-weight: 600; font-size: 12.5px; }
  .ext-when .dot { width: 7px; height: 7px; border-radius: 999px; background: var(--accent);
                   color: var(--accent); animation: pulse 2.4s infinite; }
  .ext-list { margin-top: 12px; }
  .ext-row { display: flex; align-items: center; gap: 10px; padding: 10px 4px;
             border-top: 1px solid var(--hair); border-radius: 10px; }
  .ext-row:first-child { border-top: none; }
  .ext-row.clk { cursor: pointer; }
  .ext-row.clk:hover { background: var(--surface-2); }
  .ext-row.clk:hover .sym { color: var(--accent); }
  .ext-row .logo, .ext-row .mono { width: 30px; height: 30px; flex: none; }
  .ext-row .tk { display: flex; flex-direction: column; gap: 1px; min-width: 0; }
  .ext-row .sym { font-weight: 700; letter-spacing: -0.01em; white-space: nowrap; }
  .ext-row .nm { color: var(--muted); font-weight: 600; font-size: 12.5px;
                 overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .ext-row .px { margin-left: auto; flex: none; color: var(--ink-2); font-weight: 600;
                 font-size: 13.5px; font-variant-numeric: tabular-nums; }
  .ext-row .pct { flex: none; min-width: 74px; text-align: right; font-weight: 800;
                  font-variant-numeric: tabular-nums; }

  /* widget de últimas operaciones (fecha · compra/venta · ticker · jugador) */
  .op-row { display: flex; align-items: center; gap: 10px; padding: 11px 4px;
            border-top: 1px solid var(--hair); border-radius: 10px; }
  .op-row:first-child { border-top: none; }
  .op-row.clk { cursor: pointer; }
  .op-row.clk:hover { background: var(--surface-2); }
  .op-row.clk:hover .op-tk .sym { color: var(--accent); }
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

  /* clasificación tipo parrilla (F1 / liga): posición, jugador, acumulado y la
     diferencia con el primero. La fila del líder va tintada con su color. */
  #standings td.rank { font-size: 16px; }
  #standings td.gap { color: var(--muted); font-weight: 600; }
  #standings tr.lead td {
    background: color-mix(in srgb, var(--lead, var(--accent)) 11%, transparent);
  }
  #standings tr.lead td:first-child { border-radius: 12px 0 0 12px; }
  #standings tr.lead td:last-child { border-radius: 0 12px 12px 0; }
  #standings td.empty { color: var(--muted); font-weight: 500; }
  /* en el móvil la columna «desde» se cae: lo que importa es la posición, el
     acumulado y la diferencia con el primero (la fecha sigue en su ficha). */
  @media (max-width: 560px) {
    #standings th:last-child, #standings td:not(.empty):last-child { display: none; }
    #standings th, #standings td { padding: 9px 5px; font-size: 13.5px; }
    /* los títulos se parten en dos líneas antes que obligar a desplazar la
       tabla: los datos (que sí van en una línea) caben en la pantalla. */
    #standings th { font-size: 11.5px; white-space: normal; }
    #standings td.rank { font-size: 14px; }
    #standings td.big { font-size: 14.5px; }
  }

  /* leyenda (widgets de mes) */
  .legend { display: flex; flex-wrap: wrap; gap: 8px 14px; margin-top: 12px;
            font-size: 13px; font-weight: 600; color: var(--ink-2); }
  .legend span { display: inline-flex; align-items: center; }

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
  tr.clk:hover td { background: var(--surface-2); }
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
      <span class="period" data-i18n="periodAll"></span>
    </div>
  </header>

  <section class="card warn" id="pending-card" style="display:none">
    <h2 data-i18n="pendingTitle"></h2>
    <div class="wsub" id="pending" style="margin-top:6px"></div>
  </section>

  <div id="widgets" style="display:grid;gap:12px">
    <section class="card" id="hero-card" style="position:relative">
      <button class="whelp" id="hero-help" type="button" data-i18n-title="calcHelpAria">?</button>
      <h2 data-i18n="ranking" style="padding-right:34px"></h2>
      <div class="leader" id="leader-row">
        <div class="lead-l">
          <span class="lead-tag"><span class="lead-trophy">🏆</span><span data-i18n="leader"></span></span>
          <span class="lead-name"><span class="key" id="leader-key"></span><span id="leader-name"></span></span>
        </div>
        <div class="lead-r">
          <span class="num lval" id="leader-val"></span>
          <span class="delta" id="leader-delta"></span>
        </div>
      </div>
      <div class="overx" style="margin-top:12px"><table id="standings"></table></div>
    </section>
    <section class="card widget" id="best-card">
      <div class="wlabel"><span data-i18n="bestOfDay"></span><span id="best-date"></span></div>
      <div class="mhead">
        <div class="mhead-l"><div class="bestname" id="best-name"></div></div>
        <div class="wbig"><span class="num" id="best-val"></span></div>
      </div>
    </section>
    <div class="mrow" id="month-row" style="display:none">
      <section class="card widget month" id="month-cur-card">
        <div class="wlabel" id="month-cur-label"></div>
        <div class="mhead">
          <div class="mhead-l">
            <div class="winnername"><span id="month-cur-player"></span><span class="trophy">🏆</span></div>
            <div class="wsub treat" id="month-cur-note"></div>
          </div>
          <div class="wbig sm"><span class="num" id="month-cur-val"></span></div>
        </div>
        <div class="mchart" id="month-cur-chart"></div>
        <div class="legend mlegend" id="month-cur-legend"></div>
      </section>
      <section class="card widget month" id="month-prev-card">
        <div class="wlabel" id="month-prev-label"></div>
        <div class="mhead">
          <div class="mhead-l">
            <div class="winnername"><span id="month-prev-player"></span><span class="trophy">🏆</span></div>
          </div>
          <div class="wbig sm"><span class="num" id="month-prev-val"></span></div>
        </div>
        <div class="mchart" id="month-prev-chart"></div>
        <div class="legend mlegend" id="month-prev-legend"></div>
      </section>
    </div>
  </div>

  <!-- sesión extendida (pre-market / after-hours) de los valores de la liga.
       Solo se pinta cuando había una sesión extendida en curso al generar la
       página y la foto sigue siendo reciente: la web es estática y no se
       refresca sola, así que siempre se dice a qué hora se tomó. -->
  <section class="card" id="ext-card" style="display:none">
    <div class="ext-head">
      <div style="min-width:0">
        <div class="wlabel"><span id="ext-title"></span><span class="ext-when"
          ><span class="dot"></span><span id="ext-when"></span></span></div>
        <div class="wsub muted" id="ext-sub"></div>
      </div>
      <div class="wbig sm"><span class="num" id="ext-val"></span></div>
    </div>
    <div class="ext-list" id="ext-list"></div>
    <div class="wsub muted" id="ext-note" style="margin-top:10px"></div>
  </section>

  <section class="card" id="badges-card" style="display:none">
    <h2 data-i18n="badgesTitle"></h2>
    <div class="wsub muted" data-i18n="badgesSub" style="margin-top:2px"></div>
    <section class="card widget record" id="record-card" style="display:none;margin-top:12px">
      <div class="wlabel"><span data-i18n="recordTitle"></span><span id="record-date"></span></div>
      <div class="wbig"><span class="num pos" id="record-val"></span><span class="record-tk" id="record-tk"></span></div>
      <div class="bestname" id="record-holders"></div>
      <div class="wsub muted" id="record-prev" style="margin-top:6px"></div>
    </section>
    <div id="badge-grid" class="badge-grid" style="margin-top:12px"></div>
    <div class="wsub muted" id="badge-empty" style="display:none;margin-top:8px" data-i18n="badgesEmpty"></div>
  </section>

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
    periodAll: "Since the start",
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
    extPre: "Pre-market",
    extPost: "After hours",
    extAt: t => "as of " + t,
    extHoldings: n => n + (n === 1 ? " holding" : " holdings"),
    extSession: "Extended session",
    extLeague: "League portfolio, weighted",
    extNote: "Prices outside regular trading hours (Yahoo Finance), captured " +
      "when the page was built — they don't count towards the standings until " +
      "the session closes.",
    winnerOf: ml => "Winner of " + ml,
    monthChartAria: ml => "Return of every player during " + ml,
    lunchNote: "🍽️ Their turn to buy lunch",
    aiBadge: "AI",
    insightsTitle: "League insights",
    aiLive: "automatic analysis",
    ranking: "Standings",
    rankCols: ["#", "Player", "Cumulative %", "Gap to 1st", "Last day %", "Since"],
    gapLeader: "—",
    dailyTitle: ml => "🏅 Daily champion · " + ml,
    dailyCols: ["Date", "Champion", "Day %"],
    leagueWallet: "League portfolio",
    walletsTitle: "Portfolios by player",
    badgesTitle: "🎖️ Badges",
    badgesSub: "Achievements pile up over time — once earned, they stay.",
    badgesEmpty: "No badges yet — they'll appear as the league heats up.",
    recordTitle: "🚀 Biggest single-day gain",
    recordHeld: names => "Held by " + names,
    recordPrev: (pct, tk, d) => "Previous record: " + tk + " " + pct + " · " + d,
    badgeChamp: ml => "Champion of " + ml,
    badgeChampProv: ml => "Leading " + ml,
    badgeWeek: "A week in the green",
    badgeMilestone: t => "+" + t + "% reached",
    badgeMonths: n => n + " winning months in a row",
    badgeChampMeta: pct => "Month " + pct,
    badgeOn: d => "Earned " + d,
    badgeLive: "Live",
    cumTitle: "Cumulative return · since the start",
    dailyDetailTitle: "Daily detail · since the start",
    detailAria: "Detail",
    dayByAsset: "Return by asset",
    dayOthers: "Rest of players",
    dayCash: "Cash · fees",
    dayNoBreakdown: "No per-asset breakdown for this session.",
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
      onARoll: (a, g) => a + " is on a roll: " + g + " since the league started.",
      sharp: (a, g, k) => a + " is sharp: " + g + " of the last " + k + " days green.",
      needsReact: (a, p) => a + " needs to react: " + p + " cumulative.",
      signsOfLife: (a, p) => a + " shows signs of life: " + p + " today from the bottom.",
      bottomEarly: a => a + " sits at the bottom, but the league has only just begun.",
      rollercoaster: (a, g) => a + " is on a rollercoaster: " + g + " of swing since the start.",
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
    periodAll: "開始から",
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
    extPre: "プレマーケット",
    extPost: "時間外取引",
    extAt: t => t + "時点",
    extHoldings: n => n + "銘柄",
    extSession: "時間外セッション",
    extLeague: "リーグ全体（加重平均）",
    extNote: "通常取引時間外の株価（Yahoo Finance）。ページ生成時点のスナップショット" +
      "です。セッションが終わるまで順位には反映されません。",
    winnerOf: ml => ml + "の優勝者",
    monthChartAria: ml => ml + "の全プレイヤーのリターン推移",
    lunchNote: "🍽️ ランチをおごる番",
    aiBadge: "AI",
    insightsTitle: "リーグのインサイト",
    aiLive: "自動分析",
    ranking: "順位表",
    rankCols: ["#", "プレイヤー", "累積%", "首位差", "前日比%", "開始"],
    gapLeader: "—",
    dailyTitle: ml => "🏅 デイリー王者 · " + ml,
    dailyCols: ["日付", "王者", "当日%"],
    leagueWallet: "リーグのポートフォリオ",
    walletsTitle: "プレイヤー別ポートフォリオ",
    badgesTitle: "🎖️ バッジ",
    badgesSub: "実績は積み重なり、一度獲得したら消えません。",
    badgesEmpty: "まだバッジはありません。リーグが白熱すると登場します。",
    recordTitle: "🚀 1日の最大上昇",
    recordHeld: names => "保有者: " + names,
    recordPrev: (pct, tk, d) => "前の記録: " + tk + " " + pct + " · " + d,
    badgeChamp: ml => ml + "の王者",
    badgeChampProv: ml => ml + "首位",
    badgeWeek: "1週間連勝",
    badgeMilestone: t => "+" + t + "%達成",
    badgeMonths: n => n + "か月連続勝利",
    badgeChampMeta: pct => "月間 " + pct,
    badgeOn: d => d + "獲得",
    badgeLive: "ライブ",
    cumTitle: "累積リターン · 開始から",
    dailyDetailTitle: "日次詳細 · 開始から",
    detailAria: "詳細",
    dayByAsset: "銘柄別リターン",
    dayOthers: "他のプレイヤー",
    dayCash: "現金・手数料",
    dayNoBreakdown: "この取引日の銘柄別内訳はありません。",
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
      onARoll: (a, g) => a + "が好調：リーグ開始から" + g + "。",
      sharp: (a, g, k) => a + "が絶好調：直近" + k + "日中" + g + "日プラス。",
      needsReact: (a, p) => a + "は立て直しが必要：累積" + p + "。",
      signsOfLife: (a, p) => a + "が最下位から反撃：本日" + p + "。",
      bottomEarly: a => a + "が最下位だが、リーグは始まったばかり。",
      rollercoaster: (a, g) => a + "はジェットコースター状態：開始から" + g + "の変動。",
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
// Se lee como una parrilla de F1 o una tabla de liga: primero, segundo,
// tercero… con la diferencia de cada jugador respecto al primero en puntos
// porcentuales (el líder marca el ritmo y lleva un guion).
const ranked = [...DATA.players].sort((a, b) => lastOf(b).cum - lastOf(a).cum);
const MEDALS = ["🥇","🥈","🥉"];
{
  const t = document.getElementById("standings");
  const mk = (tag, cls, text) => { const el = document.createElement(tag);
    if (cls) el.className = cls; if (text !== undefined) el.textContent = text; return el; };
  const head = t.insertRow();
  T.rankCols.forEach((h, i) => {
    const th = document.createElement("th");
    th.textContent = h; if (i === 1) th.className = "name"; head.appendChild(th);
  });
  if (!ranked.length) {
    const empty = mk("td", "empty", T.noPlayers);
    empty.colSpan = T.rankCols.length;
    t.insertRow().appendChild(empty);
  }
  const topCum = ranked.length ? lastOf(ranked[0]).cum : 0;
  ranked.forEach((p, i) => {
    const last = lastOf(p);
    const tr = t.insertRow();
    tr.classList.add("clk"); tr.dataset.player = p.id;
    if (i === 0) tr.classList.add("lead");
    tr.appendChild(mk("td", "rank", MEDALS[i] || String(i + 1)));
    const name = mk("td", "name");
    const key = mk("span", "key"); key.style.background = colorOf(p);
    name.appendChild(key); name.appendChild(document.createTextNode(p.name));
    tr.appendChild(name);
    tr.appendChild(mk("td", "big " + (last.cum >= 0 ? "pos" : "neg"), fmtPct(last.cum)));
    const behind = topCum - last.cum;
    tr.appendChild(mk("td", "gap", i === 0 || behind < 0.005
      ? T.gapLeader : "-" + behind.toFixed(2) + T.pp));
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
  // Sin jugadores la clasificación ya enseña su propio mensaje vacío: solo se
  // esconde lo que no tiene nada que contar (líder y mejor del día).
  if (!DATA.players.length) {
    document.getElementById("leader-row").style.display = "none";
    document.getElementById("best-card").style.display = "none";
    return;
  }

  // líder: quién va ganando y con qué rentabilidad acumulada. El color se pone
  // en la tarjeta para que lo hereden la banda del líder y su fila de la tabla.
  const leader = ranked[0], lc = lastOf(leader);
  document.getElementById("hero-card").style.setProperty("--lead", colorOf(leader));
  document.getElementById("leader-key").style.background = colorOf(leader);
  document.getElementById("leader-name").textContent = leader.name;
  const lv = document.getElementById("leader-val");
  lv.textContent = fmtPct(lc.cum); lv.className = "num lval " + (lc.cum >= 0 ? "pos" : "neg");
  const ld = document.getElementById("leader-delta");
  ld.textContent = (lc.day >= 0 ? "▲ " : "▼ ") + fmtPct(lc.day);
  ld.className = "delta " + (lc.day >= 0 ? "pos" : "neg");

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
  // aporta nada (sería alguien con +0,00%): se oculta el widget.
  const allZeroDay = DATA.players.every(p => Math.abs(lastOf(p).day) < 0.005);
  if (allZeroDay) {
    bestCard.style.display = "none";
  } else {
    bestCard.style.display = "";
    // Con el mercado cerrado el widget NO se queda en blanco: sigue enseñando
    // al ganador de la última jornada cerrada (que es la anterior a hoy), solo
    // que con una etiqueta de «mercado cerrado» junto a su fecha para que se
    // vea de qué sesión es el dato.
    //
    // «Cerrado» aquí es la madrugada/mañana de un día laborable, antes de que
    // abra el mercado de EE. UU. (~15:30 en Madrid) y mientras no haya jornada
    // de hoy. Todo se calcula en hora de Madrid para que el corte sea
    // exactamente la medianoche local (con DST correcto). Los fines de semana y
    // tras el cierre —con la jornada del día ya publicada— no se marca nada.
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
    bDate.textContent = " · " + bd.date.slice(5).split("-").reverse().join("/");
    bv.textContent = fmtPct(bd.day); bv.className = "num " + (bd.day >= 0 ? "pos" : "neg");
    bn.innerHTML = '<span class="medal">🥇</span>';
    bn.appendChild(document.createTextNode(best.name));
    if (marketClosed) {
      const tag = document.createElement("span");
      tag.className = "closed-tag";
      tag.textContent = "🚧 " + T.marketClosed;
      bn.appendChild(tag);
    }
  }
}
paintWidgets();

// ---- widgets «mejor del mes»: este mes y el mes pasado (si hay datos) ----
// Aunque el titular sea el ganador, la gráfica pinta a todos los jugadores del
// mes con su color: así se ve de un vistazo cómo va el resto y cuánta ventaja
// lleva el campeón. El acumulado arranca en 0 el primer día del mes (es la
// carrera *de ese mes*, no el acumulado de toda la liga).
function monthChart(host, info) {
  const NSm = "http://www.w3.org/2000/svg";
  const mk = (tag, attrs) => { const e = document.createElementNS(NSm, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]); return e; };
  const dates = info.dates || [], series = info.series || [];
  host.innerHTML = "";
  if (!dates.length || !series.length) return;
  // Las unidades del viewBox son px reales del contenedor: el texto no se
  // deforma al escalar en pantallas estrechas (igual que la gráfica principal).
  const W = Math.max(280, Math.round(host.clientWidth || 600));
  const narrow = W < 520;
  const H = narrow ? 190 : 220;
  const M = {t: 12, r: 14, b: 24, l: narrow ? 42 : 48};
  // línea base en 0: la magnitud es honesta aunque nadie se mueva mucho
  let lo = 0, hi = 0;
  series.forEach(s => s.cum.forEach(v => {
    if (v === null) return; lo = Math.min(lo, v); hi = Math.max(hi, v); }));
  if (hi === lo) { hi += 1; lo -= 1; }
  const padv = (hi - lo) * 0.12; hi += padv; lo -= padv;
  const Y = v => M.t + (1 - (v - lo) / (hi - lo)) * (H - M.t - M.b);
  // El % final va junto al último punto solo si hay sitio y las etiquetas no se
  // pisan entre sí; si no, la derecha se aprovecha para la propia gráfica (la
  // leyenda de abajo siempre lleva el dato de cada jugador).
  const ends = series
    .map(s => { const v = s.cum.filter(x => x !== null && x !== undefined).pop();
                return v === undefined ? null : {yy: Y(v), value: s.value}; })
    .filter(Boolean)
    .sort((a, b) => a.yy - b.yy);
  const showEnds = !narrow && ends.length &&
    !ends.some((e, i) => i && e.yy - ends[i - 1].yy < 13);
  if (showEnds) M.r = 58;
  const X = i => M.l + (dates.length < 2 ? 0.5 : i / (dates.length - 1)) * (W - M.l - M.r);
  const svg = mk("svg", {viewBox: "0 0 " + W + " " + H, role: "img",
    "aria-label": T.monthChartAria(monthLabel(info.month, info.month_year))});

  // rejilla + eje Y
  niceTicks(lo, hi, 4).forEach(v => {
    const isZero = Math.abs(v) < 1e-9;
    svg.appendChild(mk("line", {x1: M.l, x2: W - M.r, y1: Y(v), y2: Y(v),
      stroke: isZero ? css("--baseline") : css("--grid"), "stroke-width": 1}));
    const t = mk("text", {x: M.l - 8, y: Y(v) + 4, "text-anchor": "end",
      fill: css("--muted"), "font-size": 11, style: "font-variant-numeric:tabular-nums"});
    t.textContent = (v > 0 ? "+" : "") + v.toFixed(Math.abs(v) < 10 && v % 1 ? 1 : 0) + "%";
    svg.appendChild(t);
  });
  // eje X: tantas fechas como quepan (~1 cada 110px), con la última siempre
  const stepX = Math.max(1, Math.round(dates.length /
    Math.max(2, Math.round((W - M.l - M.r) / 110))));
  dates.forEach((d, i) => {
    const isLast = i === dates.length - 1;
    if (!isLast && (i % stepX !== 0 || dates.length - 1 - i < stepX * 0.6)) return;
    // la última fecha se alinea a la derecha si centrada se saldría del lienzo
    const clip = isLast && X(i) + 32 > W;
    const t = mk("text", {x: clip ? W - 2 : X(i), y: H - 7,
      "text-anchor": clip ? "end" : "middle",
      fill: css("--muted"), "font-size": 11});
    t.textContent = fmtDate(d);
    svg.appendChild(t);
  });
  // una línea por jugador, con su color; la del ganador va algo más gruesa
  series.forEach((s, si) => {
    const c = css(SLOTS[s.slot % SLOTS.length]);
    const pts = dates.map((d, i) => s.cum[i] === null || s.cum[i] === undefined
      ? null : [X(i), Y(s.cum[i])]).filter(Boolean);
    if (!pts.length) return;
    if (pts.length > 1) svg.appendChild(mk("path", {
      d: pts.map((pt, i) => (i ? "L" : "M") + pt[0].toFixed(1) + " " + pt[1].toFixed(1)).join(""),
      fill: "none", stroke: c, "stroke-width": si === 0 ? 2.8 : 2,
      opacity: si === 0 ? 1 : 0.85,
      "stroke-linejoin": "round", "stroke-linecap": "round"}));
    const end = pts[pts.length - 1];
    svg.appendChild(mk("circle", {cx: end[0], cy: end[1], r: si === 0 ? 4 : 3.4, fill: c,
      stroke: css("--card-solid"), "stroke-width": 2.5}));
  });
  if (showEnds) ends.forEach(e => {
    const t = mk("text", {x: W - M.r + 5, y: e.yy + 4, fill: css("--ink-2"),
      "font-size": 11, style: "font-variant-numeric:tabular-nums;font-weight:600"});
    t.textContent = fmtPct(e.value);
    svg.appendChild(t);
  });
  host.appendChild(svg);
}

// Leyenda del mes: cada jugador con su color y su % del mes, de mejor a peor.
// Abre la ficha del jugador al pulsar (delegación sobre ``data-player``).
function monthLegend(host, info) {
  host.innerHTML = "";
  const series = info.series || [];
  if (series.length < 2) return;
  series.forEach((s, i) => {
    const el = document.createElement("span");
    el.className = "clk"; el.dataset.player = s.id;
    const key = document.createElement("span");
    key.className = "key"; key.style.background = css(SLOTS[s.slot % SLOTS.length]);
    el.appendChild(key);
    if (i === 0) {
      const tr = document.createElement("span");
      tr.className = "mtrophy"; tr.textContent = "🏆"; el.appendChild(tr);
    }
    el.appendChild(document.createTextNode(s.name));
    const val = document.createElement("span");
    val.className = "mval " + (s.value >= 0 ? "pos" : "neg");
    val.textContent = fmtPct(s.value);
    el.appendChild(val);
    host.appendChild(el);
  });
}

function paintMonthly() {
  const m = DATA.monthly || {};
  const paint = (info, key) => {
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
    monthChart(document.getElementById(key + "-chart"), info);
    monthLegend(document.getElementById(key + "-legend"), info);
    return true;
  };
  const hasCur = paint(m.current, "month-cur");
  const hasPrev = paint(m.previous, "month-prev");
  const row = document.getElementById("month-row");
  row.style.display = (hasCur || hasPrev) ? "grid" : "none";
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
    // toda la fila abre el detalle del día del campeón (rentabilidad por valor
    // + el % del día del resto de jugadores)
    tr.classList.add("clk");
    tr.dataset.dayDate = r.date;
    tr.dataset.dayPlayer = (r.ids && r.ids[0]) || "";
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

// ---- insignias (badges): récord de la liga + rejilla de logros acumulados ----
// Los datos llegan ya calculados y ordenados desde el histórico persistente
// (data/badges.json): aquí solo se pintan. Cada logro lleva el color del
// jugador (slot) para reconocerlo de un vistazo.
const BADGE_ICON = {
  champion_month: "🏆", week_streak: "🔥", milestone: "💎",
  months_2: "📈", months_3: "🗓️",
};
function badgeMilestoneIcon(t) { return t >= 25 ? "🚀" : (t >= 10 ? "💎" : "🌱"); }
function badgeTitle(b) {
  if (b.type === "champion_month") {
    const ml = monthLabel(+b.month.split("-")[1], +b.month.split("-")[0]);
    return b.provisional ? T.badgeChampProv(ml) : T.badgeChamp(ml);
  }
  if (b.type === "week_streak") return T.badgeWeek;
  if (b.type === "milestone") return T.badgeMilestone(b.tier);
  if (b.type === "months_2") return T.badgeMonths(2);
  if (b.type === "months_3") return T.badgeMonths(3);
  return b.type;
}
function badgeIcon(b) {
  if (b.type === "milestone") return badgeMilestoneIcon(b.tier);
  return BADGE_ICON[b.type] || "🎖️";
}
// Insignias agrupadas por jugador, para su ficha de detalle. Las provisionales
// (campeón del mes en curso) van primero; el resto ya llega ordenado de más
// reciente a más antigua desde el histórico.
const PLAYER_BADGES = {};
(((DATA.badges || {}).provisional) || [])
  .concat(((DATA.badges || {}).awards) || [])
  .forEach(b => { if (b.player) (PLAYER_BADGES[b.player] || (PLAYER_BADGES[b.player] = [])).push(b); });
function paintBadges() {
  const data = DATA.badges || {};
  const awards = (data.provisional || []).concat(data.awards || []);
  const record = data.record || null;
  const card = document.getElementById("badges-card");
  if (!awards.length && !record) { card.style.display = "none"; return; }
  card.style.display = "";
  const slotColor = s => css(SLOTS[(s || 0) % SLOTS.length]);

  // Récord de «mayor subida de un valor en un día».
  const rc = document.getElementById("record-card");
  if (record) {
    rc.style.display = "";
    document.getElementById("record-date").textContent = " · " + fmtDate(record.date);
    document.getElementById("record-val").textContent = fmtPct(record.pct);
    document.getElementById("record-tk").textContent = record.ticker;
    const holders = (record.holders || []).map(h => h.name);
    const rh = document.getElementById("record-holders");
    rh.textContent = holders.length ? T.recordHeld(holders.join(", ")) : "";
    rh.style.display = holders.length ? "" : "none";
    const prev = (record.history || []).slice(-1)[0];
    const rp = document.getElementById("record-prev");
    if (prev) { rp.style.display = ""; rp.textContent = T.recordPrev(fmtPct(prev.pct), prev.ticker, fmtDate(prev.date)); }
    else rp.style.display = "none";
  } else rc.style.display = "none";

  // Rejilla de insignias.
  const grid = document.getElementById("badge-grid");
  grid.innerHTML = "";
  document.getElementById("badge-empty").style.display = awards.length ? "none" : "";
  awards.forEach(b => {
    const el = document.createElement("div");
    el.className = "badge" + (b.provisional ? " prov" : "");
    const ico = document.createElement("span");
    ico.className = "bico"; ico.textContent = badgeIcon(b); el.appendChild(ico);
    const box = document.createElement("div"); box.className = "btext";
    const title = document.createElement("div");
    title.className = "btitle"; title.textContent = badgeTitle(b); box.appendChild(title);
    const who = document.createElement("div"); who.className = "bwho";
    const key = document.createElement("span");
    key.className = "key"; key.style.background = slotColor(b.slot); who.appendChild(key);
    who.appendChild(document.createTextNode(b.name || "")); box.appendChild(who);
    const meta = document.createElement("div"); meta.className = "bmeta";
    if (b.type === "champion_month" && b.pct !== undefined && b.pct !== null)
      meta.textContent = T.badgeChampMeta(fmtPct(b.pct));
    else if (b.date) meta.textContent = T.badgeOn(fmtDate(b.date));
    box.appendChild(meta);
    if (b.provisional) {
      const tag = document.createElement("div");
      tag.className = "ptag"; tag.textContent = "● " + T.badgeLive; box.appendChild(tag);
    }
    el.appendChild(box);
    grid.appendChild(el);
  });
}
paintBadges();

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
  // avance desde el inicio de la liga (la serie ya no se recorta a 30 días)
  const totalDelta = p => lastp(p).cum - p.days[0].cum;
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
  ps.forEach(p => { const d = totalDelta(p); if (d > 3)
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

// ---- utilidades de escala (las usan las gráficas de los widgets del mes) ----
function niceTicks(lo, hi, n) {
  const span = hi - lo, step0 = span / n, mag = Math.pow(10, Math.floor(Math.log10(step0)));
  const step = [1,2,2.5,5,10].map(m => m * mag).find(s => span / s <= n) || 10 * mag;
  const out = []; for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) out.push(v);
  return out;
}

// Repintado ante cambios de tema o de tamaño: las gráficas de los widgets del
// mes miden en px reales del contenedor, así que hay que rehacerlas.
const mq = window.matchMedia("(prefers-color-scheme: dark)");
if (mq.addEventListener) mq.addEventListener("change", () => { paintWidgets(); paintMonthly(); paintAllocation(); paintWallets(); paintInsights(); });
let rafId;
window.addEventListener("resize", () => {
  cancelAnimationFrame(rafId);
  rafId = requestAnimationFrame(paintMonthly);
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
      // cada jornada abre su detalle: rentabilidad por valor de este jugador
      // ese día (+ el % del día del resto de jugadores)
      tr.classList.add("clk");
      tr.dataset.dayPlayer = p.id;
      tr.dataset.dayDate = dy.date;
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
    // Toda la fila es clicable: abre la ficha del valor (o la del jugador si el
    // valor no es abrible). El nombre del jugador, anidado con su propio
    // data-player, sigue abriendo su ficha por delegación (gana el más interno).
    if (TICKERS[o.ticker]) { row.classList.add("clk"); row.dataset.ticker = o.ticker; }
    else if (o.id && PLAYERS[o.id]) { row.classList.add("clk"); row.dataset.player = o.id; }

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

// ---- sesión extendida: pre-market / after-hours valor a valor -------------
// La web es estática: lo que se pinta es la foto que se tomó al generarla (el
// build corre cada hora en horario de mercado y también en las franjas de
// pre-market y after-hours). Por eso la cabecera lleva siempre la hora del
// dato y, si quien abre la página lo hace mucho después, la tarjeta se esconde
// en vez de enseñar un pre-market de hace horas como si fuera de ahora.
const EXT_MAX_AGE = 6 * 3600;  // segundos
const CUR_SYM = {USD: "$", EUR: "\\u20ac", GBP: "\\u00a3"};
const extLabel = session => session === "pre" ? T.extPre : T.extPost;
function extMoney(v, cur) {
  const n = Number(v).toLocaleString("en-US",
    {minimumFractionDigits: 2, maximumFractionDigits: 2});
  return CUR_SYM[cur] ? CUR_SYM[cur] + n : n + (cur ? " " + cur : "");
}
function fmtClock(epoch) {
  return new Intl.DateTimeFormat(LANG === "ja" ? "ja-JP" : "en-GB", {
    timeZone: "Europe/Madrid", hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  }).format(new Date(epoch * 1000));
}
function paintExtended() {
  const m = DATA.market, card = document.getElementById("ext-card");
  const fresh = m && m.asOf && (Date.now() / 1000 - m.asOf) < EXT_MAX_AGE;
  const rows = (DATA.tickers || []).filter(t =>
    t.ext && m && t.ext.session === m.session && t.ext.pct != null);
  if (!fresh || !rows.length) { card.style.display = "none"; return; }
  card.style.display = "";

  document.getElementById("ext-title").textContent =
    (m.session === "pre" ? "\\ud83c\\udf05 " : "\\ud83c\\udf19 ") + extLabel(m.session);
  document.getElementById("ext-when").textContent = T.extAt(fmtClock(m.asOf));
  // El titular es la variación media de la liga ponderada por el peso de cada
  // posición; si no se ha podido calcular, la tarjeta se queda en la lista.
  const val = document.getElementById("ext-val");
  val.textContent = m.pct == null ? "" : fmtPct(m.pct);
  val.className = "num " + (m.pct >= 0 ? "pos" : "neg");
  document.getElementById("ext-sub").textContent =
    (m.pct == null ? T.extSession : T.extLeague) + " \\u00b7 " +
    T.extHoldings(rows.length);
  document.getElementById("ext-note").textContent = T.extNote;

  const box = document.getElementById("ext-list");
  box.innerHTML = "";
  rows.sort((a, b) => b.ext.pct - a.ext.pct).forEach(t => {
    const row = h("div", "ext-row clk");
    row.dataset.ticker = t.ticker;
    row.appendChild(tickerLogoEl(t, 30));
    const tk = h("div", "tk");
    const sym = h("span", "sym"); sym.textContent = t.ticker;
    const nm = h("span", "nm"); nm.textContent = t.name;
    tk.appendChild(sym); tk.appendChild(nm);
    row.appendChild(tk);
    row.appendChild(h("span", "px", extMoney(t.ext.price, t.ext.currency)));
    row.appendChild(h("span", "pct " + (t.ext.pct >= 0 ? "pos" : "neg"),
                      fmtPct(t.ext.pct)));
    box.appendChild(row);
  });
}
paintExtended();

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
  // Sesión extendida del valor (pre-market / after-hours), si la había cuando
  // se generó la página: el precio fuera de horario y su variación frente al
  // último cierre regular.
  const ex = t.ext;
  if (ex && ex.session && ex.pct != null)
    tiles.appendChild(tileEl(
      extLabel(ex.session) + " \\u00b7 " + extMoney(ex.price, ex.currency),
      fmtPct(ex.pct), ex.pct >= 0 ? "pos" : "neg"));
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

  const myBadges = PLAYER_BADGES[pid] || [];
  if (myBadges.length) {
    const wrap = h("div", "mbadges");
    myBadges.forEach(b => {
      const chip = h("div", "mbadge-chip" + (b.provisional ? " prov" : ""));
      chip.appendChild(h("span", "i", badgeIcon(b)));
      chip.appendChild(h("span", "t", badgeTitle(b)));
      wrap.appendChild(chip);
    });
    root.appendChild(sectionEl(T.badgesTitle, wrap));
  }

  if (days.length >= 2) {
    const spark = h("div", "mspark",
      sparkSVG(days.map(d => d.cum), last.cum >= 0 ? upC : downC, "pl", {baseline0: true}));
    // la serie del jugador es toda la liga: mismo título que la gráfica grande
    root.appendChild(sectionEl(T.cumTitle, spark));
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

// ---- detalle de una jornada (campeón del día / fila del detalle diario) ----
// Índice fecha -> { id de jugador -> su jornada }, para reunir en un vistazo la
// rentabilidad de cada jugador ese día sin recorrer todo el dataset al abrir.
const DAY_INDEX = {};
DATA.players.forEach(p => (p.days || []).forEach(d => {
  (DAY_INDEX[d.date] || (DAY_INDEX[d.date] = {}))[p.id] = d;
}));

// Muestra la rentabilidad de cada valor del jugador esa jornada (los % suman el
// «% del día») y, debajo, el % del día del resto de jugadores. ``pid`` es el
// jugador protagonista (el campeón, o el propio jugador en el detalle diario);
// si falta o no tiene datos ese día, se toma el mejor de la jornada.
function openDayDetail(pid, iso) {
  const perPlayer = DAY_INDEX[iso] || {};
  let subject = PLAYERS[pid];
  if (!subject || !perPlayer[pid]) {
    let bestId = null, bestVal = -Infinity;
    Object.keys(perPlayer).forEach(id => {
      if (perPlayer[id].day > bestVal) { bestVal = perPlayer[id].day; bestId = id; }
    });
    subject = PLAYERS[bestId]; pid = bestId;
  }
  if (!subject) return;
  const sd = perPlayer[pid] || {day: 0, bd: []};
  const root = document.createElement("div");

  const head = h("div", "mhead");
  head.appendChild(monoEl(subject.name, 46, colorOf(subject)));
  const title = h("div", "mtitle");
  const t1 = h("div", "t1");
  t1.appendChild(document.createTextNode(fmtDate(iso)));
  t1.appendChild(h("span", "mbadge" + (sd.day >= 0 ? "" : " neg"), fmtPct(sd.day)));
  title.appendChild(t1);
  title.appendChild(h("div", "t2", subject.name));
  head.appendChild(title);
  root.appendChild(head);

  // rentabilidad por valor: cada porción suma el % del día
  const bd = sd.bd || [];
  if (bd.length) {
    const list = document.createElement("div");
    bd.forEach(x => {
      const row = h("div", "holder-row");
      if (x.ticker && TICKERS[x.ticker]) { row.classList.add("clk"); row.dataset.ticker = x.ticker; }
      const nm = h("span", "nm");
      if (x.ticker) {
        nm.appendChild(tickerLogoEl({ticker: x.ticker}, 26));
        nm.appendChild(document.createTextNode(x.ticker));
      } else {
        nm.appendChild(document.createTextNode("💵 " + T.dayCash));
      }
      row.appendChild(nm);
      row.appendChild(h("span", "w " + (x.pct >= 0 ? "pos" : "neg"), fmtPct(x.pct)));
      list.appendChild(row);
    });
    root.appendChild(sectionEl(T.dayByAsset, list));
  } else {
    root.appendChild(sectionEl(T.dayByAsset, h("div", "mnote", T.dayNoBreakdown)));
  }

  // resto de jugadores: su % del día (ordenado de mejor a peor)
  const others = Object.keys(perPlayer)
    .filter(id => id !== pid && PLAYERS[id])
    .map(id => ({p: PLAYERS[id], d: perPlayer[id]}))
    .sort((a, b) => b.d.day - a.d.day);
  if (others.length) {
    const list = document.createElement("div");
    others.forEach(({p, d}) => {
      const row = h("div", "holder-row clk"); row.dataset.player = p.id;
      const nm = h("span", "nm");
      const key = h("span", "key"); key.style.background = colorOf(p);
      nm.appendChild(key); nm.appendChild(document.createTextNode(p.name));
      row.appendChild(nm);
      row.appendChild(h("span", "w " + (d.day >= 0 ? "pos" : "neg"), fmtPct(d.day)));
      list.appendChild(row);
    });
    root.appendChild(sectionEl(T.dayOthers, list));
  }

  showModal(root);
}

// ---- apertura por delegación + cierre (backdrop / ✕ / Esc) ----
document.addEventListener("click", ev => {
  // detalle de una jornada (campeón del día / fila del detalle diario)
  const dd = ev.target.closest("[data-day-date]");
  if (dd && dd.dataset.dayDate) {
    openDayDetail(dd.dataset.dayPlayer || "", dd.dataset.dayDate); return;
  }
  const tk = ev.target.closest("[data-ticker]");
  const pl = ev.target.closest("[data-player]");
  // Cuando un elemento abrible está anidado dentro de otro (p. ej. el nombre
  // del jugador dentro de una fila de operación que abre el valor), gana el más
  // interno: el que el usuario ha tocado realmente.
  if (tk && pl) {
    if (tk.contains(pl)) openPlayer(pl.dataset.player);
    else openTicker(tk.dataset.ticker);
    return;
  }
  if (tk && tk.dataset.ticker) { openTicker(tk.dataset.ticker); return; }
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
    price_days: int,
    analysts: dict[str, dict] | None = None,
    extended: dict[str, dict] | None = None,
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
    return {
        "name": best["name"],
        "value": round(best["ret"], 2),
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
    ``[{"ticker", "pct"}]`` ordenada por magnitud, donde la suma de los ``pct``
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
                  contributions: dict[str, dict[date, dict[str, float]]] | None = None,
                  badges: dict | None = None,
                  today: date | None = None,
                  now: datetime | None = None) -> dict:
    """Datos embebidos en la página. Respeta show_amounts por jugador.

    La liga se juega **desde el inicio**: por defecto (``last_days=0``) se
    publica la serie completa de cada jugador, así que la clasificación (con la
    diferencia de cada uno con el primero) y el detalle diario cubren toda la
    competición. Los
    campeones del mes actual y del anterior son parciales y se calculan aparte
    (``monthly``), sin recortar esta serie. ``last_days > 0`` recorta a esa
    ventana (útil en pruebas). El ``% acumulado`` de cada día es siempre el de
    siempre (desde el inicio real), y ``since`` guarda la fecha de inicio real
    para la columna «Desde» de la clasificación.

    ``price_days`` es otra cosa: la ventana de la mini-serie de precios del
    detalle de cada ticker (contexto de mercado del valor, no de la liga).

    ``allocation`` es el valor de mercado agregado por ticker de toda la liga;
    se publica solo como pesos (%) para el widget de cartera de la liga, sin
    importes. ``holdings`` es el mismo valor de mercado por ticker pero
    desglosado por jugador (``{id: {ticker: valor}}``): se publica también solo
    como pesos (%) para la sección «Carteras», que muestra el reparto de cada
    jugador sin revelar importes.

    ``extended`` es la cotización fuera de horario por ticker (pre-market /
    after-hours, ver :mod:`trader.extended`): precios públicos de mercado, foto
    del momento del build, que alimentan la tarjeta de sesión extendida del
    dashboard y el detalle de cada valor.
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
            "holdings": holdings_w,
        }
        suggestion = _buy_sell_suggestion(holdings_w, analysts)
        if suggestion:
            entry["suggestion"] = suggestion
        players.append(entry)
    return {"players": players, "pending": pending or [],
            "operations": _recent_operations(computed, order),
            "allocation": _allocation_weights(allocation),
            "market": _market_snapshot(allocation, extended,
                                       int(now.timestamp())),
            "tickers": _ticker_details(allocation, holdings, order, names,
                                       prices, price_days, analysts, extended),
            "monthly": _monthly_bests(computed, today, order),
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
    contributions: dict[str, dict[date, dict[str, float]]] | None = None,
    badges: dict | None = None,
) -> str:
    payload = json.dumps(
        build_payload(computed, last_days=last_days, price_days=price_days,
                      pending=pending,
                      allocation=allocation, holdings=holdings,
                      prices=prices, analysts=analysts, extended=extended,
                      contributions=contributions, badges=badges,
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
