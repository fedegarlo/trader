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
rentabilidad acumulada por jugador + detalle diario). Para activarla, una
sola vez:

1. Ve a **Settings → Pages** del repositorio.
2. En *Build and deployment*, elige **Deploy from a branch**,
   rama **`main`**, carpeta **`/docs`**, y guarda.

En un par de minutos la web queda en
`https://<usuario>.github.io/trader/` (para este repo:
**https://fedegarlo.github.io/trader/**). Cada vez que la Action actualiza
`docs/`, Pages redespliega solo.

> El ranking incluye un jugador **Demo 🤖** con operaciones ficticias
> (cifradas con la frase pública `demo`) para ver la primera iteración
> funcionando de punta a punta. Se elimina borrando `players/demo/` y su
> línea en el workflow.

## Cómo funciona

Revolut no ofrece API pública de trading para cuentas personales, así que el
flujo se basa en el extracto CSV que exporta la propia app:

```
extracto CSV de Revolut ──cifrar──> players/<id>/trades.csv.enc  (público, ilegible)
                                            │
                     GitHub Action (diaria) │ descifra con el secret PLAYER_<ID>_KEY
                                            ▼
                        reconstruye posiciones día a día
                        valora al cierre (Yahoo Finance)
                                            ▼
                        docs/ranking.md  +  data/public/<id>.json
```

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

- Cada jugador cifra su extracto con una **frase de paso propia**
  (`python -m trader encrypt ...`, AES vía Fernet + PBKDF2 600k iteraciones).
  En el repo solo hay ficheros `.csv.enc` ilegibles.
- Las frases de paso viven como **GitHub Actions Secrets**
  (`PLAYER_<ID>_KEY`), que solo el workflow puede leer. Nadie —ni siquiera
  los administradores— puede ver un secret una vez guardado.
- En `player.json`, con `"show_amounts": false` el ranking muestra **solo
  porcentajes**: ni importes, ni tickers, ni operaciones.

> ⚠️ Los secrets no están disponibles en workflows lanzados desde forks:
> los jugadores añaden sus ficheros por PR, pero el ranking solo se
> recalcula al hacer merge a `main`.

## Empezar

```bash
pip install -r requirements.txt
python -m pytest tests/ -q          # comprobar que todo funciona

# Probar con el jugador de ejemplo (sin red):
python -m trader ranking --players-dir examples/players \
    --prices-dir examples/prices --offline
```

### Unirse a la competición

Sigue los pasos de [`players/README.md`](players/README.md): exportar el
extracto de Revolut, cifrarlo, subirlo por PR y registrar tu secret.

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
trader/            código (parser Revolut, cartera, precios, cifrado, informes)
players/<id>/      configuración pública + extracto cifrado de cada jugador
data/prices/       caché de precios de cierre (se versiona; reproducible)
data/public/       series diarias públicas en JSON (para gráficas)
docs/ranking.md    el ranking 🏆
examples/          jugador de ejemplo con precios ficticios para probar
tests/             pytest
```

## Limitaciones conocidas

- Todo se calcula en la divisa del extracto; si mezclas acciones en USD y
  EUR en la misma cuenta, el tipo de cambio no se ajusta día a día.
- Los tickers deben existir en Yahoo Finance con el mismo símbolo que usa
  Revolut (para los principales de EE. UU. coincide).
- Tipos de fila no reconocidos del extracto se ignoran con un aviso en el
  informe — abre un issue con el tipo y lo añadimos.
