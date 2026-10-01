/* Trader League — la app de la web (estática).
 *
 * La página no lleva datos dentro: al abrirse pide ``api/league.json`` (lo
 * único que escribe ``python -m trader ranking``) y con eso pinta el hilo.
 * Por eso un cambio de diseño no obliga a recalcular la liga, y un recálculo
 * no reescribe la página.
 *
 * La portada es un chat de agentes al estilo de Grok Bots: tú preguntas lo de
 * siempre («¿quién va ganando?», «¿cómo fue la sesión?»…) y Warren (Trader) o
 * Scout (Watch) contestan con su tarjeta. La barra de mensaje de abajo
 * también contesta: un jugador, un ticker o un tema («noticias», «mes»…).
 *
 * Privacidad: igual que antes, la API solo trae porcentajes y pesos (los
 * importes, solo de quien publica los suyos). Los textos que vienen de fuera
 * (titulares de noticias) entran siempre por textContent, nunca como HTML.
 */
"use strict";

const API_URL = "api/league.json";
const MAIL_TO = "ligatrader26@gmail.com";
// Si la app vuelve a primer plano tras este rato, se vuelve a pedir la API
// (instalada como app no hay botón de recargar del navegador).
const STALE_MS = 2 * 60 * 1000;

// ==== utilidades ===========================================================
const $ = id => document.getElementById(id);
const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
// ``html`` es HTML de confianza (plantillas propias); para texto, ``txt``.
const h = (tag, cls, html) => { const e = document.createElement(tag);
  if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; };
const txt = (tag, cls, text) => { const e = document.createElement(tag);
  if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };

// Color de cada jugador: naranja el primero, marrón el segundo y ocres a
// partir del tercero (``--p1..--p8``), por orden alfabético de id.
const SLOTS = ["--p1","--p2","--p3","--p4","--p5","--p6","--p7","--p8"];
const slotColor = s => css(SLOTS[(s || 0) % SLOTS.length]);
const colorOf = p => slotColor(p.slot);
const fmtPct = v => (v > 0 ? "+" : "") + v.toFixed(2) + "%";
const fmtDate = iso => { const [y, m, d] = iso.split("-"); return d + "/" + m + "/" + y.slice(2); };
const fmtW = w => w.toFixed(w < 10 ? 1 : 0) + "%";
const money = v => "$" + Number(v).toLocaleString("en-US", {minimumFractionDigits: 2, maximumFractionDigits: 2});
const lastOf = p => p.days[p.days.length - 1];
const MEDALS = ["🥇","🥈","🥉"];
// sin tildes y en minúsculas: «Séance» y «seance» son la misma palabra
const norm = s => String(s || "").normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();
// los títulos de las tarjetas van limpios en su cabecera (sin el emoji)
const bare = s => String(s).replace(/^[^\p{L}\p{N}]+/u, "");

// El sello «AAAA-MM-DD HH:MM» (hora de Madrid) se lee con el mes escrito en
// el idioma activo —«October 1, 2026 · 19:15»—, con espacios duros para que
// no se parta. Si no viene con esa forma se deja tal cual.
function fmtStamp(stamp) {
  const m = /^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}:\d{2}))?/.exec(String(stamp || "").trim());
  if (!m) return stamp || "";
  const y = m[1], mo = +m[2], d = +m[3], hm = m[4];
  const day = LANG === "ja" ? y + "年" + mo + "月" + d + "日"
    : LANG === "fr" ? d + NBSP + MONTHS.fr[mo - 1] + NBSP + y
    : MONTHS.en[mo - 1] + NBSP + d + "," + NBSP + y;
  return hm ? day + (LANG === "ja" ? NBSP : NBSP + "·" + NBSP) + hm : day;
}

// ==== estado (lo rellena ``setData`` con lo que devuelve la API) ===========
let DATA = null;
let TICKERS = {}, PLAYERS = {}, DAY_INDEX = {}, PLAYER_BADGES = {};
let ranked = [];
let FILTER = "all";          // agente que se está mirando: all | warren | scout
let CHARTS = [];             // gráficas que se rehacen al cambiar de tamaño
let insightTimer = null;

function setData(data) {
  DATA = data;
  DATA.players = DATA.players || [];
  TICKERS = {}; (DATA.tickers || []).forEach(t => TICKERS[t.ticker] = t);
  PLAYERS = {}; DATA.players.forEach(p => PLAYERS[p.id] = p);
  // clasificación: ordenada por acumulado (parrilla de F1 / tabla de liga)
  ranked = [...DATA.players].sort((a, b) => lastOf(b).cum - lastOf(a).cum);
  // fecha -> {jugador -> su jornada}, para el detalle de una sesión
  DAY_INDEX = {};
  DATA.players.forEach(p => (p.days || []).forEach(d => {
    (DAY_INDEX[d.date] || (DAY_INDEX[d.date] = {}))[p.id] = d;
  }));
  // insignias por jugador (las provisionales primero) para su ficha
  PLAYER_BADGES = {};
  ((DATA.badges || {}).provisional || []).concat((DATA.badges || {}).awards || [])
    .forEach(b => { if (b.player) (PLAYER_BADGES[b.player] || (PLAYER_BADGES[b.player] = [])).push(b); });
}

// ==== avatares-blob ========================================================
// Colores planos con dos ojitos, como los bots de Grok. Warren es un círculo
// verde azulado, Scout un rombo violeta y cada jugador un círculo de su color.
const BLOB_BODY = {
  circle: '<circle cx="20" cy="20" r="19"/>',
  diamond: '<rect x="6.5" y="6.5" width="27" height="27" rx="7.5" transform="rotate(45 20 20)"/>',
  tri: '<path d="M20 3.6c1.4 0 2.6.7 3.3 1.9l14 24.2c1.5 2.6-.4 5.8-3.4 5.8H6.1c-3 0-4.9-3.2-3.4-5.8l14-24.2c.7-1.2 1.9-1.9 3.3-1.9z"/>',
};
const BLOB_EYES = {circle: [15.4, 14.6, 22.2, 13.7], diamond: [15.9, 15.2, 22.4, 14.3], tri: [16.8, 19.4, 22.6, 18.6]};
function blobSVG(color, shape, ring) {
  const s = BLOB_BODY[shape] ? shape : "circle";
  const [ax, ay, bx, by] = BLOB_EYES[s];
  // ``ring``: filete del color del fondo alrededor de la forma, para que los
  // avatares montados se separen (también el rombo, que no es redondo)
  const halo = ring ? ' style="stroke:var(--pane);stroke-width:5;paint-order:stroke"' : "";
  return '<svg viewBox="0 0 40 40" aria-hidden="true"><g fill="' + color + '"' + halo + ">" + BLOB_BODY[s] +
    '</g><path d="M' + ax + " " + ay + "l.5 4.3M" + bx + " " + by + 'l.5 4.3" stroke="#121212" ' +
    'stroke-opacity=".82" stroke-width="2.3" stroke-linecap="round" fill="none"/></svg>';
}
const AGENTS = {
  warren: {name: T.agentWarren, role: T.agentWarrenRole, about: T.agentWarrenAbout,
           color: "--warren", shape: "circle"},
  scout: {name: T.agentScout, role: T.agentScoutRole, about: T.agentScoutAbout,
          color: "--scout", shape: "diamond"},
};
function avEl(color, shape, size, ring) {
  const s = h("span", "av" + (size ? " " + size : ""), blobSVG(color, shape, ring));
  s.setAttribute("aria-hidden", "true");
  return s;
}
const agentAv = (id, size, ring) => avEl(css(AGENTS[id].color), AGENTS[id].shape, size, ring);
const playerAv = (p, size) => avEl(colorOf(p), "circle", size);
// la liga entera: Warren, Scout y el primer jugador, montados (Connect the Bots)
function groupAv(size) {
  const s = h("span", "stack" + (size ? " " + size : ""));
  s.setAttribute("aria-hidden", "true");
  s.append(agentAv("warren", size, true), agentAv("scout", size, true), avEl(slotColor(0), "circle", size, true));
  return s;
}

// ==== piezas del hilo ======================================================
// Línea de sistema centrada («Mensajes de ● Warren y ● Scout»).
function sysLine(...parts) {
  const el = h("div", "sys");
  parts.forEach(p => el.append(typeof p === "string" ? document.createTextNode(p) : p));
  return el;
}
function sysTag(agentId) {
  const t = h("span", "tag");
  t.append(agentAv(agentId, "xs"), txt("b", null, AGENTS[agentId].name));
  return t;
}
// Tu mensaje: burbuja clara a la derecha (con una reacción opcional).
function meBubble(text, react) {
  const el = txt("div", "me", text);
  if (react) el.appendChild(txt("span", "react", react));
  return el;
}
// Píldoras de acción: la rellena es la principal (como «Send email»).
function pill(label, onClick, fill) {
  const b = txt("button", "pill" + (fill ? " fill" : ""), label);
  b.type = "button";
  b.addEventListener("click", onClick);
  return b;
}
// Tarjeta adjunta: cabecera «etiqueta · título» y el cuerpo.
function card({lbl, ttl, end, body, cls, head}) {
  const c = h("section", "card" + (cls ? " " + cls : ""));
  if (head) c.appendChild(head);
  else if (lbl || ttl) {
    const hd = h("div", "card-h");
    if (lbl && (!ttl || norm(lbl) !== norm(bare(ttl)))) hd.appendChild(txt("span", "lbl", lbl));
    if (ttl) hd.appendChild(txt("span", "ttl", bare(ttl)));
    if (end) { const e = h("span", "end"); [].concat(end).forEach(x => e.append(x)); hd.appendChild(e); }
    c.appendChild(hd);
  }
  [].concat(body || []).forEach(x => x && c.appendChild(x));
  return c;
}
function qbtn(label, onClick) {
  const b = txt("button", "qbtn", "?");
  b.type = "button"; b.title = label; b.setAttribute("aria-label", label);
  b.addEventListener("click", onClick);
  return b;
}
// Un mensaje del agente: lo que dice, la línea de herramienta (✓ Ledger → …),
// sus tarjetas y sus acciones. Sin tarjeta que enseñar, no hay mensaje.
function bubble({say, sayHTML, tool, cards, acts, needsCard}) {
  const list = [].concat(cards || []).filter(Boolean);
  if (needsCard !== false && cards !== undefined && !list.length) return null;
  const b = h("div", "bub" + (list.length ? " has-card" : ""));
  if (say || sayHTML) b.appendChild(sayHTML ? h("p", "say", sayHTML) : txt("p", "say", say));
  if (tool) b.appendChild(tool);
  list.forEach(c => b.appendChild(c));
  const a = [].concat(acts || []).filter(Boolean);
  if (a.length) { const row = h("div", "acts"); a.forEach(x => row.appendChild(x)); b.appendChild(row); }
  return b;
}
function toolLine(name, result) {
  const el = h("div", "tool");
  el.append(txt("span", "ok", "✓"), txt("b", null, name), document.createTextNode(" → " + result));
  return el;
}
// Un intercambio: tu pregunta (opcional) y la respuesta del agente.
function exchange(key, agentId, question, bubbles, react) {
  const list = bubbles.filter(Boolean);
  if (!list.length) return null;
  const ex = h("div", "ex");
  ex.id = "ex-" + key;
  ex.dataset.agent = agentId;
  if (question) ex.appendChild(meBubble(question, react));
  const g = h("div", "grp");
  const who = h("div", "who");
  who.append(agentAv(agentId, "sm"), txt("b", null, AGENTS[agentId].name),
             document.createTextNode(AGENTS[agentId].role));
  g.appendChild(who);
  list.forEach(b => g.appendChild(b));
  ex.appendChild(g);
  return ex;
}

// ---- listados largos: 5 filas y el resto detrás de «ver más» --------------
const LIST_MAX = 5;
function collapseList(rows, host) {
  if (!host) return;
  const old = host.querySelector(":scope > .more");
  if (old) old.remove();
  if (rows.length <= LIST_MAX) return;
  const extra = rows.slice(LIST_MAX);
  extra.forEach(r => r.classList.add("xtra"));
  const btn = txt("button", "more", T.showMore(extra.length));
  btn.type = "button";
  btn.setAttribute("aria-expanded", "false");
  btn.addEventListener("click", () => {
    const open = btn.getAttribute("aria-expanded") === "true";
    extra.forEach(r => r.classList.toggle("xtra", open));
    btn.setAttribute("aria-expanded", open ? "false" : "true");
    btn.textContent = open ? T.showMore(extra.length) : T.showLess;
  });
  host.appendChild(btn);
}

// ==== gráficas =============================================================
// Curvas suaves: spline cúbico *monótono* (Fritsch–Carlson). Se van los picos
// angulosos sin inventarse subidas ni bajadas: entre dos puntos nunca se sale
// de su rango y en cada máximo o mínimo la pendiente es 0.
function smoothD(pts) {
  const n = pts.length;
  if (!n) return "";
  const P = i => pts[i][0].toFixed(2) + " " + pts[i][1].toFixed(2);
  if (n === 1) return "M" + P(0);
  const dx = [], sl = [], m = [];
  for (let i = 0; i < n - 1; i++) {
    dx.push(pts[i + 1][0] - pts[i][0]);
    sl.push(dx[i] === 0 ? 0 : (pts[i + 1][1] - pts[i][1]) / dx[i]);
  }
  m[0] = sl[0];
  for (let i = 1; i < n - 1; i++) m[i] = sl[i - 1] * sl[i] <= 0 ? 0 : (sl[i - 1] + sl[i]) / 2;
  m[n - 1] = sl[n - 2];
  for (let i = 0; i < n - 1; i++) {
    if (sl[i] === 0) { m[i] = 0; m[i + 1] = 0; continue; }
    const a = m[i] / sl[i], b = m[i + 1] / sl[i];
    const hh = Math.hypot(a, b);
    if (hh > 3) { m[i] = (3 * a / hh) * sl[i]; m[i + 1] = (3 * b / hh) * sl[i]; }
  }
  let d = "M" + P(0);
  for (let i = 0; i < n - 1; i++) {
    const t = dx[i] / 3;
    d += " C" + (pts[i][0] + t).toFixed(2) + " " + (pts[i][1] + m[i] * t).toFixed(2) +
      " " + (pts[i + 1][0] - t).toFixed(2) + " " + (pts[i + 1][1] - m[i + 1] * t).toFixed(2) +
      " " + P(i + 1);
  }
  return d;
}
function sparkSVG(values, color, id, opts) {
  const W = 100, H = 40, pad = 3;
  // con línea base en 0 una serie casi plana no se estira a toda la altura
  let mn = Math.min(...values), mx = Math.max(...values);
  if (opts && opts.baseline0) { mn = Math.min(0, mn); mx = Math.max(0, mx); }
  if (mx === mn) { mx += 1; mn -= 1; }
  const xs = i => values.length < 2 ? W / 2 : (i / (values.length - 1)) * W;
  const ys = v => pad + (1 - (v - mn) / (mx - mn)) * (H - 2 * pad);
  const pts = values.map((v, i) => [xs(i), ys(v)]);
  const line = smoothD(pts);
  const area = line + " L" + xs(values.length - 1).toFixed(2) + " " + H +
    " L" + xs(0).toFixed(2) + " " + H + " Z";
  return '<svg class="spark" viewBox="0 0 ' + W + " " + H + '" preserveAspectRatio="none" aria-hidden="true">' +
    '<defs><linearGradient id="sg' + id + '" x1="0" y1="0" x2="0" y2="1">' +
    '<stop offset="0" stop-color="' + color + '" stop-opacity="0.32"/>' +
    '<stop offset="1" stop-color="' + color + '" stop-opacity="0"/>' +
    "</linearGradient></defs>" +
    '<path d="' + area + '" fill="url(#sg' + id + ')"/>' +
    '<path d="' + line + '" fill="none" stroke="' + color + '" stroke-width="2.2" ' +
    'vector-effect="non-scaling-stroke" stroke-linejoin="round" stroke-linecap="round"/></svg>';
}
function niceTicks(lo, hi, n) {
  const span = hi - lo, step0 = span / n, mag = Math.pow(10, Math.floor(Math.log10(step0)));
  const step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(s => span / s <= n) || 10 * mag;
  const out = []; for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) out.push(v);
  return out;
}
// Evolución de *todos* los jugadores dentro de un mes (cada uno con su color).
// El acumulado arranca en 0 el primer día: es la carrera de ese mes. Mide en
// px reales del contenedor, así que se pinta ya montada en la página.
function monthChart(host, info) {
  const NSm = "http://www.w3.org/2000/svg";
  const mk = (tag, attrs) => { const e = document.createElementNS(NSm, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]); return e; };
  const dates = info.dates || [], series = info.series || [];
  host.innerHTML = "";
  if (!dates.length || !series.length) return;
  const W = Math.max(260, Math.round(host.clientWidth || 600));
  const narrow = W < 520;
  const H = narrow ? 180 : 210;
  const M = {t: 12, r: 12, b: 24, l: narrow ? 40 : 46};
  let lo = 0, hi = 0;
  series.forEach(s => s.cum.forEach(v => {
    if (v === null) return; lo = Math.min(lo, v); hi = Math.max(hi, v); }));
  if (hi === lo) { hi += 1; lo -= 1; }
  const padv = (hi - lo) * 0.12; hi += padv; lo -= padv;
  const Y = v => M.t + (1 - (v - lo) / (hi - lo)) * (H - M.t - M.b);
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
  niceTicks(lo, hi, 4).forEach(v => {
    const isZero = Math.abs(v) < 1e-9;
    svg.appendChild(mk("line", {x1: M.l, x2: W - M.r, y1: Y(v), y2: Y(v),
      stroke: isZero ? css("--baseline") : css("--grid"), "stroke-width": 1}));
    const t = mk("text", {x: M.l - 8, y: Y(v) + 4, "text-anchor": "end",
      fill: css("--muted"), "font-size": 11, style: "font-variant-numeric:tabular-nums"});
    t.textContent = (v > 0 ? "+" : "") + v.toFixed(Math.abs(v) < 10 && v % 1 ? 1 : 0) + "%";
    svg.appendChild(t);
  });
  const stepX = Math.max(1, Math.round(dates.length /
    Math.max(2, Math.round((W - M.l - M.r) / 110))));
  dates.forEach((d, i) => {
    const isLast = i === dates.length - 1;
    if (!isLast && (i % stepX !== 0 || dates.length - 1 - i < stepX * 0.6)) return;
    const clip = isLast && X(i) + 32 > W;
    const t = mk("text", {x: clip ? W - 2 : X(i), y: H - 7, "text-anchor": clip ? "end" : "middle",
      fill: css("--muted"), "font-size": 11});
    t.textContent = fmtDate(d);
    svg.appendChild(t);
  });
  series.forEach(s => {
    const c = slotColor(s.slot);
    const pts = dates.map((d, i) => s.cum[i] === null || s.cum[i] === undefined
      ? null : [X(i), Y(s.cum[i])]).filter(Boolean);
    if (!pts.length) return;
    if (pts.length > 1) svg.appendChild(mk("path", {d: smoothD(pts), fill: "none", stroke: c,
      "stroke-width": 2.2, "stroke-linejoin": "round", "stroke-linecap": "round"}));
    const end = pts[pts.length - 1];
    svg.appendChild(mk("circle", {cx: end[0], cy: end[1], r: 3.6, fill: c,
      stroke: css("--card"), "stroke-width": 2.5}));
  });
  if (showEnds) ends.forEach(e => {
    const t = mk("text", {x: W - M.r + 6, y: e.yy + 4, fill: css("--ink-2"), "font-size": 11,
      style: "font-variant-numeric:tabular-nums;font-weight:600"});
    t.textContent = fmtPct(e.value);
    svg.appendChild(t);
  });
  host.appendChild(svg);
}
// Leyenda del mes: cada jugador con su color y su % del mes, de mejor a peor.
function monthLegend(info) {
  const host = h("div", "legend");
  const series = info.series || [];
  if (series.length < 2) return null;
  series.forEach((s, i) => {
    const el = h("span", "clk"); el.dataset.player = s.id;
    const key = h("span", "key"); key.style.background = slotColor(s.slot);
    el.appendChild(key);
    if (i === 0) el.appendChild(txt("span", "mtrophy", "🏆"));
    el.appendChild(document.createTextNode(s.name));
    el.appendChild(txt("span", "mval " + (s.value >= 0 ? "pos" : "neg"), fmtPct(s.value)));
    host.appendChild(el);
  });
  return host;
}
function chartHost(info) {
  const host = h("div", "mchart");
  CHARTS.push([host, info]);
  return host;
}
function paintCharts() { CHARTS.forEach(([host, info]) => { if (host.isConnected) monthChart(host, info); }); }

// ---- carteras: tarta (cada porción = su peso real) ------------------------
// Color de cada ticker: la paleta de los blobs, repartida por orden de
// aparición para que dos porciones vecinas nunca repitan color.
const TICKER_PALETTE = ["--g1","--g4","--g3","--g8","--g5","--g6","--g7","--g2"];
let TICKER_COLOR = {}, tickerNext = 0;
function tickerColor(t) {
  if (!(t in TICKER_COLOR)) TICKER_COLOR[t] = TICKER_PALETTE[tickerNext++ % TICKER_PALETTE.length];
  return css(TICKER_COLOR[t]);
}
function allocItems(all) {
  if (all.length <= 6) return all;
  const rest = all.slice(5).reduce((s, x) => s + x.w, 0);
  return all.slice(0, 5).concat([{ticker: T.others, w: Math.round(rest * 100) / 100, other: true}]);
}
function donutSVG(items, count, size) {
  const S = size || 128, sw = S < 120 ? 15 : 18;
  const cx = S / 2, cy = S / 2, r = (S - sw) / 2 - 1, C = 2 * Math.PI * r;
  const drawn = items.filter(x => x.w > 0);
  const gap = drawn.length > 1 ? 2 : 0;
  let acc = 0;
  const segs = drawn.map(x => {
    const col = x.other ? css("--muted") : tickerColor(x.ticker);
    const frac = x.w / 100;
    const len = Math.max(0.5, frac * C - gap);
    const off = (-acc * C).toFixed(2);
    acc += frac;
    return '<circle cx="' + cx + '" cy="' + cy + '" r="' + r.toFixed(2) +
      '" fill="none" stroke="' + col + '" stroke-width="' + sw +
      '" stroke-dasharray="' + len.toFixed(2) + " " + (C - len).toFixed(2) +
      '" stroke-dashoffset="' + off + '"><title>' + x.ticker + " · " + fmtW(x.w) + "</title></circle>";
  }).join("");
  const big = S < 120 ? 19 : 22;
  const center = count
    ? '<text x="' + cx + '" y="' + (cy - 1) + '" text-anchor="middle" class="donut-center" font-size="' +
      big + '">' + count + "</text>" +
      '<text x="' + cx + '" y="' + (cy + 14) + '" text-anchor="middle" class="donut-sub" font-size="10.5">' +
      T.assets(count) + "</text>"
    : "";
  return '<svg class="donut" width="' + S + '" height="' + S + '" viewBox="0 0 ' + S + " " + S +
    '" role="img" aria-label="' + T.donutAria + '"><g transform="rotate(-90 ' + cx + " " + cy + ')">' +
    segs + "</g>" + center + "</svg>";
}
function donutEl(all, size) {
  const items = allocItems(all);
  const wrap = h("div", "donut-wrap", donutSVG(items, all.length, size));
  const ul = h("ul", "donut-legend");
  items.forEach(x => {
    const li = h("li", "dl");
    if (!x.other && TICKERS[x.ticker]) { li.classList.add("clk"); li.dataset.ticker = x.ticker; }
    const dot = h("span", "dot"); dot.style.background = x.other ? css("--muted") : tickerColor(x.ticker);
    li.append(dot, txt("span", "tk", x.ticker), txt("span", "w", fmtW(x.w)));
    ul.appendChild(li);
  });
  wrap.appendChild(ul);
  return wrap;
}

// ---- logos de empresa (logo.dev) con monograma de respaldo ----------------
const LOGO_TOKEN = "pk_cgMPtdfzT5GGEORKN4rMDA";   // token publicable, pensado para el frontend
function monoEl(text, size, bg) {
  const m = txt("span", "mono", (text || "?").slice(0, 2).toUpperCase());
  m.style.width = m.style.height = size + "px";
  m.style.fontSize = Math.round(size * 0.38) + "px";
  m.style.background = bg;
  return m;
}
function tickerLogoEl(t, size) {
  const bg = tickerColor(t.ticker);
  if (!t.ticker) return monoEl(t.ticker, size, bg);
  const img = document.createElement("img");
  img.className = "logo"; img.width = img.height = size; img.alt = "";
  img.loading = "lazy"; img.referrerPolicy = "no-referrer";
  img.src = "https://img.logo.dev/ticker/" + encodeURIComponent(t.ticker) +
    "?token=" + LOGO_TOKEN + "&size=" + size + "&retina=true&format=png";
  img.onerror = () => img.replaceWith(monoEl(t.ticker, size, bg));
  return img;
}

// ---- enlaces externos: siempre en otra ventana ----------------------------
// Con la web instalada como app (``display: standalone``) un target=_blank se
// abriría dentro de la app, sin barra ni botón de atrás: ahí se abre con
// ``window.open``, que salta al navegador.
const STANDALONE = (() => {
  try {
    return ["standalone", "fullscreen", "minimal-ui"].some(
      m => window.matchMedia("(display-mode: " + m + ")").matches)
      || window.navigator.standalone === true;
  } catch (e) { return false; }
})();
function externalLink(href) {
  const a = document.createElement("a");
  a.href = href; a.target = "_blank"; a.rel = "noopener noreferrer";
  if (STANDALONE) a.addEventListener("click", ev => {
    ev.preventDefault();
    window.open(href, "_blank", "noopener,noreferrer");
  });
  return a;
}
const DATE_RE = /^\d{4}-\d{2}-\d{2}/;
// Titulares de varios valores, sin repetidos y **repartidos por rondas**: el
// más reciente de cada valor, luego el segundo de cada uno… Así las primeras
// filas no se llenan con la empresa que más haya publicado ese día.
function newsFor(syms, max) {
  const seen = {}, queues = [];
  syms.forEach(sym => {
    const queue = [];
    ((TICKERS[sym] || {}).news || []).forEach(n => {
      if (seen[n.link]) return;
      seen[n.link] = 1;
      queue.push(Object.assign({sym: sym}, n));
    });
    queue.sort((a, b) => (b.at || "").localeCompare(a.at || ""));
    if (queue.length) queues.push(queue);
  });
  const out = [];
  while (queues.length && (!max || out.length < max)) {
    queues.sort((a, b) => (b[0].at || "").localeCompare(a[0].at || ""));
    queues.forEach(q => out.push(q.shift()));
    for (let i = queues.length - 1; i >= 0; i--) if (!queues[i].length) queues.splice(i, 1);
  }
  return max ? out.slice(0, max) : out;
}
// Fila de titular: todo por textContent (viene de una API de terceros).
function newsRowEl(n, withLogo) {
  const row = externalLink(n.link);
  row.className = "li nw-row";
  if (withLogo) row.appendChild(tickerLogoEl(TICKERS[n.sym] || {ticker: n.sym}, 30));
  const body = h("div", "nw-b");
  body.appendChild(txt("div", "nw-t", n.title));
  const meta = h("div", "nw-m");
  if (n.sym) meta.appendChild(txt("span", "sym", n.sym));
  const bits = [];
  if (n.source) bits.push(n.source);
  if (n.at && DATE_RE.test(n.at)) bits.push(fmtDate(n.at.slice(0, 10)));
  if (bits.length) meta.appendChild(document.createTextNode((n.sym ? " · " : "") + bits.join(" · ")));
  if (meta.childNodes.length) body.appendChild(meta);
  row.appendChild(body);
  return row;
}
// Enlaces de búsqueda por símbolo: no dependen de que la API respondiera.
function newsLinksEl(sym) {
  const q = encodeURIComponent(sym + " stock");
  const box = h("div", "news-links");
  [["Yahoo Finance", "https://finance.yahoo.com/quote/" + encodeURIComponent(sym)],
   ["Google News", "https://news.google.com/search?q=" + q],
   ["Finviz", "https://finviz.com/quote.ashx?t=" + encodeURIComponent(sym)]].forEach(([label, href]) => {
    const a = externalLink(href);
    a.append(document.createTextNode(label + " "), txt("span", "ext", "↗"));
    box.appendChild(a);
  });
  return box;
}
function newsSectionEl(title, items, sym) {
  const list = h("div");
  items.forEach(n => list.appendChild(newsRowEl(n, false)));
  const sec = sectionEl(title, list);
  sec.appendChild(newsLinksEl(sym));
  return sec;
}

// ==== módulos: cada uno devuelve su tarjeta, o null si no hay nada =========
let AFTER = [];   // lo que necesita la tarjeta ya montada (medidas, carrusel)

// Cabecera de un Gran Premio: enlaza a la web oficial del destino.
function gpBanner(cls, href, aria, kicker, main, sub, icon) {
  const a = externalLink(href);
  a.className = "gpban " + cls;
  a.setAttribute("aria-label", aria);
  a.innerHTML = '<span class="cicon" aria-hidden="true"></span><span class="ctext">' +
    '<span class="ckicker"></span><span class="cmain"></span><span class="csub"></span></span>' +
    '<span class="carrow" aria-hidden="true">→</span>';
  a.querySelector(".cicon").textContent = icon;
  a.querySelector(".ckicker").textContent = kicker;
  a.querySelector(".cmain").textContent = main;
  a.querySelector(".csub").textContent = sub;
  return a;
}
// Quién va ganando (la general o el mes): su color, su % y la ventaja en
// puntos sobre el segundo. Abre su ficha.
function leadBlock(p, value, gap, kicker, leaf) {
  const row = h("div", "gp-lead clk");
  row.dataset.player = p.id;
  row.appendChild(playerAv(p, "lg"));
  const l = h("div", "gp-l");
  l.appendChild(txt("div", "kicker", kicker));
  const nm = h("div", "gp-name");
  nm.append(txt("span", null, p.name), txt("span", "leaf", leaf));
  l.append(nm, txt("div", "gp-gap", gap));
  row.append(l, txt("div", "gp-cum num " + (value >= 0 ? "pos" : "neg"), fmtPct(value)));
  return row;
}
// El resto del podio (2º y 3º), en fichas que abren la ficha del jugador.
function podiumEl(list) {
  if (!list.length) return null;
  const box = h("div", "gp-podium");
  list.forEach((p, i) => {
    const chip = h("div", "gp-chip clk");
    chip.dataset.player = p.id;
    chip.append(playerAv(p, "sm"), txt("span", "m", MEDALS[i + 1]), txt("span", "n ell", p.name),
                txt("span", "v " + (p.value >= 0 ? "pos" : "neg"), fmtPct(p.value)));
    box.appendChild(chip);
  });
  return box;
}

// ---- Canada Grand Prix 26/27: la clasificación general --------------------
// El viaje es el premio de la general: el banner de Canadá hace de cabecera,
// debajo va quién lo lleva ganado y su podio, y luego la parrilla completa.
function standingsCard() {
  const body = [];
  const leader = ranked[0];
  if (leader) {
    const second = ranked[1];
    const last = lastOf(leader);
    body.push(leadBlock(leader, last.cum,
      second ? T.gpGap(second.name, (last.cum - lastOf(second).cum).toFixed(2)) : T.gpSolo,
      T.gpLeading, "🍁"));
    body.push(podiumEl(ranked.slice(1, 3).map(p =>
      ({id: p.id, name: p.name, slot: p.slot, value: lastOf(p).cum}))));
  }
  const sub = h("div", "sub-h");
  sub.append(txt("span", null, T.ranking), qbtn(T.calcHelpAria, openLeaderHelp));
  body.push(sub);
  const t = document.createElement("table");
  t.id = "standings";
  const head = t.insertRow();
  T.rankCols.forEach((x, i) => { const th = txt("th", i === 1 ? "name" : null, x); head.appendChild(th); });
  if (!ranked.length) {
    const td = txt("td", "empty", T.noPlayers); td.colSpan = T.rankCols.length;
    t.insertRow().appendChild(td);
  }
  ranked.forEach((p, i) => {
    const last = lastOf(p);
    const tr = t.insertRow();
    tr.className = "clk" + (i === 0 ? " lead" : "");
    tr.dataset.player = p.id;
    tr.appendChild(txt("td", "rank", MEDALS[i] || String(i + 1)));
    const name = h("td", "name");
    const key = h("span", "key"); key.style.background = colorOf(p);
    name.append(key, document.createTextNode(p.name));
    tr.append(name, txt("td", "big " + (last.cum >= 0 ? "pos" : "neg"), fmtPct(last.cum)),
              txt("td", last.day >= 0 ? "pos" : "neg", fmtPct(last.day)));
  });
  const over = h("div", "overx"); over.appendChild(t);
  body.push(over);
  const c = card({head: gpBanner("ca-banner", T.caHref, T.caAria, T.caTitle, T.gpTitle, T.caSub, "🍁"), body});
  c.id = "hero-card";
  if (leader) c.style.setProperty("--lead", colorOf(leader));
  return c;
}

// ---- mejor de la última sesión --------------------------------------------
// Con empate en el % del día, desempata el acumulado.
const bestOfDay = () => DATA.players.length ? [...DATA.players].sort((a, b) =>
  (lastOf(b).day - lastOf(a).day) || (lastOf(b).cum - lastOf(a).cum))[0] : null;
// «Mercado cerrado»: madrugada o mañana de un día laborable en Madrid, antes de
// que abra EE. UU. (~15:30) y sin jornada de hoy. Entonces el dato es el de la
// última sesión cerrada y se dice.
function marketClosedFor(bd) {
  const mp = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/Madrid", weekday: "short", year: "numeric", month: "2-digit",
    day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  }).formatToParts(new Date());
  const gp = t => (mp.find(x => x.type === t) || {}).value;
  const madridDate = gp("year") + "-" + gp("month") + "-" + gp("day");
  const isWeekday = gp("weekday") !== "Sat" && gp("weekday") !== "Sun";
  const hh = +gp("hour"), mm = +gp("minute");
  const preOpen = hh < 15 || (hh === 15 && mm < 30);
  return isWeekday && preOpen && bd.date !== madridDate;
}
function bestCard(best) {
  // si todos empatan a 0 en la jornada, el «mejor del día» no cuenta nada
  if (!best || DATA.players.every(p => Math.abs(lastOf(p).day) < 0.005)) return null;
  const bd = lastOf(best);
  const end = marketClosedFor(bd) ? txt("span", "closed-tag", "🚧 " + T.marketClosed) : null;
  const hl = h("div", "headline clk");
  hl.dataset.dayDate = bd.date; hl.dataset.dayPlayer = best.id;
  const g = h("div", "grow");
  g.appendChild(txt("div", "kicker", T.bestOfDay));
  const nm = h("div", "nm"); nm.append(txt("span", null, best.name), txt("span", null, "🥇"));
  g.appendChild(nm);
  hl.append(playerAv(best, "lg"), g, txt("div", "big num " + (bd.day >= 0 ? "pos" : "neg"), fmtPct(bd.day)));
  const c = card({lbl: T.lbl.session, ttl: fmtDate(bd.date), end: end || [], body: [hl]});
  c.id = "best-card";
  return c;
}

// ---- campeón de cada día del mes en curso ---------------------------------
function dailyCard() {
  const dw = DATA.dailyWinners || {};
  const rows = dw.rows || [];
  if (!rows.length) return null;
  const t = document.createElement("table");
  t.id = "daily";
  const head = t.insertRow();
  T.dailyCols.forEach((x, i) => head.appendChild(txt("th", i === 1 ? "name" : null, x)));
  const trs = rows.map(r => {
    const tr = t.insertRow();
    // la fila abre el detalle del día del campeón (por valor + el resto)
    tr.className = "clk";
    tr.dataset.dayDate = r.date;
    tr.dataset.dayPlayer = (r.ids && r.ids[0]) || "";
    tr.appendChild(txt("td", null, fmtDate(r.date)));
    const name = h("td", "name");
    if (r.slot !== null && r.slot !== undefined) {
      const key = h("span", "key"); key.style.background = slotColor(r.slot); name.appendChild(key);
    }
    name.appendChild(document.createTextNode(r.names.join(", ")));
    tr.append(name, txt("td", r.value >= 0 ? "pos" : "neg", fmtPct(r.value)));
    return tr;
  });
  const over = h("div", "overx"); over.appendChild(t);
  const c = card({lbl: T.lbl.daily, ttl: T.dailyTitle(monthLabel(dw.month, dw.month_year)), body: [over]});
  c.id = "daily-card";
  collapseList(trs, c);
  return c;
}

// ---- quién invita y **dónde**: la escala del restaurante ------------------
// El ganador del mes paga la comida y su rentabilidad decide el sitio; la
// escala viaja entera en la API (``treatScale``) y cada mes trae su peldaño.
const treatMoney = v => new Intl.NumberFormat(LANG_META.locale,
  {style: "currency", currency: "EUR", maximumFractionDigits: 0}).format(v);
const treatPct = v => (v > 0 ? "+" : "") + (v % 1 ? v.toFixed(1) : v.toFixed(0)) + "%";
function treatRange(i) {
  const scale = DATA.treatScale || [];
  const lo = scale[i].min;
  const hi = i + 1 < scale.length ? scale[i + 1].min : null;
  if (lo === null || lo === undefined) return T.treatUnder(treatPct(hi));
  if (hi === null || hi === undefined) return T.treatFrom(treatPct(lo));
  return treatPct(lo) + " – " + treatPct(hi);
}
function treatNote(info, live) {
  const scale = DATA.treatScale || [];
  if (!scale[info.treat]) return null;
  const note = h("div", "treat");
  note.appendChild(document.createTextNode(live ? T.lunchNoteLive : T.lunchNote));
  const b = h("button", "tchip");
  b.type = "button"; b.title = T.treatHelpAria; b.setAttribute("aria-label", T.treatHelpAria);
  b.append(txt("span", "eur", scale[info.treat].euros), document.createTextNode(T.treatTiers[info.treat]));
  b.addEventListener("click", () => openTreatHelp(info));
  note.appendChild(b);
  return note;
}

// ---- Gran Premio de la ciudad de Vancouver: el mes en curso ---------------
function monthCurCard(info) {
  if (!info) return null;
  const ml = monthLabel(info.month, info.month_year);
  const series = info.series || [];
  const leader = series[0];
  const body = [];
  if (leader) {
    const second = series[1];
    body.push(leadBlock(leader, leader.value,
      second ? T.gpGap(second.name, (leader.value - second.value).toFixed(2)) : T.gpSolo,
      T.vgpLeading, "🏆"));
  }
  body.push(treatNote(info, true), podiumEl(series.slice(1, 3)));
  const sub = h("div", "sub-h");
  sub.append(txt("span", null, T.winnerOf(ml)), qbtn(T.treatHelpAria, () => openTreatHelp(info)));
  body.push(sub, chartHost(info), monthLegend(info));
  const c = card({head: gpBanner("vc-banner", T.vcHref, T.vcAria, T.vcTitle, T.vgpTitle(ml), T.vcSub, "🏙️"), body});
  c.id = "month-cur-card";
  return c;
}
// El mes pasado ya está cerrado: titular (quién ganó y con cuánto) y su
// gráfica detrás de «ver más».
function monthPrevCard(info) {
  if (!info) return null;
  const ml = monthLabel(info.month, info.month_year);
  const hl = h("div", "headline clk");
  hl.dataset.player = info.series && info.series[0] ? info.series[0].id : "";
  const g = h("div", "grow");
  const nm = h("div", "nm"); nm.append(txt("span", null, info.name), txt("span", null, "🏆"));
  g.appendChild(nm);
  hl.append(avEl(slotColor(info.slot), "circle", "lg"), g,
            txt("div", "big num " + (info.value >= 0 ? "pos" : "neg"), fmtPct(info.value)));
  const c = card({lbl: T.lbl.prev, ttl: T.winnerOf(ml), end: qbtn(T.treatHelpAria, () => openTreatHelp(info)),
                  body: [hl, treatNote(info, false)]});
  c.id = "month-prev-card";
  return c;
}

