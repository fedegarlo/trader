# 🏆 Trader — competición de rentabilidad con Revolut

Aplicación para trackear las órdenes de compra/venta de Revolut de varios
jugadores, calcular la rentabilidad diaria y acumulada de cada uno, y
publicar un ranking — todo en un repositorio público **sin exponer las
operaciones ni los importes de nadie** (los extractos se suben cifrados).

📊 **El ranking se publica en dos formatos**, actualizados automáticamente
en la apertura y el cierre de cada día de mercado por una GitHub Action:

- **Web (clasificación y widgets)**: `docs/index.html`, servida con GitHub Pages en
  **https://fedegarlo.github.io/trader/** (ver [Ver en web](#ver-en-web)).
- **Markdown**: [`docs/ranking.md`](docs/ranking.md), legible directamente
  en GitHub.

## Ver en web

La página es estática y autocontenida. Se lee como un **hilo de conversación**
con dos agentes —**Warren** (Trader) y **Scout** (Watch)—: salen los dibujitos,
cuentan quién va ganando el día, el mes y el acumulado desde el inicio, y
debajo de cada turno siguen los mismos módulos de siempre. Abre con el
**Canada Grand Prix 26/27**,
que es la **clasificación general** contada como una carrera: de cabecera, el
banner de turismo de Canadá (enlaza a la web oficial de Destination Canada en el
idioma activo), porque el viaje es el premio de la general; debajo, **quién va
ganando** —el líder con su acumulado y su ventaja en puntos sobre el segundo— y
el resto del **podio** (2º y 3º); y a continuación la clasificación completa de
siempre: una tabla tipo parrilla de F1 o tabla de liga (1º, 2º, 3º…, con el
acumulado de cada jugador y el % de la última jornada). Líder, podio y filas
abren la ficha del jugador. Le sigue el **mejor del día** y, después, los
**ganadores del mes**: el mes en curso es el **Gran Premio de la ciudad de
Vancouver**, la **clasificación mensual** contada igual que la general —de
cabecera, el banner de la ciudad (enlaza a la web oficial del ayuntamiento,
[vancouver.ca](https://vancouver.ca/)); debajo, **quién va ganando el mes** con
su rentabilidad y su ventaja en puntos sobre el segundo, el **podio** (2º y 3º)
y la evolución de todos los jugadores, que sigue entera—; el mes pasado, ya
cerrado, se queda en su titular con esa gráfica detrás de «ver más». Los dos
llevan la **categoría del restaurante** que le toca pagar al ganador (ver
[🍽️ Quién invita y **dónde**](#-quién-invita-y-dónde)). Le siguen las
**noticias de la liga** (ver
[📰 Noticias de los valores de la liga](#-noticias-de-los-valores-de-la-liga)) y
el **detalle mensual** (por jugador, una fila por mes con la rentabilidad de
ese mes y el acumulado a su cierre: **solo rentabilidad**, sin importes). La
página cierra con el **camino al objetivo** (ver
[🎯 Camino al objetivo](#-camino-al-objetivo)) y las **insignias**, que son el
palmarés de la liga y no el titular del día. La liga se juega **desde el
inicio**: la clasificación y el
detalle mensual cubren toda la competición; los campeones del mes actual y del
anterior son **parciales** y se calculan aparte. Además, al **tocar un jugador**
(fila de la clasificación, leyenda o su cartera) o un **ticker** (leyenda de
cualquier tarta de cartera) se abre una **ficha de detalle**:
