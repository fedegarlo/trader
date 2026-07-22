# 🏆 Trader — competición de rentabilidad con Revolut

Aplicación para trackear las órdenes de compra/venta de Revolut de varios
jugadores, calcular la rentabilidad diaria y acumulada de cada uno, y
publicar un ranking — todo en un repositorio público **sin exponer las
operaciones ni los importes de nadie** (los extractos se suben cifrados).

📊 **El ranking se publica en dos formatos**, actualizados automáticamente
cada día de mercado por una GitHub Action:

- **Web con gráficas**: `docs/index.html`, servida con GitHub Pages en
  **https://fedegarlo.github.io/trader/** (ver [Ver en web](#ver-en-web)).
- **Markdown**: [`docs/ranking.md`](docs/ranking.md), legible directamente
  en GitHub.

## Ver en web

La página es estática y autocontenida (tabla de clasificación + gráfica de
rentabilidad acumulada por jugador + detalle diario). Además, al **tocar un
jugador** (fila del ranking, leyenda o su cartera) o un **ticker** (leyenda de
cualquier tarta de cartera) se abre una **ficha de detalle**:

- **Detalle del jugador**: estadísticas (acumulado, mejor y peor día, racha,
  jornadas), rentabilidad acumulada, su cartera con los logos de cada valor y
  enlaces a noticias.
- **Detalle del ticker**: logo y nombre de la empresa, peso en la liga, quién
  lo tiene, la variación de precio de la ventana con su mini-gráfica, la
  **recomendación de analistas** (consenso comprar/mantener/vender, reparto de
  opiniones, nº de analistas y precio objetivo con su recorrido), **valores
  relacionados** y enlaces a noticias (Yahoo Finance, Google News, Finviz).
- **Próximo paso del jugador**: en su ficha, una sugerencia orientativa de
  compra/venta sobre una de sus posiciones, elegida por la señal más marcada del
  consenso de analistas. Es informativa (no es una recomendación de inversión).
- **Detalle de una jornada**: al tocar un **campeón del día** (tabla del mes) o
  cualquier fila del **detalle diario** se abre una ficha con la **rentabilidad
  de cada valor** de ese jugador ese día (los porcentajes suman el % del día) y,
  debajo, el % del día del **resto de jugadores**. Solo porcentajes, sin
  importes. Las **últimas operaciones** también son filas clicables.

En móvil la ficha aparece como una **hoja inferior** (bottom sheet) a lo ancho
de la pantalla, con barra de agarre: se cierra deslizándola hacia abajo, tocando
la barra, con la ✕ o pulsando fuera. En pantallas anchas se centra como diálogo.

Los logos se piden en tiempo de vista a logo.dev (por dominio) con respaldo a
un monograma de color si el servicio no responde, y las noticias son enlaces de
búsqueda por símbolo: la página sigue sin exponer importes ni operaciones. El
**consenso de analistas** se descarga en el build del ranking (Yahoo Finance,
módulo `quoteSummary`) y se cachea en `data/analysts/<TICKER>.json` (versionado,
igual que los precios); si Yahoo no responde, la sección simplemente no aparece
(nunca se inventan cifras). Los valores relacionados están curados en
`trader/tickers.py`.

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
flujo se basa en el extracto CSV que exporta la propia app:

```
extracto CSV de Revolut ──email──> buzón de la liga (privado)
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
adjunta su CSV y lo envía; ni token de GitHub ni frase ni cifrado manual). Se
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
> **Subida por email (recomendada):** el jugador envía su extracto CSV como
> adjunto a un buzón de la liga. Un workflow (`.github/workflows/inbox.yml`)
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
qué dirección y te registra; tú exportas el CSV de Revolut y lo adjuntas en un
correo desde tu dirección registrada. Sin token, sin frase, sin cifrar nada.
También puedes usar la web **[⬆️ Subir tu extracto](https://fedegarlo.github.io/trader/subir.html)**
(cifra en el navegador y sube con tu token, sin PR) o la CLI + PR. Los
detalles, en [`players/README.md`](players/README.md).

**Dos flujos de actualización.** Tanto por email (botón «Enviar extracto» de la
página principal) como en la web de subida puedes elegir entre:

- **Mensual** (ligero): solo se reemplazan las operaciones del **mes en curso**
  y se conserva el histórico ya subido. Por email viaja como etiqueta
  `[MENSUAL]` en el asunto; la web descifra tu extracto anterior en el navegador
  y fusiona el mes actual antes de subir.
- **Total** (pesado, por defecto): el extracto **reemplaza al anterior por
  completo** y se reprocesa todo. Si el asunto no trae etiqueta, se hace el total.

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
data/analysts/              caché del consenso de analistas por ticker (Yahoo quoteSummary)
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
- Los tickers deben existir en Yahoo Finance con el mismo símbolo que usa
  Revolut (para los principales de EE. UU. coincide).
- Tipos de fila no reconocidos del extracto se ignoran con un aviso en el
  informe — abre un issue con el tipo y lo añadimos.