// ---- detalle mensual: una fila por mes y jugador (solo rentabilidad) -------
function monthlyDetailCard() {
  if (!ranked.length) return null;
  const box = h("div");
  ranked.forEach(p => {
    const det = document.createElement("details");
    const sum = document.createElement("summary");
    sum.append(playerAv(p, "sm"), document.createTextNode(p.name));
    det.appendChild(sum);
    const over = h("div", "overx");
    const t = document.createElement("table");
    const head = t.insertRow();
    T.detailCols.forEach(x => head.appendChild(txt("th", null, x)));
    const trs = (p.months || []).map(mo => {
      const tr = t.insertRow();
      tr.appendChild(txt("td", null, monthLabel(mo.month, mo.month_year)));
      [mo.ret, mo.cum].forEach(v => tr.appendChild(txt("td", v > 0 ? "pos" : (v < 0 ? "neg" : ""), fmtPct(v))));
      return tr;
    });
    over.appendChild(t); det.appendChild(over); box.appendChild(det);
    collapseList(trs, det);
  });
  const c = card({lbl: T.lbl.detail, ttl: T.monthlyDetailTitle, body: [box]});
  c.id = "monthly-card";
  return c;
}

// ---- insights automáticos: plantillas con hueco para los jugadores --------
// Cada una con su condición; se enseñan tres y van rotando.
function computeInsights() {
  const ps = DATA.players.filter(p => p.days && p.days.length);
  if (!ps.length) return [];
  const lastp = p => p.days[p.days.length - 1];
  const rk = [...ps].sort((a, b) => lastp(b).cum - lastp(a).cum);
  const byDay = [...ps].sort((a, b) => lastp(b).day - lastp(a).day);
  const n = ps.length;
  const leader = rk[0], second = rk[1], tail = rk[n - 1];
  const bestDay = byDay[0], worstDay = byDay[n - 1];
  const esc = s => String(s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
  const who = p => '<b style="color:' + colorOf(p) + '">' + esc(p.name) + "</b>";
  const pts = v => T.points(v);
  const I = T.ins;
  const streak = (p, positive) => { let c = 0; for (let i = p.days.length - 1; i >= 0; i--) {
    const d = p.days[i].day; if (positive ? d > 0 : d < 0) c++; else break; } return c; };
  const greenCount = (p, k) => p.days.slice(-k).filter(d => d.day > 0).length;
  const totalDelta = p => lastp(p).cum - p.days[0].cum;
  const range = p => { const c = p.days.map(d => d.cum); return Math.max(...c) - Math.min(...c); };
  const recovered = p => p.days.length >= 2 && lastp(p).day > 0 && p.days[p.days.length - 2].day < 0;
  const allNeg = ps.every(p => lastp(p).day < 0);
  const allPos = ps.every(p => lastp(p).day > 0);
  const out = [];
  const add = (prio, icon, html) => out.push({prio, icon, html});

  if (n >= 2) {
    const g = lastp(leader).cum - lastp(second).cum;
    if (g > 0.05) add(9.5, "🔥", I.leaderFire(who(leader), pts(g), who(second)));
    if (g > 3) add(6.7, "🧱", I.leaderPullAway(who(leader)));
  }
  add(6.0, lastp(leader).cum >= 0 ? "👑" : "🏳️", I.leaderLeads(who(leader), fmtPct(lastp(leader).cum)));
  add(4.6, "🧭", I.leaderHelm(who(leader)));
  if (lastp(leader).day > 0) add(6.9, "🛰️", I.leaderUnstoppable(who(leader), fmtPct(lastp(leader).day)));
  if (leader === bestDay && lastp(leader).day > 0)
    add(8.5, "🚀", I.leaderPerfect(who(leader), fmtPct(lastp(leader).day)));
  { const s = streak(leader, true); if (s >= 2) add(7.0, "📈", I.leaderGreenStreak(who(leader), s)); }
  if (n >= 2) {
    const g = lastp(leader).cum - lastp(tail).cum;
    if (g > 5) add(6.5, "🏁", I.raceFinish(who(leader), pts(g), who(tail)));
    add(4.8, "📐", I.overallGap(who(leader), who(tail), pts(g)));
    add(4.4, "🛡️", I.leaderDefends(who(leader), who(tail)));
    add(4.2, "🎙️", I.pulse(who(leader), who(second)));
  }
  if (bestDay && lastp(bestDay).day > 0) add(7.5, "⚡", I.bestSession(who(bestDay), fmtPct(lastp(bestDay).day)));
  if (n >= 2 && lastp(worstDay).day < 0) add(6.5, "🧊", I.worstDrop(who(worstDay), fmtPct(lastp(worstDay).day)));
  if (n >= 2 && allNeg) add(7.2, "📉", I.allRed());
  if (n >= 2 && allPos) add(7.2, "🟢", I.allGreen());
  ps.forEach(p => { if (p !== leader && lastp(p).day >= 2) add(6.6, "✨", I.surprise(who(p), fmtPct(lastp(p).day))); });
  ps.forEach(p => { if (p !== worstDay && lastp(p).day <= -2) add(5.6, "🪂", I.deflate(who(p), fmtPct(lastp(p).day))); });
  ps.forEach(p => { if (recovered(p)) add(5.7, "🌤️", I.backToGreen(who(p), fmtPct(lastp(p).day))); });
  if (n >= 2) { const g = lastp(rk[0]).cum - lastp(rk[1]).cum;
    if (g >= 0 && g < 1.5) add(8.0, "🥊", I.duelTop(who(rk[0]), who(rk[1]), pts(g))); }
  for (let i = 0; i < n - 1; i++) { const g = lastp(rk[i]).cum - lastp(rk[i + 1]).cum;
    if (g >= 0 && g < 0.3) add(7.0, "📸", I.photoFinish(who(rk[i]), who(rk[i + 1]), pts(g))); }
  for (let i = 0; i < n - 1; i++) { const up = rk[i], lo = rk[i + 1];
    const g = lastp(up).cum - lastp(lo).cum, diff = lastp(lo).day - lastp(up).day;
    if (diff > 0.5 && g < 6) add(6.8, "🔀", I.cutsGround(who(lo), who(up), pts(diff))); }
  ps.forEach(p => { const s = streak(p, false); if (s >= 2) add(6.0 + s * 0.2, "🌧️", I.redStreak(who(p), s)); });
  ps.forEach(p => { if (p === leader) return; const s = streak(p, true); if (s >= 3) add(6.4, "🔋", I.holdsFirm(who(p), s)); });
  ps.forEach(p => { const d = totalDelta(p); if (d > 3) add(6.0 + Math.min(d, 10) / 10, "🛫", I.onARoll(who(p), pts(d))); });
  ps.forEach(p => { const k = Math.min(5, p.days.length); if (k >= 4 && greenCount(p, k) >= 4)
    add(5.8, "✅", I.sharp(who(p), greenCount(p, k), k)); });
  ps.forEach(p => { if (lastp(p).cum <= -2) add(5.2, "🧯", I.needsReact(who(p), fmtPct(lastp(p).cum))); });
  if (n >= 2 && lastp(tail).day > 0) add(5.5, "🌱", I.signsOfLife(who(tail), fmtPct(lastp(tail).day)));
  if (n >= 2) add(4.0, "⏳", I.bottomEarly(who(tail)));
  ps.forEach(p => { if (p.days.length >= 3 && range(p) >= 6) add(5.2, "🎢", I.rollercoaster(who(p), pts(range(p)))); });
  ps.forEach(p => { const hd = p.holdings; if (!hd || !hd.length) return;
    if (hd.length === 1) add(6.2, "🎯", I.allIn(who(p), hd[0].ticker));
    else if (hd[0].w >= 40) add(6.0, "⚠️", I.concentrates(who(p), fmtW(hd[0].w), hd[0].ticker)); });
  { const withH = ps.filter(p => p.holdings && p.holdings.length);
    if (withH.length) {
      const div = withH.slice().sort((a, b) => b.holdings.length - a.holdings.length)[0];
      if (div.holdings.length >= 4) add(5.4, "🧩", I.mostDiversified(who(div), div.holdings.length)); } }
  if (DATA.allocation && DATA.allocation.length) { const top = DATA.allocation[0];
    if (top.w >= 20) add(5.0, "📊", I.leagueLoaded(top.ticker, fmtW(top.w))); }
  out.sort((a, b) => b.prio - a.prio);
  return out;
}
function insightsCard() {
  const items = computeInsights();
  if (!items.length) return null;
  const box = h("div", "insights");
  const show = Math.min(3, items.length);
  let off = 0;
  const paint = () => {
    box.innerHTML = "";
    for (let k = 0; k < show; k++) {
      const it = items[(off + k) % items.length];
      box.appendChild(h("div", "insight", '<span class="ic">' + it.icon + '</span><span class="tx">' + it.html + "</span>"));
    }
  };
  paint();
  if (items.length > show) {
    insightTimer = setInterval(() => {
      [...box.children].forEach(c => c.style.opacity = "0");
      setTimeout(() => { off = (off + show) % items.length; paint(); }, 450);
    }, 7000);
  }
  const head = h("div", "card-h");
  const live = h("span", "end live");
  live.append(h("span", "pulse"), document.createTextNode(T.aiLive));
  head.append(txt("span", "ai-badge", T.aiBadge), txt("span", "ttl", T.insightsTitle), live);
  const c = card({head, body: [box]});
  c.id = "insights-card";
  return c;
}

// ---- sesión extendida: pre-market / after-hours valor a valor -------------
// Es la foto del momento del recálculo: lleva su hora, y si quien abre la
// página lo hace mucho después, la tarjeta no sale.
const EXT_MAX_AGE = 6 * 3600;  // segundos
const CUR_SYM = {USD: "$", EUR: "€", GBP: "£"};
const extLabel = session => session === "pre" ? T.extPre : T.extPost;
function extMoney(v, cur) {
  const n = Number(v).toLocaleString("en-US", {minimumFractionDigits: 2, maximumFractionDigits: 2});
  return CUR_SYM[cur] ? CUR_SYM[cur] + n : n + (cur ? " " + cur : "");
}
function fmtClock(epoch) {
  return new Intl.DateTimeFormat(LANG_META.clock, {
    timeZone: "Europe/Madrid", hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  }).format(new Date(epoch * 1000));
}
function extRows() {
  const m = DATA.market;
  const fresh = m && m.asOf && (Date.now() / 1000 - m.asOf) < EXT_MAX_AGE;
  if (!fresh) return [];
  return (DATA.tickers || []).filter(t => t.ext && t.ext.session === m.session && t.ext.pct != null)
    .sort((a, b) => b.ext.pct - a.ext.pct);
}
function extCard() {
  const rows = extRows();
  if (!rows.length) return null;
  const m = DATA.market;
  const end = h("span", "end");
  end.append(h("span", "pulse"), document.createTextNode(T.extAt(fmtClock(m.asOf))));
  const hl = h("div", "headline");
  const g = h("div", "grow");
  g.append(txt("div", "kicker", (m.pct == null ? T.extSession : T.extLeague) + " · " + T.extHoldings(rows.length)));
  hl.appendChild(g);
  if (m.pct != null) hl.appendChild(txt("div", "big num " + (m.pct >= 0 ? "pos" : "neg"), fmtPct(m.pct)));
  const list = h("div");
  const painted = rows.map(t => {
    const row = h("div", "li ext-row clk");
    row.dataset.ticker = t.ticker;
    const tk = h("div", "grow");
    tk.append(txt("div", "sym", t.ticker), txt("div", "sub ell", t.name));
    row.append(tickerLogoEl(t, 30), tk, txt("span", "px", extMoney(t.ext.price, t.ext.currency)),
               txt("span", "pct " + (t.ext.pct >= 0 ? "pos" : "neg"), fmtPct(t.ext.pct)));
    list.appendChild(row);
    return row;
  });
  collapseList(painted, list);
  const c = card({head: (() => { const hd = h("div", "card-h");
      hd.append(txt("span", "lbl", T.lbl.ext), txt("span", "ttl", (m.session === "pre" ? "🌅 " : "🌙 ") + extLabel(m.session)), end);
      return hd; })(),
    body: [hl, list, txt("div", "note", T.extNote)]});
  c.id = "ext-card";
  return c;
}

// ---- últimas operaciones de la liga ---------------------------------------
// Solo qué se compró o vendió, de qué valor y qué día: ni importes ni
// cantidades. La fila abre el valor; el nombre, la ficha del jugador.
function opsCard() {
  const ops = DATA.operations || [];
  if (!ops.length) return null;
  const list = h("div");
  const rows = ops.map(o => {
    const row = h("div", "li op-row");
    if (TICKERS[o.ticker]) { row.classList.add("clk"); row.dataset.ticker = o.ticker; }
    else if (o.id && PLAYERS[o.id]) { row.classList.add("clk"); row.dataset.player = o.id; }
    row.append(tickerLogoEl({ticker: o.ticker}, 30), txt("span", "sym", o.ticker),
               txt("span", "op-act " + (o.kind === "BUY" ? "buy" : "sell"), o.kind === "BUY" ? T.opBuy : T.opSell));
    const name = h("span", "op-name");
    if (o.id && PLAYERS[o.id]) { name.classList.add("clk"); name.dataset.player = o.id; }
    const key = h("span", "key"); key.style.background = slotColor(o.slot);
    name.append(key, txt("span", "nm", o.name));
    row.append(name, txt("span", "op-date", fmtDate(o.date)));
    list.appendChild(row);
    return row;
  });
  collapseList(rows, list);
  const c = card({lbl: T.lbl.trades, ttl: T.recentOps, body: [list]});
  c.id = "ops-card";
  return c;
}
const opsTool = () => {
  const ops = DATA.operations || [];
  return ops.length ? toolLine("Ledger", T.tradesCount(ops.length) + " · " +
    T.playersCount(new Set(ops.map(o => o.id)).size)) : null;
};

// ---- noticias de la liga --------------------------------------------------
const NEWS_HOME_MAX = 12;
const homeNews = () => newsFor((DATA.tickers || []).map(t => t.ticker), NEWS_HOME_MAX);
function newsCard() {
  const items = homeNews();
  if (!items.length) return null;
  const list = h("div");
  const rows = items.map(n => { const r = newsRowEl(n, true); list.appendChild(r); return r; });
  collapseList(rows, list);
  const c = card({lbl: T.lbl.news, ttl: T.leagueNews, body: [list, txt("div", "note", T.newsNote)]});
  c.id = "news-card";
  return c;
}
const newsTool = () => {
  const items = homeNews();
  if (!items.length) return null;
  const withNews = (DATA.tickers || []).filter(t => (t.news || []).length).length;
  return toolLine("Newswire", T.newsCount(items.length) + " · " + T.newsTickers(withNews));
};

// ---- carteras: la de la liga y la de cada jugador (solo pesos) ------------
function allocCard() {
  const all = DATA.allocation || [];
  if (!all.length) return null;
  const c = card({lbl: T.lbl.portfolio, ttl: T.leagueWallet,
                  body: [donutEl(all), h("div", "note", T.allocInsight(all[0].ticker, fmtW(all[0].w)))]});
  c.id = "alloc-card";
  return c;
}
function walletsCard() {
  const withHoldings = ranked.filter(p => p.holdings && p.holdings.length);
  if (!withHoldings.length) return null;
  const box = h("div");
  const wallets = withHoldings.map(p => {
    const wrap = h("div", "wallet");
    const head = h("div", "whead clk");
    head.dataset.player = p.id;
    head.append(playerAv(p, "sm"), txt("span", null, p.name),
                txt("span", "top", T.walletTop(p.holdings[0].ticker, fmtW(p.holdings[0].w))));
    wrap.append(head, donutEl(p.holdings, 104));
    box.appendChild(wrap);
    return wrap;
  });
  collapseList(wallets, box);
  const c = card({lbl: T.lbl.wallets, ttl: T.walletsTitle, body: [box]});
  c.id = "wallets-card";
  return c;
}

// ---- objetivo de la liga: avance de cada jugador + cuenta atrás -----------
// Solo se pinta la barra de quien publica su avance (``show_goal``): el %
// deja adivinar el importe. El resto sale con la barra en trama.
const goalMoney = v => new Intl.NumberFormat(LANG_META.locale,
  {style: "currency", currency: "EUR", maximumFractionDigits: 0}).format(v);
function goalCard() {
  const g = DATA.goal;
  if (!g || !ranked.length) return null;
  const count = h("span", "goal-count");
  count.append(txt("span", "num", String(g.days)),
               txt("span", "lbl", g.days === 0 ? T.goalToday : (g.days === 1 ? T.goalDay : T.goalDays)));
  const list = h("div");
  const rows = ranked.map((p, i) => ({p, i}))
    .sort((a, b) => ((b.p.goal ? b.p.goal.pct : -1) - (a.p.goal ? a.p.goal.pct : -1)) || (a.i - b.i));
  const painted = rows.map(({p}) => {
    const goal = (p.goal && p.goal.pct != null) ? p.goal : null;
    const row = h("div", "goal-row clk");
    row.dataset.player = p.id;
    const top = h("div", "goal-top");
    top.append(playerAv(p, "sm"), txt("span", "nm", p.name));
    const pct = h("span", "pct");
    if (goal) {
      pct.textContent = goal.pct.toFixed(1) + "%" + (goal.pct >= 100 ? " 🎉" : "");
      if (goal.pct >= 100) pct.classList.add("done");
    } else {
      pct.textContent = (p.goal && p.goal.noFx) ? T.goalNoRate : T.goalHidden;
      pct.classList.add("hidden");
    }
    top.appendChild(pct);
    const bar = h("div", "goal-bar" + (goal ? "" : " priv"));
    if (goal) {
      const fill = h("span");
      fill.style.width = Math.max(0, Math.min(100, goal.pct)) + "%";
      fill.style.background = colorOf(p);
      bar.appendChild(fill);
    }
    row.append(top, bar);
    if (goal && goal.value != null) row.appendChild(txt("div", "goal-meta", goalMoney(goal.value)));
    list.appendChild(row);
    return row;
  });
  collapseList(painted, list);
  // el cambio aplicado es de la liga (las carteras van en la divisa del
  // extracto y el objetivo en euros): se enseña aunque todos vayan en privado
  const rates = Object.entries(g.fx || {});
  const body = [];
  if (rates.length) body.push(txt("div", "kicker", rates.map(([cur, r]) => T.goalFx(cur, r.toFixed(4))).join(" · ")));
  body.push(list);
  const c = card({lbl: T.lbl.goal, ttl: T.goalTitle, end: count, body});
  c.id = "goal-card";
  return c;
}

// ---- insignias: récord de la liga + carrusel de logros --------------------
const BADGE_ICON = {champion_month: "🏆", week_streak: "🔥", milestone: "💎", months_2: "📈", months_3: "🗓️"};
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
// Cada insignia es un blob, como los agentes: forma y color según el logro.
function badgeBlob(b) {
  let shape = "circle", col = "--g8";
  if (b.type === "champion_month") { shape = "circle"; col = "--g5"; }
  else if (b.type === "week_streak") { shape = "diamond"; col = "--g6"; }
  else if (b.type === "milestone") {
    if (b.tier >= 25) { shape = "tri"; col = "--g3"; }
    else if (b.tier >= 10) { shape = "diamond"; col = "--g1"; }
    else { shape = "tri"; col = "--g4"; }
  }
  else if (b.type === "months_2") { shape = "circle"; col = "--g2"; }
  else if (b.type === "months_3") { shape = "diamond"; col = "--g7"; }
  return blobSVG(css(col), shape);
}
const BADGE_DOTS_MAX = 10;
function badgeNav(rail, cards, nav) {
  nav.innerHTML = "";
  nav.hidden = true;
  if (cards.length < 2) return;
  const showNav = () => { nav.hidden = !(rail.scrollWidth > rail.clientWidth + 2); };
  const dots = cards.length <= BADGE_DOTS_MAX ? cards.map((el, i) => {
    const dot = h("button");
    dot.type = "button";
    dot.setAttribute("aria-label", T.badgeGoTo(i + 1, cards.length));
    dot.addEventListener("click", () => {
      const left = el.getBoundingClientRect().left - rail.getBoundingClientRect().left + rail.scrollLeft - 14;
      rail.scrollTo({left: Math.max(0, left), behavior: "smooth"});
    });
    nav.appendChild(dot);
    return dot;
  }) : null;
  const count = dots ? null : nav.appendChild(h("span", "count"));
  let at = -1, tick = 0;
  const sync = () => {
    tick = 0;
    const base = rail.getBoundingClientRect().left + 14;
    let best = 0, dist = Infinity;
    cards.forEach((el, i) => {
      const d = Math.abs(el.getBoundingClientRect().left - base);
      if (d < dist) { dist = d; best = i; }
    });
    if (best === at) return;
    at = best;
    if (dots) dots.forEach((d, i) => { d.classList.toggle("on", i === at); d.setAttribute("aria-current", i === at ? "true" : "false"); });
    else count.textContent = (at + 1) + " / " + cards.length;
  };
  rail.addEventListener("scroll", () => { if (!tick) tick = requestAnimationFrame(sync); }, {passive: true});
  window.addEventListener("resize", showNav);
  sync();
  showNav();
}
function badgesCard() {
  const data = DATA.badges || {};
  const awards = (data.provisional || []).concat(data.awards || []);
  const record = data.record || null;
  if (!awards.length && !record) return null;
  const body = [txt("div", "kicker", T.badgesSub), h("div")];
  body[1].style.height = "10px";
  if (record) {
    const rc = h("div", "record");
    const g = h("div", "grow");
    g.appendChild(txt("div", "kicker", bare(T.recordTitle) + " · " + fmtDate(record.date)));
    const big = h("div", "big num");
    big.append(document.createTextNode(fmtPct(record.pct)), txt("span", "rtk", record.ticker));
    g.appendChild(big);
    const holders = (record.holders || []).map(x => x.name);
    if (holders.length) g.appendChild(txt("div", "kicker", T.recordHeld(holders.join(", "))));
    const prev = (record.history || []).slice(-1)[0];
    if (prev) g.appendChild(txt("div", "kicker", T.recordPrev(fmtPct(prev.pct), prev.ticker, fmtDate(prev.date))));
    rc.append(h("span", "av lg", blobSVG(css("--g8"), "tri")), g);
    body.push(rc);
  }
  if (awards.length) {
    const rail = h("div", "badge-rail");
    rail.tabIndex = 0;
    rail.setAttribute("role", "list");
    rail.setAttribute("aria-label", T.badgesRailAria);
    const cards = awards.map(b => {
      const el = h("div", "badge" + (b.provisional ? " prov" : ""));
      el.setAttribute("role", "listitem");
      const box = h("div", "btext");
      box.appendChild(txt("div", "btitle", badgeTitle(b)));
      const who = h("div", "bwho");
      const key = h("span", "key"); key.style.background = slotColor(b.slot);
      who.append(key, document.createTextNode(b.name || ""));
      box.appendChild(who);
      let meta = "";
      if (b.type === "champion_month" && b.pct != null) meta = T.badgeChampMeta(fmtPct(b.pct));
      else if (b.date) meta = T.badgeOn(fmtDate(b.date));
      box.appendChild(txt("div", "bmeta", meta));
      if (b.provisional) box.appendChild(txt("div", "ptag", "● " + T.badgeLive));
      el.append(h("span", "bico", badgeBlob(b)), box);
      if (b.player && PLAYERS[b.player]) { el.classList.add("clk"); el.dataset.player = b.player; }
      rail.appendChild(el);
      return el;
    });
    const nav = h("div", "badge-nav");
    body.push(rail, nav);
    AFTER.push(() => badgeNav(rail, cards, nav));
  } else {
    body.push(txt("div", "kicker", T.badgesEmpty));
  }
  const c = card({lbl: T.lbl.badges, ttl: T.badgesTitle, body});
  c.id = "badges-card";
  return c;
}

// ---- extractos subidos que no se pueden descifrar -------------------------
function pendingCard() {
  if (!DATA.pending || !DATA.pending.length) return null;
  const c = card({lbl: T.lbl.pending, ttl: T.pendingTitle, cls: "warn",
                  body: [txt("p", null, T.pendingText(DATA.pending.map(p => p.name).join(", ")))]});
  c.id = "pending-card";
  return c;
}

// ==== el hilo ==============================================================
// Cada intercambio es una pregunta de las de siempre y la respuesta de su
// agente. Si un agente no tiene nada que enseñar, el intercambio no sale.
const CHIPS = [
  ["standings", "warren", () => T.lbl.standings], ["today", "warren", () => T.lbl.session],
  ["month", "warren", () => T.lbl.month], ["ext", "scout", () => T.lbl.ext],
  ["trades", "scout", () => T.lbl.trades], ["news", "scout", () => T.lbl.news],
  ["portfolio", "scout", () => T.lbl.portfolio], ["goal", "warren", () => T.lbl.goal],
  ["badges", "warren", () => T.lbl.badges],
];
function render() {
  clearInterval(insightTimer); insightTimer = null;
  CHARTS = []; AFTER = [];
  TICKER_COLOR = {}; tickerNext = 0;
  const th = $("thread");
  const asks = $("asks") || h("div");
  asks.id = "asks";
  th.innerHTML = "";

  const intro = h("div", "intro");
  intro.append(groupAv("xl"), txt("h1", null, T.appTitle), txt("p", null, T.introSub));
  th.append(intro, txt("div", "day", T.today),
            sysLine(T.msgsFrom, sysTag("warren"), T.and, sysTag("scout")));

  const m = DATA.monthly || {};
  const dw = DATA.dailyWinners || {};
  const leader = ranked[0];
  const best = bestOfDay();
  // «¿Cómo va octubre?»: en la pregunta basta el nombre del mes
  const nowM = dw.month || (m.current && m.current.month);
  const nowMonth = nowM ? (MONTHS[LANG] || MONTHS.en)[nowM - 1] : "";
  const exs = [
    exchange("pending", "warren", null, [bubble({say: T.chatPending, cards: [pendingCard()]})]),
    exchange("standings", "warren", T.qStandings, [
      bubble({say: leader ? T.chatStandings(leader.name, fmtPct(lastOf(leader).cum)) : T.noPlayersDot,
              cards: [standingsCard()],
              acts: [leader && pill(T.openName(leader.name), () => openPlayer(leader.id), true),
                     pill(T.howCalculated, openLeaderHelp)]}),
      bubble({say: T.chatInsights, cards: [insightsCard()]}),
    ], leader && lastOf(leader).cum > 0 ? "🔥" : null),
    exchange("today", "warren", T.qToday, [
      bubble({say: best ? T.chatDay(best.name, fmtPct(lastOf(best).day)) : null, cards: [bestCard(best)],
              acts: [best && pill(T.seeSession, () => openDayDetail(best.id, lastOf(best).date), true)]}),
      bubble({say: T.chatDaily, cards: [dailyCard()]}),
    ], best && lastOf(best).day >= 2 ? "🚀" : null),
    exchange("month", "warren", nowMonth ? T.qMonth(nowMonth) : null, [
      bubble({say: m.current ? T.chatMonth(m.current.name, fmtPct(m.current.value),
                                           monthLabel(m.current.month, m.current.month_year)) : null,
              cards: [monthCurCard(m.current)],
              acts: [m.current && pill(T.treatBtn, () => openTreatHelp(m.current), true)]}),
      bubble({say: m.previous ? T.chatMonthPrev(m.previous.name, fmtPct(m.previous.value),
                                                monthLabel(m.previous.month, m.previous.month_year)) : null,
              cards: [monthPrevCard(m.previous)],
              acts: [m.previous && pill(T.monthSeeMore, () => openMonthDetail(m.previous), true)]}),
      bubble({say: T.chatMonthlyDetail, cards: [monthlyDetailCard()]}),
    ]),
    exchange("ext", "scout", T.qExt, [bubble({say: T.chatExt, cards: [extCard()],
      tool: extRows().length ? toolLine("Tape", T.extHoldings(extRows().length) + " · " +
                                        T.extAt(fmtClock(DATA.market.asOf))) : null})]),
    exchange("trades", "scout", T.qTrades, [bubble({say: T.chatOps, tool: opsTool(), cards: [opsCard()]})]),
    exchange("news", "scout", T.qNews, [bubble({say: T.chatNews, tool: newsTool(), cards: [newsCard()]})]),
    exchange("portfolio", "scout", T.qPortfolios, [
      bubble({say: T.chatAlloc, cards: [allocCard()]}),
      bubble({say: T.chatWallets, cards: [walletsCard()]}),
    ]),
    exchange("goal", "warren", T.qGoal, [bubble({say: T.chatGoal, cards: [goalCard()]})]),
    exchange("badges", "warren", T.qBadges, [bubble({say: T.chatBadges, cards: [badgesCard()]})]),
  ];
  exs.forEach(ex => ex && th.appendChild(ex));

  // la rutina que alimenta el hilo: el ranking a la apertura y al cierre
  const clock = h("span", "ico", "⏱");
  clock.setAttribute("aria-hidden", "true");
  th.appendChild(sysLine(T.routine, clock, txt("b", null, T.routineName),
                         "· " + T.updated(fmtStamp(DATA.updated))));
  th.appendChild(h("p", "foot", T.footer));
  th.appendChild(asks);

  paintCharts();
  AFTER.forEach(fn => fn());
  renderChrome();
  applyFilter();
}
function renderLoading() {
  const box = $("loading");
  if (!box) return;
  const stack = box.querySelector(".stack");
  if (stack && !stack.childNodes.length) stack.replaceWith(groupAv("xl"));
  $("loading-text").textContent = T.loading;
}
function renderError() {
  const th = $("thread");
  th.innerHTML = "";
  const ex = exchange("error", "warren", null, [bubble({say: T.loadError,
    acts: [pill(T.retry, () => { th.innerHTML = ""; th.appendChild(loadingEl()); load(); }, true)]})]);
  th.append(h("div", "loading"), ex);
  th.firstChild.appendChild(groupAv("xl"));
}
function loadingEl() {
  const box = h("div", "loading");
  box.id = "loading";
  const typing = h("span", "typing", '<span class="dots"><i></i><i></i><i></i></span>');
  typing.appendChild(txt("span", null, T.loading));
  box.append(groupAv("xl"), typing);
  return box;
}

// ==== filtro por agente, carril, píldora y sugerencias =====================
function applyFilter() {
  document.querySelectorAll("#thread > .ex[data-agent]").forEach(ex => {
    ex.hidden = FILTER !== "all" && ex.dataset.agent !== FILTER;
  });
  document.querySelectorAll("#chips .chip").forEach(c => {
    c.hidden = FILTER !== "all" && c.dataset.agent !== FILTER;
  });
}
function setFilter(f) {
  FILTER = f;
  renderChrome();
  applyFilter();
  window.scrollTo({top: 0});
  $("scroll").scrollTop = 0;
}
function scrollToEx(key) {
  const ex = $("ex-" + key);
  if (!ex) return;
  if (ex.hidden) setFilter("all");
  ex.scrollIntoView({behavior: "smooth", block: "start"});
}
function renderChrome() {
  // carril (escritorio): la liga entera, los dos agentes y los jugadores
  const rail = $("rail-list");
  rail.innerHTML = "";
  const railIt = (node, label, current, onClick) => {
    const b = h("button", "rail-it");
    b.type = "button"; b.title = label; b.setAttribute("aria-label", label);
    if (current != null) b.setAttribute("aria-current", current ? "true" : "false");
    b.appendChild(node);
    b.addEventListener("click", onClick);
    rail.appendChild(b);
  };
  railIt(groupAv(), T.appTitle + " · " + T.everyone, FILTER === "all", () => setFilter("all"));
  ["warren", "scout"].forEach(id => railIt(agentAv(id), AGENTS[id].name + " · " + AGENTS[id].about,
                                           FILTER === id, () => setFilter(id)));
  if (DATA && ranked.length) {
    rail.appendChild(h("hr"));
    ranked.forEach(p => railIt(playerAv(p), p.name, null, () => openPlayer(p.id)));
  }
  // píldora del agente (arriba)
  const av = $("who-av");
  av.innerHTML = "";
  if (FILTER === "all") {
    av.appendChild(groupAv("sm"));
    $("who-name").textContent = T.appTitle;
    $("who-sub").textContent = DATA ? "· " + T.updated(fmtStamp(DATA.updated)) : "";
  } else {
    av.appendChild(agentAv(FILTER));
    $("who-name").textContent = AGENTS[FILTER].name;
    $("who-sub").textContent = "· " + AGENTS[FILTER].about;
  }
  $("ask").placeholder = T.msgPlaceholder(AGENTS[FILTER === "scout" ? "scout" : "warren"].name);
  // sugerencias encima de la barra: saltan a cada respuesta
  const chips = $("chips");
  chips.innerHTML = "";
  CHIPS.forEach(([key, agent, label]) => {
    if (!$("ex-" + key)) return;
    const c = h("button", "chip");
    c.type = "button"; c.dataset.agent = agent;
    c.append(agentAv(agent, "sm"), document.createTextNode(label()));
    c.addEventListener("click", () => scrollToEx(key));
    chips.appendChild(c);
  });
}

// ==== la barra de mensaje: preguntar por un jugador, un ticker o un tema ===
// No hay modelo detrás: Warren y Scout contestan con los datos de la API. Un
// jugador abre su ficha, un ticker la suya y un tema te lleva a su respuesta.
const TOPICS = {
  standings: ["standing", "ranking", "rank", "leader", "leading", "winning", "winner", "clasificacion",
              "classement", "lider", "ganando", "gana", "general", "canada", "順位", "首位"],
  today: ["today", "session", "yesterday", "hoy", "ayer", "sesion", "jornada", "seance", "aujourd", "今日", "セッション"],
  month: ["month", "monthly", "mes", "mois", "vancouver", "restaurant", "lunch", "comida", "invita", "今月"],
  ext: ["premarket", "pre-market", "afterhours", "after-hours", "extended", "horario", "hors", "時間外"],
  trades: ["trade", "trading", "buy", "sell", "bought", "sold", "operacion", "compra", "venta", "achat",
           "vente", "operation", "売買", "取引"],
  news: ["news", "headline", "noticia", "actualite", "nouvelle", "ニュース"],
  portfolio: ["portfolio", "allocation", "holding", "wallet", "cartera", "portefeuille", "ポートフォリオ"],
  goal: ["goal", "target", "objetivo", "objectif", "meta", "目標"],
  badges: ["badge", "record", "trophy", "insignia", "trofeo", "palmares", "バッジ"],
};
const TOPIC_AGENT = {standings: "warren", today: "warren", month: "warren", goal: "warren", badges: "warren",
                     ext: "scout", trades: "scout", news: "scout", portfolio: "scout"};
function understand(q) {
  const n = norm(q);
  const words = n.split(/[^\p{L}\p{N}.\-]+/u).filter(Boolean);
  const player = DATA.players.find(p => words.includes(norm(p.name)) || words.includes(norm(p.id)));
  if (player) return {kind: "player", agent: "warren", player};
  const tk = (DATA.tickers || []).find(t => words.includes(norm(t.ticker)) ||
    words.some(w => w.length >= 4 && norm(t.name).split(/\s+/).includes(w)));
  if (tk) return {kind: "ticker", agent: "scout", ticker: tk};
  for (const key in TOPICS) {
    // las claves pasan por la misma normalización (バッジ pierde el dakuten igual)
    if (TOPICS[key].some(k => n.includes(norm(k))) && $("ex-" + key))
      return {kind: "topic", agent: TOPIC_AGENT[key], key};
  }
  return {kind: "help", agent: FILTER === "scout" ? "scout" : "warren"};
}
function answerFor(a, dismiss) {
  if (a.kind === "player") {
    const p = a.player, last = lastOf(p);
    return bubble({say: T.askPlayer(p.name, T.rankOrd(ranked.indexOf(p) + 1), fmtPct(last.cum), fmtPct(last.day)),
                   acts: [pill(T.openProfile, () => openPlayer(p.id), true), pill(T.dismiss, dismiss)]});
  }
  if (a.kind === "ticker") {
    const t = a.ticker;
    return bubble({say: T.askTicker(t.ticker, t.name, fmtW(t.w), T.playersCount(t.holders.length)),
                   acts: [pill(T.openTicker(t.ticker), () => openTicker(t.ticker), true), pill(T.dismiss, dismiss)]});
  }
  if (a.kind === "topic")
    return bubble({say: T.askTopic, acts: [pill(T.showMe, () => scrollToEx(a.key), true), pill(T.dismiss, dismiss)]});
  const tickers = (DATA.tickers || []).slice(0, 4).map(t => t.ticker).join(", ");
  return bubble({say: T.askHelp(DATA.players.map(p => p.name).join(", "), tickers),
                 acts: [pill(T.dismiss, dismiss)]});
}
function toBottom() {
  const sc = $("scroll");
  sc.scrollTo({top: sc.scrollHeight, behavior: "smooth"});
  window.scrollTo({top: document.documentElement.scrollHeight, behavior: "smooth"});
}
function ask(q) {
  q = q.trim();
  if (!q || !DATA) return;
  const a = understand(q);
  const ex = h("div", "ex asked");
  ex.dataset.agent = a.agent;
  const grp = h("div", "grp");
  const who = h("div", "who");
  who.append(agentAv(a.agent, "sm"), txt("b", null, AGENTS[a.agent].name), document.createTextNode(AGENTS[a.agent].role));
  const typing = h("span", "typing", '<span class="dots"><i></i><i></i><i></i></span>');
  typing.appendChild(txt("span", null, T.typing(AGENTS[a.agent].name)));
  grp.append(who, typing);
  ex.append(meBubble(q), grp);
  $("asks").appendChild(ex);
  toBottom();
  setTimeout(() => {
    typing.replaceWith(answerFor(a, () => ex.remove()));
    toBottom();
  }, 650);
}

// ==== fichas de detalle (hoja inferior en el móvil) ========================
const modal = $("modal"), modalBody = $("modal-body"), sheet = $("sheet");
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
  sheet.classList.add("closing");
  clearTimeout(closingTimer);
  closingTimer = setTimeout(hideModal, 220);
}
function showModal(node) {
  clearTimeout(closingTimer);
  sheet.classList.remove("closing");
  sheet.style.transform = ""; sheet.style.transition = ""; sheet.style.opacity = "";
  modalBody.innerHTML = "";
  const close = txt("button", "mclose", "✕");
  close.type = "button";
  close.setAttribute("aria-label", T.close);
  close.addEventListener("click", closeModal);
  node.appendChild(close);
  modalBody.appendChild(node);
  modal.classList.add("open");
  modal.setAttribute("aria-hidden", "false");
  document.body.style.overflow = "hidden";
  sheet.scrollTop = 0;
}
function sectionEl(title, node) {
  const s = h("div", "msec");
  s.appendChild(txt("div", "h", title));
  s.appendChild(node);
  return s;
}
function tileEl(k, v, cls) {
  const t = h("div", "tile");
  t.append(txt("div", "k", k), txt("div", "v" + (cls ? " " + cls : ""), v));
  return t;
}
function mhead(icon, t1, badge, t2) {
  const head = h("div", "mhead");
  head.appendChild(icon);
  const title = h("div", "mtitle");
  const a = h("div", "t1");
  a.appendChild(document.createTextNode(t1));
  if (badge) a.appendChild(badge);
  title.append(a, txt("div", "t2", t2));
  head.appendChild(title);
  return head;
}
const pctBadge = v => txt("span", "mbadge" + (v >= 0 ? "" : " neg"), fmtPct(v));

// ---- cómo se calcula la rentabilidad --------------------------------------
function openLeaderHelp() {
  const c = T.calc;
  const root = h("div");
  const head = h("div", "mhead");
  const title = h("div", "mtitle");
  title.append(txt("div", "t1", c.title), txt("div", "t2", c.subtitle));
  head.appendChild(title);
  root.appendChild(head);
  c.qa.forEach(([q, a]) => root.appendChild(sectionEl(q, h("div", "mtext", a))));
  const fsec = h("div", "msec");
  fsec.appendChild(txt("div", "h", c.formulaLabel));
  [[c.dailyLbl, c.dailyFormula], [c.cumLbl, c.cumFormula]].forEach(([l, f]) => {
    const row = h("div", "formula");
    row.append(txt("span", "lbl", l), document.createTextNode(f));
    fsec.appendChild(row);
  });
  root.append(fsec, txt("div", "mnote", c.note));
  showModal(root);
}

// ---- la escala del restaurante (quién invita y dónde) ---------------------
function openTreatHelp(info) {
  const scale = DATA.treatScale || [];
  const root = h("div");
  const head = h("div", "mhead");
  const title = h("div", "mtitle");
  title.append(txt("div", "t1", T.treatTitle), txt("div", "t2", T.treatSubtitle));
  head.appendChild(title);
  root.append(head, txt("div", "mtext", T.treatIntro));
  const table = document.createElement("table");
  table.className = "scale";
  const cols = table.insertRow();
  T.treatCols.forEach((x, i) => cols.appendChild(txt("th", i === 1 ? "where" : null, x)));
  scale.forEach((step, i) => {
    const tr = table.insertRow();
    if (info && info.treat === i) tr.className = "on";
    tr.appendChild(txt("td", "rng", treatRange(i)));
    const where = h("td", "where");
    where.append(txt("span", "eur", step.euros), document.createTextNode(T.treatTiers[i]),
                 txt("span", "ex", (step.places || []).join(" · ")));
    tr.appendChild(where);
    tr.appendChild(txt("td", "price", i === scale.length - 1 ? T.treatPlus(treatMoney(step.price)) : treatMoney(step.price)));
  });
  root.append(sectionEl(T.treatScaleLbl, table), txt("div", "mnote", T.treatNote));
  showModal(root);
}

// ---- detalle de ticker ----------------------------------------------------
// Reparto de opiniones de los analistas: rampa verde → gris → rojo.
const REC_BUCKETS = [
  ["strongBuy", T.recBuckets[0], "#15a34a"], ["buy", T.recBuckets[1], "#22c55e"],
  ["hold", T.recBuckets[2], "#9aa0ac"], ["sell", T.recBuckets[3], "#f59e0b"],
  ["strongSell", T.recBuckets[4], "#ef4444"],
];
// el consenso llega en español desde el backend: se traduce por su bucket
const REC_LABEL_MAP = {"Compra fuerte": 0, "Comprar": 1, "Mantener": 2, "Vender": 3, "Venta fuerte": 4};
const recLabel = l => { const i = REC_LABEL_MAP[l]; return i == null ? l : T.recBuckets[i]; };
function analystSectionEl(a) {
  const cons = h("div", "consensus");
  if (a.label) cons.appendChild(txt("span", "cbadge " + (a.tone || "neutral"), recLabel(a.label)));
  const meta = [];
  if (a.count) meta.push(T.analysts(a.count));
  if (a.mean != null) meta.push(T.avg(a.mean.toFixed(1)));
  if (meta.length) cons.appendChild(txt("span", "cmeta", meta.join(" · ")));
  const wrap = sectionEl(T.analystRec + (a.asOf ? " · " + fmtDate(a.asOf) : ""), cons);
  if (a.dist) {
    const total = REC_BUCKETS.reduce((s, [k]) => s + (a.dist[k] || 0), 0);
    if (total > 0) {
      const bar = h("div", "distbar"), leg = h("div", "distlegend");
      REC_BUCKETS.forEach(([k, lbl, col]) => {
        const n = a.dist[k] || 0; if (!n) return;
        const seg = h("span"); seg.style.background = col; seg.style.width = (n / total * 100) + "%";
        seg.title = lbl + ": " + n; bar.appendChild(seg);
        const item = h("span"); const sw = h("span", "sw"); sw.style.background = col;
        item.append(sw, document.createTextNode(lbl + " " + n)); leg.appendChild(item);
      });
      wrap.append(bar, leg);
    }
  }
  if (a.target != null) {
    const t = h("div", "target");
    t.appendChild(document.createTextNode(T.priceTarget(money(a.target)) + " "));
    if (a.upside != null) t.appendChild(txt("span", a.upside >= 0 ? "pos" : "neg", "(" + fmtPct(a.upside) + ") "));
    if (a.targetLow != null && a.targetHigh != null)
      t.appendChild(txt("span", "rng", T.rangeLabel(money(a.targetLow), money(a.targetHigh))));
    wrap.appendChild(t);
  }
  return wrap;
}
// Comprar / Vender abren el detalle del valor en la app de Revolut.
function revolutRow(sym) {
  const href = "https://revolut.com/app/trading/stocks/" + encodeURIComponent(sym);
  const box = h("div", "revolut");
  [[T.buy, "buy", "▲"], [T.sell, "sell", "▼"]].forEach(([label, cls, ico]) => {
    const a = document.createElement("a");
    a.href = href;
    a.className = "pill rev-btn " + cls + (cls === "buy" ? " fill" : "");
    a.append(txt("span", "ic", ico), document.createTextNode(label));
    box.appendChild(a);
  });
  return box;
}
function peersSectionEl(peers) {
  const chips = h("div", "chips-w");
  peers.forEach(p => {
    const known = !!TICKERS[p.ticker];
    let chip;
    if (known) { chip = h("div", "chip-tk clk"); chip.dataset.ticker = p.ticker; }
    else {
      chip = externalLink("https://revolut.com/app/trading/stocks/" + encodeURIComponent(p.ticker));
      chip.className = "chip-tk"; chip.style.textDecoration = "none";
    }
    chip.append(tickerLogoEl(p, 24), document.createTextNode(p.ticker));
    if (!known) chip.appendChild(txt("span", "w", "↗"));
    chips.appendChild(chip);
  });
  return sectionEl(T.relatedTickers, chips);
}
const playerIdByName = name => { const p = DATA.players.find(x => x.name === name); return p ? p.id : null; };
function openTicker(sym) {
  const t = TICKERS[sym];
  if (!t) return;
  const root = h("div");
  root.appendChild(mhead(tickerLogoEl(t, 44), t.ticker, t.ret != null ? pctBadge(t.ret) : null, t.name));
  const tiles = h("div", "tiles");
  tiles.append(tileEl(T.weightInLeague, fmtW(t.w)), tileEl(T.heldBy, T.playersCount(t.holders.length)),
               tileEl(T.variation, t.ret == null ? "—" : fmtPct(t.ret), t.ret == null ? "" : (t.ret >= 0 ? "pos" : "neg")));
  const ex = t.ext;
  if (ex && ex.session && ex.pct != null)
    tiles.appendChild(tileEl(extLabel(ex.session) + " · " + extMoney(ex.price, ex.currency),
                             fmtPct(ex.pct), ex.pct >= 0 ? "pos" : "neg"));
  root.appendChild(tiles);
  const revSec = sectionEl(T.tradeOnRevolut, revolutRow(t.ticker));
  revSec.appendChild(txt("div", "rev-note", T.revNote(t.ticker)));
  root.appendChild(revSec);
  if (t.analyst) root.appendChild(analystSectionEl(t.analyst));
  if (t.prices && t.prices.length >= 2) {
    const spark = h("div", "mspark", sparkSVG(t.prices.map(p => p.close), css(t.ret >= 0 ? "--up" : "--down"), "tk"));
    root.appendChild(sectionEl(T.priceRange(fmtDate(t.prices[0].date), fmtDate(t.prices[t.prices.length - 1].date)), spark));
  }
  if (t.holders.length) {
    const list = h("div");
    t.holders.forEach(hd => {
      const row = h("div", "holder-row clk");
      row.dataset.player = playerIdByName(hd.name) || "";
      const nm = h("span", "nm");
      nm.append(avEl(slotColor(hd.slot), "circle", "sm"), document.createTextNode(hd.name));
      row.append(nm, txt("span", "w", T.ofPortfolio(fmtW(hd.w))));
      list.appendChild(row);
    });
    root.appendChild(sectionEl(T.whoHasIt, list));
  }
  if (t.peers && t.peers.length) root.appendChild(peersSectionEl(t.peers));
  root.appendChild(newsSectionEl(T.news, t.news || [], t.ticker));
  root.appendChild(h("div", "mnote", T.tickerNote));
  showModal(root);
}

// ---- detalle de jugador ---------------------------------------------------
function nextStepEl(s) {
  const box = h("div", "nextstep");
  if (TICKERS[s.ticker]) { box.classList.add("clk"); box.dataset.ticker = s.ticker; }
  const isBuy = s.action !== "trim";
  const top = h("div", "top");
  top.append(tickerLogoEl(s, 26), txt("span", "act" + (isBuy ? "" : " neg"), isBuy ? T.nextBuy : T.nextTrim),
             txt("span", "ttl", T.nextTitle(s.ticker, isBuy)));
  box.appendChild(top);
  const bits = [];
  if (s.label) bits.push(T.consensusBit(recLabel(s.label)));
  if (s.count) bits.push(T.analysts(s.count));
  if (s.upside != null) bits.push(T.targetBit(fmtPct(s.upside)));
  bits.push(T.ofPortfolio(fmtW(s.w)));
  box.append(txt("div", "body", bits.join(" · ")), txt("div", "dis", T.nextDisclaimer));
  return box;
}
function openPlayer(pid) {
  const p = PLAYERS[pid];
  if (!p) return;
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
  const root = h("div");
  root.appendChild(mhead(playerAv(p, "lg"), p.name,
    rankIdx >= 0 ? txt("span", "mbadge rank", MEDALS[rankIdx] || "#" + (rankIdx + 1)) : null,
    T.since(p.since ? fmtDate(p.since) : (days[0] || {}).date || "")));
  if (p.suggestion) root.appendChild(sectionEl(T.nextStep, nextStepEl(p.suggestion)));
  const tiles = h("div", "tiles");
  tiles.append(tileEl(T.cumPct, fmtPct(last.cum), last.cum >= 0 ? "pos" : "neg"),
               tileEl(T.bestDayTile, fmtPct(bestDay.day), "pos"),
               tileEl(T.worstDayTile, fmtPct(worstDay.day), worstDay.day < 0 ? "neg" : ""),
               tileEl(T.lastDayPct, fmtPct(last.day), last.day >= 0 ? "pos" : "neg"),
               tileEl(T.streakLabel(sign, streak), String(streak), sign > 0 ? "pos" : (sign < 0 ? "neg" : "")),
               tileEl(T.sessions, String(days.length)));
  root.appendChild(tiles);
  const mine = PLAYER_BADGES[pid] || [];
  if (mine.length) {
    const wrap = h("div", "mbadges");
    mine.forEach(b => {
      const chip = h("div", "mbadge-chip" + (b.provisional ? " prov" : ""));
      chip.append(h("span", "i", badgeBlob(b)), txt("span", "t", badgeTitle(b)));
      wrap.appendChild(chip);
    });
    root.appendChild(sectionEl(bare(T.badgesTitle), wrap));
  }
  if (days.length >= 2)
    root.appendChild(sectionEl(T.cumTitle, h("div", "mspark",
      sparkSVG(days.map(d => d.cum), css(last.cum >= 0 ? "--up" : "--down"), "pl", {baseline0: true}))));
  if (p.holdings && p.holdings.length) {
    const chips = h("div", "chips-w");
    p.holdings.forEach(hh => {
      const meta = TICKERS[hh.ticker] || {ticker: hh.ticker};
      const chip = h("div", "chip-tk" + (TICKERS[hh.ticker] ? " clk" : ""));
      if (TICKERS[hh.ticker]) chip.dataset.ticker = hh.ticker;
      chip.append(tickerLogoEl(meta, 24), document.createTextNode(hh.ticker), txt("span", "w", fmtW(hh.w)));
      chips.appendChild(chip);
    });
    root.appendChild(sectionEl(T.portfolioCount(p.holdings.length), chips));
  }
  const recent = days.slice(-6).reverse();
  if (recent.length) {
    const list = h("div");
    recent.forEach(d => {
      const row = h("div", "mini-row clk");
      row.dataset.dayDate = d.date; row.dataset.dayPlayer = pid;
      row.append(txt("span", "dt", fmtDate(d.date)), txt("span", "v " + (d.day >= 0 ? "pos" : "neg"), fmtPct(d.day)));
      list.appendChild(row);
    });
    root.appendChild(sectionEl(T.recentSessions, list));
  }
  if (p.holdings && p.holdings.length) {
    // los titulares de toda su cartera, no solo de su primera posición
    const syms = p.holdings.map(hh => hh.ticker);
    root.appendChild(newsSectionEl(T.portfolioNews, newsFor(syms, 6), syms[0]));
  }
  showModal(root);
}

