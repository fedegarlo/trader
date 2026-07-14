# Jugadores

> El directorio `demo/` es un jugador de demostración con operaciones
> ficticias; su frase de paso es pública (`demo`) para que se pueda ver el
> flujo completo funcionando. Bórralo (y su línea en
> `.github/workflows/ranking.yml`) cuando haya jugadores reales.

Cada jugador tiene su propio directorio:

```
players/
  fede/
    player.json      <- configuración pública
    trades.csv.enc   <- extracto de Revolut CIFRADO (nunca subas el .csv en claro)
```

## Cómo unirte (recomendado: desde la web, sin PR)

La forma más simple es la página **[⬆️ Subir tu extracto](https://fedegarlo.github.io/trader/subir.html)**
(enlazada desde el ranking):

1. Exporta tu extracto desde la app de Revolut
   (**Inversiones → ⋯ → Extractos → CSV**).
2. En la web, rellena tu id, nombre y frase de paso, y elige el CSV. El
   extracto **se cifra en tu propio navegador** (nunca sale en claro) y la web
   valida que es un extracto de Revolut legible.
3. Pega un [token fine-grained](https://github.com/settings/tokens?type=beta)
   con permiso **Contents: Read and write** sobre este repo y pulsa *Subir sin
   PR*: hace un commit directo de `player.json` y `trades.csv.enc`.

> **Solo la primera vez**, pide al administrador que cree el secret
> `PLAYER_<TU_ID>_KEY` con tu frase de paso
> (Settings → Secrets and variables → Actions). Ya no hace falta editar el
> workflow: `trader` lee todas las claves de los secrets automáticamente. Las
> siguientes actualizaciones no requieren nada del administrador.

Para actualizar tus operaciones basta con volver a exportar el extracto y
subirlo de nuevo con la misma frase de paso.

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
2. Elige una frase de paso y cifra tu extracto:

   ```bash
   python -m trader encrypt extracto.csv --out players/<tu-id>/trades.csv.enc
   ```

3. Sube `player.json` y `trades.csv.enc` en un pull request. **Jamás subas el
   CSV sin cifrar** (el `.gitignore` ayuda, pero revisa el diff).
4. Pide al administrador que cree el secret `PLAYER_<TU_ID>_KEY` con tu frase
   de paso (Settings → Secrets and variables → Actions).
