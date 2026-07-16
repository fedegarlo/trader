# Jugadores

Cada jugador tiene su propio directorio:

```
players/
  fede/
    player.json      <- configuración pública
    trades.csv.enc   <- extracto de Revolut CIFRADO (nunca subas el .csv en claro)
```

> **La liga usa una única frase de paso compartida entre todos.** El
> administrador la guarda una sola vez como secret `TRADER_KEY`; tú solo
> tienes que usar esa misma frase al cifrar. No hay un secret por jugador.

## Cómo unirte (recomendado: por email)

La forma más simple es **enviar tu extracto por correo**. No necesitas token
de GitHub, ni ser colaborador, ni cifrar nada:

1. Pídele al administrador la **dirección del buzón de la liga** y que te
   **registre** (tu id ↔ tu dirección de correo).
2. Exporta tu extracto desde la app de Revolut
   (**Inversiones → ⋯ → Extractos → CSV**).
3. **Envía un email a esa dirección, con el CSV adjunto, desde tu dirección
   registrada.** Eso es todo.

Un workflow lee el buzón cada pocos minutos, **verifica que el correo pasa
DMARC** (que de verdad viene de tu dirección, no de alguien que la suplanta),
**cifra tu CSV** con la frase de la liga y lo publica en tu carpeta
`players/<tu-id>/`. En 1–2 minutos aparece en el ranking.

> **Importante:** envía el correo **desde la dirección que registró el
> administrador**, y desde un proveedor que use DMARC (Gmail, iCloud, Outlook,
> etc. — casi todos). Si el remitente no coincide o no pasa DMARC, el extracto
> se descarta por seguridad. Para actualizar tus operaciones, reenvía un CSV
> nuevo: el último gana.

## Alternativa: desde la web, con token (sin PR)

La página **[⬆️ Subir tu extracto](https://fedegarlo.github.io/trader/subir.html)**
cifra tu CSV en el navegador y lo sube con tu token de GitHub. Requiere ser
**colaborador con permiso Write**, estar registrado en `PLAYER_OWNERS` y usar
un [token fine-grained](https://github.com/settings/tokens?type=beta) con
permiso **Contents: Read and write**. Un guardián de CI solo te deja escribir
en tu propia carpeta `players/<tu-id>/`.

## Alternativa: por línea de comandos y pull request

1. Crea tu directorio `players/<tu-id>/` con un `player.json`:

   ```json
   {
     "display_name": "Tu Nombre",
     "currency": "USD",
     "show_amounts": false
   }
   ```

   Con `show_amounts: false` el ranking público solo muestra porcentajes;
   tus importes no se publican.
2. Cifra tu extracto con la **frase compartida de la liga**:

   ```bash
   python -m trader encrypt extracto.csv --out players/<tu-id>/trades.csv.enc
   ```

3. Sube `player.json` y `trades.csv.enc` en un pull request. **Jamás subas el
   CSV sin cifrar** (el `.gitignore` ayuda, pero revisa el diff).

## Para el administrador

**Configuración inicial (una sola vez para toda la liga):** crea el secret
`TRADER_KEY` (Settings → Secrets and variables → Actions → *Secrets*) con la
frase compartida.

### Vía por email (recomendada)

Configuración inicial, **una sola vez**:

1. Crea un **buzón dedicado** para la liga (p. ej. una cuenta de Gmail nueva) y
   activa IMAP. En Gmail, genera una **contraseña de aplicación**.
2. Añade estos **secrets** (Settings → Secrets and variables → Actions →
   *Secrets*):
   - `IMAP_USER` — la dirección del buzón (p. ej. `liga.trader@gmail.com`).
   - `IMAP_PASS` — la contraseña de aplicación.
   - (opcional) `IMAP_HOST` (por defecto `imap.gmail.com`), `IMAP_PORT` (993).
3. (Opcional pero recomendable) Añade la **Variable** `INBOX_TRUSTED_AUTHSERV`
   con el identificador de tu servidor receptor (Gmail: `mx.google.com`). Así
   solo se confía en la cabecera `Authentication-Results` de ese servidor.

**Dar de alta a un jugador** — **una vez por jugador** (las actualizaciones no
requieren nada): regístralo en la Variable `PLAYER_EMAILS` (Settings → Secrets
and variables → Actions → *Variables*), un JSON `id → datos`:

```json
{
  "fede": { "email": "fede@icloud.com", "name": "Fede 🚀", "currency": "USD", "show_amounts": false },
  "ana":  { "email": "ana@gmail.com", "name": "Ana", "currency": "EUR", "show_amounts": true }
}
```

El workflow `.github/workflows/inbox.yml` usa este mapa para autorizar al
remitente y, si el jugador es nuevo, crear su `player.json`. No hace falta que
sea colaborador ni que tenga token. Dile la dirección del buzón y listo.

> **Seguridad:** el workflow **no se fía del `From:`** (falsificable): exige
> que el correo pase **DMARC** (o un DKIM alineado) según la cabecera
> `Authentication-Results` que estampa el buzón receptor. Y como el bot solo
> escribe en la carpeta del `id` mapeado al remitente verificado, un jugador
> **no puede escribir en la de otro por construcción** (aislación preventiva,
> no reactiva). El CSV en claro pasa por el buzón y el runner de Actions: para
> una liga entre colegas —donde el admin ya conoce la frase y puede descifrar a
> todos— no es una pérdida real de privacidad frente al público.

### Vía por token (web/CLI, alternativa)

Si además quieres permitir la subida con token desde `docs/subir.html`:

1. **Colaborador:** invítalo con permiso **Write** (Settings → Collaborators).
2. **Regístralo** en la Variable `PLAYER_OWNERS`, un JSON `id → usuario de
   GitHub`:

   ```json
   { "fede": "fedegarlo", "juan": "juangh" }
   ```

   El guardián de CI (`.github/workflows/guard.yml`) usa este mapa: si alguien
   toca una carpeta que no es la suya, un id no registrado o ficheros fuera de
   `players/`, **revierte el push y abre una issue**. Tú (admin) y los bots
   quedáis exentos.
3. **Frase de la liga:** dile la frase compartida.

> El guardián es una malla de seguridad contra despistes y gamberreo casual
> (los jugadores no pueden editar ni el workflow ni la Variable). Un insider
> decidido con un token más amplio podría sortearlo; para prevención estricta
> haría falta el *gatekeeper* serverless. La vía por email no tiene este
> problema: el jugador nunca recibe un token del repo.