// ---- detalle de una sesión: rentabilidad por valor y el resto -------------
function openDayDetail(pid, iso) {
  const perPlayer = DAY_INDEX[iso] || {};
  let subject = PLAYERS[pid];
  if (!subject || !perPlayer[pid]) {
    let bestId = null, bestVal = -Infinity;
    Object.keys(perPlayer).forEach(id => { if (perPlayer[id].day > bestVal) { bestVal = perPlayer[id].day; bestId = id; } });
    subject = PLAYERS[bestId]; pid = bestId;
  }
  if (!subject) return;
  const sd = perPlayer[pid] || {day: 0, bd: []};
  const root = h("div");
  root.appendChild(mhead(playerAv(subject, "lg"), fmtDate(iso), pctBadge(sd.day), subject.name));
  const bd = sd.bd || [];
  if (bd.length) {
    const list = h("div");
    const rows = bd.map(x => {
      const row = h("div", "holder-row");
      if (x.ticker && TICKERS[x.ticker]) { row.classList.add("clk"); row.dataset.ticker = x.ticker; }
      const nm = h("span", "nm");
      if (x.ticker) nm.append(tickerLogoEl({ticker: x.ticker}, 26), document.createTextNode(x.ticker));
      else nm.appendChild(document.createTextNode("💵 " + T.dayCash));
      row.append(nm, txt("span", "w " + (x.pct >= 0 ? "pos" : "neg"), fmtPct(x.pct)));
      list.appendChild(row);
      return row;
    });
    collapseList(rows, list);
    root.appendChild(sectionEl(T.dayByAsset, list));
  } else {
    root.appendChild(sectionEl(T.dayByAsset, txt("div", "mnote", T.dayNoBreakdown)));
  }
  const others = Object.keys(perPlayer).filter(id => id !== pid && PLAYERS[id])
    .map(id => ({p: PLAYERS[id], d: perPlayer[id]})).sort((a, b) => b.d.day - a.d.day);
  if (others.length) {
    const list = h("div");
    others.forEach(({p, d}) => {
      const row = h("div", "holder-row clk"); row.dataset.player = p.id;
      const nm = h("span", "nm"); nm.append(playerAv(p, "sm"), document.createTextNode(p.name));
      row.append(nm, txt("span", "w " + (d.day >= 0 ? "pos" : "neg"), fmtPct(d.day)));
      list.appendChild(row);
    });
    root.appendChild(sectionEl(T.dayOthers, list));
  }
  showModal(root);
}

// ---- segundo nivel del mes pasado: su gráfica y su clasificación ----------
function openMonthDetail(info) {
  if (!info) return;
  const ml = monthLabel(info.month, info.month_year);
  const root = h("div");
  root.appendChild(mhead(avEl(slotColor(info.slot), "circle", "lg"), ml, pctBadge(info.value), "🏆 " + info.name));
  // la gráfica se pinta con la hoja ya abierta: mide el ancho real
  const chart = h("div", "mchart");
  root.appendChild(sectionEl(T.monthEvolution, chart));
  const series = info.series || [];
  if (series.length) {
    const list = h("div");
    const rows = series.map((s, i) => {
      const row = h("div", "holder-row clk"); row.dataset.player = s.id;
      const nm = h("span", "nm");
      nm.append(avEl(slotColor(s.slot), "circle", "sm"), document.createTextNode((i === 0 ? "🏆 " : "") + s.name));
      row.append(nm, txt("span", "w " + (s.value >= 0 ? "pos" : "neg"), fmtPct(s.value)));
      list.appendChild(row);
      return row;
    });
    collapseList(rows, list);
    root.appendChild(sectionEl(T.monthRanking, list));
  }
  showModal(root);
  monthChart(chart, info);
}

// ==== menús: idioma y agente ===============================================
function menu(btn, box, build) {
  const close = () => {
    box.hidden = true;
    btn.setAttribute("aria-expanded", "false");
    document.removeEventListener("click", outside, true);
    document.removeEventListener("keydown", onKey);
  };
  function outside(ev) { if (!box.contains(ev.target) && !btn.contains(ev.target)) close(); }
  function onKey(ev) { if (ev.key === "Escape") { close(); btn.focus(); } }
  btn.addEventListener("click", () => {
    if (!box.hidden) { close(); return; }
    box.innerHTML = "";
    build(close);
    box.hidden = false;
    btn.setAttribute("aria-expanded", "true");
    document.addEventListener("click", outside, true);
    document.addEventListener("keydown", onKey);
  });
}
function menuItem(box, {icon, label, sub, checked, onClick, close}) {
  const b = h("button");
  b.type = "button";
  b.setAttribute("role", checked == null ? "menuitem" : "menuitemradio");
  if (checked != null) b.setAttribute("aria-checked", checked ? "true" : "false");
  if (icon) b.appendChild(icon);
  const l = h("span");
  l.appendChild(document.createTextNode(label));
  if (sub) l.appendChild(txt("span", "mi-sub", sub));
  b.appendChild(l);
  if (checked != null) b.appendChild(txt("span", "tick", "✓"));
  b.addEventListener("click", () => { close(); onClick(); });
  box.appendChild(b);
}
// Idioma: se guarda por dispositivo y se recarga para repintar todo.
menu($("lang-btn"), $("lang-menu"), close => LANGS.forEach(l => {
  menuItem($("lang-menu"), {label: l.label, checked: l.code === LANG, close, onClick: () => {
    if (l.code === LANG) return;
    try { localStorage.setItem("lang", l.code); } catch (e) {}
    location.reload();
  }});
  $("lang-menu").lastChild.lang = l.code;
}));
// Agente: la liga entera, Warren o Scout; y la ficha de cada jugador.
menu($("who"), $("who-menu"), close => {
  const box = $("who-menu");
  menuItem(box, {icon: groupAv("sm"), label: T.appTitle, sub: T.everyone, checked: FILTER === "all",
                 close, onClick: () => setFilter("all")});
  ["warren", "scout"].forEach(id => menuItem(box, {icon: agentAv(id, "sm"), label: AGENTS[id].name,
    sub: AGENTS[id].about, checked: FILTER === id, close, onClick: () => setFilter(id)}));
  if (DATA && ranked.length) {
    box.appendChild(h("hr"));
    box.appendChild(txt("div", "mi-h", T.playersLbl));
    ranked.forEach(p => menuItem(box, {icon: playerAv(p, "sm"), label: p.name, sub: fmtPct(lastOf(p).cum),
      close, onClick: () => openPlayer(p.id)}));
  }
});

// ==== carga de la API ======================================================
let lastLoad = 0, loadingNow = false;
async function load() {
  if (loadingNow) return;
  loadingNow = true;
  $("refresh").classList.add("spin");
  try {
    // no-cache: se revalida siempre (ETag) y llega el último recálculo
    const res = await fetch(API_URL, {cache: "no-cache"});
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    lastLoad = Date.now();
    if (!DATA || data.generatedAt !== DATA.generatedAt || data.updated !== DATA.updated) {
      const y = window.scrollY, sy = $("scroll").scrollTop;
      setData(data);
      render();
      window.scrollTo({top: y}); $("scroll").scrollTop = sy;
    }
  } catch (e) {
    console.warn("league api:", e);
    if (!DATA) renderError();
  } finally {
    loadingNow = false;
    $("refresh").classList.remove("spin");
  }
}

// ==== arranque ==============================================================
(() => {
  document.title = T.appTitle;
  $("app-title-meta").setAttribute("content", T.appTitle);
  if (LANG_META.manifest) $("manifest-link").setAttribute("href", LANG_META.manifest);
  $("lang-label").textContent = LANG_META.short;
  [["lang-btn", T.langAria], ["refresh", T.refresh], ["send", T.send], ["who", T.agentsAria],
   ["upload-mail", T.sendPositions], ["rail-mail", T.sendPositions], ["ask", T.msgPlaceholder(T.agentWarren)]]
    .forEach(([id, label]) => { $(id).setAttribute("aria-label", label); $(id).title = label; });
  $("rail").setAttribute("aria-label", T.agentsAria);
  sheet.setAttribute("aria-label", T.detailAria);
  // enviar posiciones: correo al buzón de la liga con fecha en el asunto
  const setMail = el => {
    const now = new Date();
    const p = n => String(n).padStart(2, "0");
    const subject = p(now.getDate()) + "/" + p(now.getMonth() + 1) + "/" + now.getFullYear() +
      " " + p(now.getHours()) + ":" + p(now.getMinutes());
    el.href = "mailto:" + MAIL_TO + "?subject=" + encodeURIComponent(subject) + "&body=" + encodeURIComponent(T.mailBody);
  };
  ["upload-mail", "rail-mail"].forEach(id => { const el = $(id); setMail(el); el.addEventListener("click", () => setMail(el)); });

  renderLoading();
  renderChrome();
  load();

  $("refresh").addEventListener("click", () => { DATA && (DATA.generatedAt = null); load(); });
  const input = $("ask"), send = $("send");
  input.addEventListener("input", () => { send.disabled = !input.value.trim(); });
  $("composer").addEventListener("submit", ev => {
    ev.preventDefault();
    ask(input.value);
    input.value = "";
    send.disabled = true;
  });
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && Date.now() - lastLoad > STALE_MS) load();
  });
  // al cambiar de tamaño se rehacen las gráficas (miden px reales); al
  // cambiar de tema, todo (los colores salen de los tokens)
  let raf;
  window.addEventListener("resize", () => {
    cancelAnimationFrame(raf);
    raf = requestAnimationFrame(paintCharts);
  });
  const mq = window.matchMedia("(prefers-color-scheme: dark)");
  if (mq.addEventListener) mq.addEventListener("change", () => { if (DATA) render(); });

  // apertura de fichas por delegación (gana el elemento más interno)
  document.addEventListener("click", ev => {
    if (ev.target.closest(".menu, a[href]")) return;
    const dd = ev.target.closest("[data-day-date]");
    const tk = ev.target.closest("[data-ticker]");
    const pl = ev.target.closest("[data-player]");
    const inner = [dd, tk, pl].filter(Boolean).sort((a, b) => a.contains(b) ? 1 : (b.contains(a) ? -1 : 0))[0];
    if (!inner) return;
    if (inner === dd && dd.dataset.dayDate) openDayDetail(dd.dataset.dayPlayer || "", dd.dataset.dayDate);
    else if (inner === tk && tk.dataset.ticker) openTicker(tk.dataset.ticker);
    else if (inner === pl && pl.dataset.player) openPlayer(pl.dataset.player);
  });
  modal.addEventListener("click", ev => { if (ev.target === modal) closeModal(); });
  document.addEventListener("keydown", ev => { if (ev.key === "Escape" && modal.classList.contains("open")) closeModal(); });
  sheet.querySelector(".grab").addEventListener("click", closeModal);

  // arrastrar la hoja hacia abajo para cerrarla (como una hoja nativa)
  let startY = 0, dy = 0, dragging = false;
  sheet.addEventListener("touchstart", e => {
    if (sheet.scrollTop > 0) { dragging = false; return; }
    startY = e.touches[0].clientY; dy = 0; dragging = true;
    sheet.style.transition = "none";
  }, {passive: true});
  sheet.addEventListener("touchmove", e => {
    if (!dragging) return;
    dy = e.touches[0].clientY - startY;
    if (dy <= 0 || sheet.scrollTop > 0) { sheet.style.transform = ""; sheet.style.opacity = ""; return; }
    if (e.cancelable) e.preventDefault();
    sheet.style.transform = "translateY(" + dy + "px)";
    sheet.style.opacity = String(Math.max(0.5, 1 - dy / 640));
  }, {passive: false});
  const end = () => {
    if (!dragging) return;
    dragging = false;
    sheet.style.transition = "";
    if (dy > 110) {
      sheet.style.transition = "transform .2s ease-in, opacity .2s ease-in";
      sheet.style.transform = "translateY(100%)"; sheet.style.opacity = "0";
      clearTimeout(closingTimer);
      closingTimer = setTimeout(hideModal, 200);
    } else { sheet.style.transform = ""; sheet.style.opacity = ""; }
  };
  sheet.addEventListener("touchend", end);
  sheet.addEventListener("touchcancel", end);
})();
