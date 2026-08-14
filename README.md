# 🏆 Trader — competición de rentabilidad con Revolut

Aplicación para trackear las órdenes de compra/venta de Revolut de varios
jugadores, calcular la rentabilidad diaria y acumulada de cada uno, y
publicar un ranking — todo en un repositorio público **sin exponer las
operaciones ni los importes de nadie** (los extractos se suben cifrados).

📊 **El ranking se publica en dos formatos**, actualizados automáticamente
cada día de mercado por una GitHub Action:

- **Web (clasificación y widgets)**: `docs/index.html`, servida con GitHub Pages en
  **https://fedegarlo.github.io/trader/** (ver [Ver en web](#ver-en-web)).
- **Markdown**: [`docs/ranking.md`](docs/ranking.md), legible directamente
  en GitHub.

## Ver en web

La página es estática y autocontenida. Abre con la **clasificación**: una tabla
tipo parrilla de F1 o tabla de liga (1º, 2º, 3º…, con el acumulado de cada
jugador y el % de la última jornada), seguida del **mejor del día**, del
**camino al objetivo** (ver [🎯 Camino al objetivo](#-camino-al-objetivo)), de
las **noticias de la liga** (ver
[📰 Noticias de los valores de la liga](#-noticias-de-los-valores-de-la-liga)) y
del detalle diario. La liga se juega **desde el inicio**: la clasificación y el
detalle diario cubren toda la competición; los campeones del mes actual y del
anterior son **parciales** y se calculan aparte. Además, al **tocar un jugador**
(fila de la clasificación, leyenda o su cartera) o un **ticker** (leyenda de
cualquier tarta de cartera) se abre una **ficha de detalle**:

- **Detalle del jugador**: estadísticas (acumulado, mejor y peor día, racha,
  jornadas), rentabilidad acumulada, su cartera con los logos de cada valor y
  las **noticias de toda su cartera** (los titulares de sus valores, mezclados
  de más a menos reciente y etiquetados con el símbolo de cada uno).
- **Detalle del ticker**: logo y nombre de la empresa, peso en la liga, quién
  lo tiene, la variación de precio de la ventana con su mini-gráfica, la
  **recomendación de analistas** (consenso comprar/mantener/vender, reparto de
  opiniones, nº de analistas y precio objetivo con su recorrido), **valores
  relacionados** y sus **noticias** (titular, entradilla, medio y fecha), con
  los enlaces de búsqueda de siempre (Yahoo Finance, Google News, Finviz).
- **Próximo paso del jugador**: en su ficha, una sugerencia orientativa de
  compra/venta sobre una de sus posiciones, elegida por la señal más marcada del
  consenso de analistas. Es informativa (no es una recomendación de inversión).

En móvil la ficha aparece como una **hoja inferior** (bottom sheet) a lo ancho
de la pantalla, con barra de agarre: se cierra deslizándola hacia abajo, tocando
la barra, con la ✕ o pulsando fuera. En pantallas anchas se centra como diálogo.

Los logos se piden en tiempo de vista a logo.dev (por dominio) con respaldo a
un monograma de color si el servicio no responde: la página sigue sin exponer
importes ni operaciones. El **consenso de analistas** se descarga en el build
del ranking (Yahoo Finance, módulo `quoteSummary`) y se cachea en
`data/analysts/<TICKER>.json` (versionado,
igual que los precios); si Yahoo no responde, la sección simplemente no aparece
(nunca se inventan cifras). La **cotización fuera de horario** (pre-market /
after-hours) se descarga también en el build, del mismo `quoteSummary`, pero
**no se cachea**: caduca en minutos, así que o hay dato fresco o no se enseña.
Los valores relacionados están curados en `trader/tickers.py`.

### 📰 Noticias de los valores de la liga

La portada lleva un módulo **«Noticias de la liga»** con los últimos titulares
de todos los valores que hay en cartera, mezclados de más a menos reciente: cada
fila lleva el logo y el símbolo del valor, el medio y la fecha, y abre la
noticia en su medio. Como el resto de listados, enseña cinco y el resto detrás
de «ver más»; si no se ha podido descargar nada, la tarjeta no aparece.

Los titulares de los valores **que alguien tiene en cartera** se descargan
en el build (`trader/news.py`) de la API de noticias de la liga:

```bash
curl -X POST http://imprifyapp.com/api/trader/news \
  -H 'Content-Type: application/json' \
  -d '{"tickers":["AAPL","TSLA"],"timezone":"Europe/Madrid","limit":5}'
```

Se pide **una sola petición en lote** (troceada de 20 en 20 si la liga tiene
muchos valores) con los símbolos de la cartera agregada, y de cada noticia se
guarda titular, entradilla, enlace, medio y fecha. Lo que viaja a la API son
**solo símbolos**, que ya son públicos en la propia página (el widget de cartera
los enseña con su peso): nunca quién tiene qué, ni importes, ni operaciones.

Todo es *best-effort* y con red debajo:

- La respuesta se cachea en `data/news/<TICKER>.json` **por día** (no se
  versiona: los titulares caducan). Si la API falla en un build, se sirve lo
  cacheado; si no hay nada, la ficha se queda con los enlaces de búsqueda.
- Solo se publican noticias con titular y con enlace `http(s)`. Como el texto
  viene de fuera, la página lo pinta siempre como texto plano, nunca como HTML.
- **Las noticias se abren siempre en otra ventana**, también con la web
  instalada como app: ahí un `target="_blank"` se abriría *dentro* de la app
  —sin barra de direcciones ni botón de atrás— así que en modo `standalone` el
  enlace lo abre `window.open`, que salta al navegador. El ranking se queda
  donde estaba.
- El endpoint se puede cambiar con `--news-api` o con la variable de entorno
  `TRADER_NEWS_API`, y `--news-limit` fija cuántos titulares por valor
  (`--news-limit 0` desactiva las noticias). Con `--offline` no se pide nada.

Las **gráficas van suavizadas**: los puntos se unen con un spline cúbico
monótono (Fritsch–Carlson) en vez de con segmentos rectos, así que se van los
picos angulosos sin que la curva se invente subidas ni bajadas —entre dos días
nunca sale del rango de esos dos días, y en cada máximo o mínimo la pendiente
es 0—. El **color de cada jugador** sale de una paleta cálida: naranja el
primero, marrón el segundo y tonos ocres (teja, oro viejo, cobre) a partir del
tercero. Se asigna por orden alfabético de id, así que no cambia si cambia la
clasificación.

### 🎯 Camino al objetivo

Un módulo con **todos los jugadores** y una barra de avance hacia el objetivo
de la liga: **14.000 entre inversiones y efectivo antes del 1 de agosto**. Los
jugadores van de más a menos avance.

La tarjeta es deliberadamente escueta: **ni la fecha ni el importe del objetivo
se escriben** —los sabe quien juega—, solo la cuenta atrás (los días que quedan
para el próximo 1 de agosto: es una meta que se renueva cada año), el nombre,
el porcentaje y la barra. Dos líneas por jugador, para que quepan todos sin
convertir la pantalla en un scroll. Los datos completos siguen en el JSON
embebido de la página.

El porcentaje es el valor de la cartera al último cierre (posiciones + efectivo)
sobre el objetivo de cada uno, así que **publicar el avance es publicar ese
importe**: «42,11 % de 14.000 €» son 5.895 € al céntimo. No es un porcentaje
como el de la clasificación, donde la escala se cancela y no se deduce nada.

Por eso el avance es **opt-in y por defecto está apagado**, incluso para quien
tenga `show_amounts: true`: solo se pinta la barra de quien active
`"show_goal": true` en su `player.json`. Quien no lo active sigue apareciendo
en el módulo —están todos— pero con la barra en trama y sin ninguna cifra.
`show_amounts: true` añade debajo lo que lleva (`5.000 €`), que a esas alturas
ya no revela nada nuevo. El objetivo se cambia por jugador con `"goal"`.

**El objetivo está en euros y las carteras se valoran en la divisa del
extracto** (dólares, para los valores de EE. UU.), así que hay que convertir:
sin hacerlo, una cartera de 5.895 $ salía al 42 % de 14.000 € cuando de verdad
va por el 36 %. El cambio se descarga de Yahoo (`EURUSD=X` y equivalentes) en
el build y se cachea y versiona como un precio más
([`trader/fx.py`](trader/fx.py)); la tarjeta enseña el cambio aplicado bajo el
título (`1 USD = 0,8651 €`), que es lo único que se escribe ahí. Ese cambio es
de la liga, no de cada jugador —es un precio de mercado público—, así que sale
**aunque todos tengan su avance en privado**: es lo que explica cómo se cuenta
el objetivo. Es la **única** parte del proyecto que toca divisas — la
clasificación va en porcentaje y ahí la divisa se cancela. Si Yahoo no responde y no hay
caché, el módulo dice que no hay cambio en vez de enseñar un avance
equivocado.

### 📋 Listados largos

Los listados que crecen con la liga —campeón de cada día, últimas operaciones,
insignias, carteras, la sesión extendida, el detalle diario de cada jugador y
el desglose por valor de una jornada— se pintan con **5 filas y un botón
«ver más»** que despliega el resto (y vuelve a plegarlo). Así el móvil no se
convierte en un scroll infinito según avanza la competición.

### 🌅🌙 Pre-market y after-hours

Cuando el mercado de EE. UU. está en **pre-market** (antes de abrir) o en
**after-hours** (tras el cierre), la web enseña una tarjeta con la **cotización
fuera de horario valor a valor**: precio y variación frente al último cierre
regular de cada ticker de la liga, más la **media ponderada por el peso de cada
posición** en la cartera agregada. La misma información aparece en la ficha de
cada ticker.

Como la página es estática, ese dato es la **foto del momento del build** (por
eso la tarjeta lleva siempre la hora a la que se tomó, y desaparece si se abre
la página más de 6 horas después). El workflow del ranking pasa a propósito por
las dos franjas para que el dato llegue a tiempo. No cuenta para la
clasificación: la jornada solo se cierra con el precio de cierre oficial.

Con el **mercado cerrado**, el widget de *mejor del día* no se queda en blanco:
enseña al ganador de la **última jornada cerrada**, con su fecha y una etiqueta
de «mercado cerrado» para que se vea de qué sesión es el dato.

### 🎖️ Insignias (badges)

La web muestra una sección de **insignias** que premia los hitos de la liga:

- **🏆 Campeón del mes** — el jugador con mejor rentabilidad compuesta de cada
  mes ya cerrado (el mes en curso aparece como provisional, con etiqueta *LIVE*).
- **🔥 Una semana ganando** — cinco jornadas de mercado seguidas en verde.
- **🌱💎🚀 Hitos +5 % / +10 % / +25 %** — al alcanzar esa rentabilidad acumulada.
- **📈🗓️ Dos / tres meses consecutivos ganando** — meses naturales seguidos en
  positivo.
- **🚀 Mayor subida de un valor en un día** — récord de la liga que se **reescribe
  cada vez que se supera** (el anterior se guarda en su historial).

Cada logro es su propia tarjeta y todas se pasan **en carrusel**, deslizando en
horizontal: se quedan ancladas de una en una y debajo se ve en cuál se está
(puntos, o un contador «3 / 27» cuando ya hay demasiadas para pintar un punto
por insignia).

Lo importante es que las insignias se **acumulan en un histórico persistente**
([`data/badges.json`](data/badges.json)): en cada recálculo **no se procesa todo
desde cero**, sino que se **añaden** las insignias nuevas a las ya conseguidas
(una vez ganada, se conserva para siempre) y el récord solo se actualiza cuando
alguien lo bate. La lógica vive en [`trader/badges.py`](trader/badges.py) y el
fichero se versiona igual que los precios y las series públicas.

Para activarla, una sola vez:

1. Ve a **Settings → Pages** del repositorio.
2. En *Build and deployment*, elige **Deploy from a branch**,
   rama **`main`**, carpeta **`/docs`**, y guarda.

En un par de minutos la web queda en
`https://<usuario>.github.io/trader/` (para este repo:
**https://fedegarlo.github.io/trader/**). Cada vez que la Action actualiza
`docs/`, Pages redespliega solo.

## Cómo funciona

Revolut no ofrece API pública de trading para cuentas personales, así que el
flujo se basa en el extracto que da la propia app: el **CSV** que exporta
(Inversiones -> Extractos) o el **PDF de cuenta** ("Account Statement") que
Revolut envía por correo; los dos valen y el PDF se convierte al CSV
equivalente al ingerirlo.

```
extracto de Revolut (CSV o PDF) ──email──> buzón de la liga (privado)
                                            │
                     GitHub Action (IMAP)   │ verifica el remitente por DMARC
                                            │ y CIFRA con el secret TRADER_KEY
                                            ▼
                        players/<id>/trades.csv.enc  (público, ilegible)
                                            │
                     GitHub Action (diaria) │ descifra con el secret TRADER_KEY
                                            ▼
                        reconstruye posiciones día a día
                        valora al cierre (Yahoo Finance)
                                            ▼
                        docs/ranking.md  +  data/public/<id>.json
```

La vía recomendada para subir el extracto es **por email** (el jugador solo
adjunta su extracto y lo envía; ni token de GitHub ni frase ni cifrado
manual). Se
mantiene además la subida desde la web y por CLI como alternativas avanzadas
(ver [`players/README.md`](players/README.md)).

Para cada día natural se calcula:

- **Cómo empezó y cómo terminó la cartera**: valor al inicio y al cierre del
  día (efectivo + posiciones a precio de cierre).
- **P&L del día**: importe ganado/perdido.
- **% del día**: con la fórmula de *Dietz simple*, que descuenta ingresos y
  retiradas de efectivo — meter más dinero no sube la puntuación.
- **% acumulado desde el inicio**: composición geométrica de los porcentajes
  diarios (*time-weighted return*), la métrica justa para comparar jugadores
  que invierten importes distintos.

## Privacidad en un repo público

- Los extractos se cifran (AES vía Fernet + PBKDF2 600k iteraciones) con una
  **única frase de paso compartida por la liga**. En el repo solo hay ficheros
  `.csv.enc` ilegibles para quien no conozca esa frase.
- La frase vive como **GitHub Actions Secret** (`TRADER_KEY`), que solo el
  workflow puede leer. Nadie que no esté en la liga —ni por ser público el
  repo— puede descifrar los extractos.
- En `player.json`, con `"show_amounts": false` el ranking muestra **solo
  porcentajes**: ni importes, ni tickers, ni operaciones.

> **Modelo de confianza:** al ser una liga entre colegas, todos comparten la
> misma frase, así que entre vosotros os podéis descifrar los extractos; lo
> que queda protegido es que el **público** (el repo es abierto) no pueda
> leerlos. Si quisieras privacidad también entre jugadores, se usaría una
> frase por jugador (un secret `PLAYER_<ID>_KEY` cada uno).
>
> **Subida por email (recomendada):** el jugador envía su extracto (CSV o el
> PDF "Account Statement") como adjunto a un buzón de la liga. Un workflow (`.github/workflows/inbox.yml`)
> lo lee por IMAP, **verifica el remitente por DMARC** (no por el `From:`, que
> es falsificable: mira la cabecera `Authentication-Results` que estampa el
> servidor receptor y exige `dmarc=pass`), lo **cifra él mismo** con
> `TRADER_KEY` y lo commitea en `players/<id>/`. Así el jugador **no necesita
> token de GitHub, ni ser colaborador, ni cifrar nada**: solo enviar un email.
> Como es el bot quien decide en qué carpeta escribe según el remitente
> verificado, un jugador no puede tocar la carpeta de otro **por
> construcción**. Dar de alta a alguien nuevo solo requiere añadir su
> `email ↔ id` a la Variable `PLAYER_EMAILS`.
>
> Al editar esa Variable, ojo con **escribirla desde el móvil**: iOS y macOS
> sustituyen las comillas rectas por tipográficas (`“ ”`) y el JSON deja de ser
> válido. La ingesta las interpreta igualmente para no caerse, pero avisa en el
> log; lo suyo es pegar el JSON con comillas rectas (`"`).
>
> El extracto recibido **se fusiona** con el que ya hubiera: manda en el
> periodo que cubre (de su primera a su última operación, así se pueden
> corregir cosas) y fuera de ese periodo se conserva lo ya registrado. Por eso
> un extracto **parcial** (solo el mes en curso) o **antiguo** (exportado antes
> de las últimas operaciones) nunca borra operaciones. Si el extracto no aporta
> nada nuevo no se reescribe nada y **no hay commit**: en el log del workflow
> se ve `0 nueva(s)`. Si esperabas ver operaciones que no salen, casi siempre es
> que Revolut todavía no las había incluido al exportar: vuelve a enviarlo más
> tarde.
>
> **Alternativa: subida por token (web/CLI).** Con `docs/subir.html` el commit
> va directo con el token del jugador (cifrado en el navegador, sin PR). Aquí
> el jugador escribe con un token que da acceso a todo el repo, así que un
> guardián de CI (`.github/workflows/guard.yml`) revierte cualquier push que
> toque carpetas ajenas, según el mapa `PLAYER_OWNERS`. Ver
> [`players/README.md`](players/README.md).

## Empezar

```bash
pip install -r requirements.txt
python -m pytest tests/ -q          # comprobar que todo funciona

# Probar con el jugador de ejemplo (sin red):
python -m trader ranking --players-dir examples/players \
    --prices-dir examples/prices --offline
```

### Unirse a la competición

Lo más fácil es **enviar tu extracto por email**: el administrador te dice a
qué dirección y te registra; tú adjuntas tu extracto de Revolut —el CSV que
exporta la app o el PDF de cuenta que te manda Revolut— en un correo desde tu
dirección registrada. Ojo: manda un extracto que cubra **desde tu primera
operación**; si empieza más tarde, con la cartera ya montada, no se puede
reconstruir (el bot lo avisa en el log). Sin token, sin frase, sin cifrar nada.
También puedes usar la web **[⬆️ Subir tu extracto](https://fedegarlo.github.io/trader/subir.html)**
(cifra en el navegador y sube con tu token, sin PR) o la CLI + PR. Los
detalles, en [`players/README.md`](players/README.md).

### Comandos

| Comando | Qué hace |
|---|---|
| `python -m trader encrypt extracto.csv --out players/fede/trades.csv.enc` | Cifra tu extracto |
| `python -m trader decrypt players/fede/trades.csv.enc` | Lo descifra (comprobación local) |
| `python -m trader report fede` | Serie diaria de un jugador |
| `python -m trader ranking` | Ranking completo + JSON públicos |

La frase de paso se pide por prompt, o se toma de `TRADER_KEY` /
`PLAYER_<ID>_KEY` si están definidas.

## Estructura

```
trader/                     código (parser Revolut, cartera, precios, cifrado, informes, metadatos de tickers)
players/<id>/               configuración pública + extracto cifrado de cada jugador
data/prices/                caché de precios de cierre (se versiona; reproducible)
data/badges.json            histórico acumulativo de insignias (badges)
data/analysts/              caché del consenso de analistas por ticker (Yahoo quoteSummary)
trader/extended.py          cotización fuera de horario (pre-market / after-hours), sin caché
trader/fx.py                cambio a euros para el objetivo de la liga (cacheado en data/prices/)
trader/yahoo.py             sesión anónima de Yahoo (cookie + crumb) compartida
data/public/                series diarias públicas en JSON (para gráficas)
docs/index.html             la web del ranking 🏆 (GitHub Pages)
docs/subir.html             página para subir tu extracto (cifra en el navegador, sin PR)
docs/ranking.md             el ranking en Markdown
.github/workflows/inbox.yml     ingesta extractos recibidos por email (IMAP + DMARC)
.github/workflows/ranking.yml   recalcula y publica el ranking
.github/workflows/guard.yml     revierte pushes que toquen carpetas ajenas (vía token)
examples/                   jugador de ejemplo con precios ficticios para probar
tests/                      pytest
```

## Limitaciones conocidas

- Todo se calcula en la divisa del extracto; si mezclas acciones en USD y
  EUR en la misma cuenta, el tipo de cambio no se ajusta día a día.
- La excepción es el **objetivo de la liga**, que sí convierte a euros el valor
  de la cartera (un cambio al cierre, ver [🎯 Camino al objetivo](#-camino-al-objetivo)):
  ahí se compara un importe, no un porcentaje, y la divisa cambia el resultado.
  Sigue siendo una conversión al cambio del día, no un histórico día a día.
- Los tickers deben existir en Yahoo Finance con el mismo símbolo que usa
  Revolut (para los principales de EE. UU. coincide).
- Tipos de fila no reconocidos del extracto se ignoran con un aviso en el
  informe — abre un issue con el tipo y lo añadimos.
