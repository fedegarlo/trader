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

> **La liga usa una única frase de paso compartida entre todos.** El
> administrador la guarda una sola vez como secret `TRADER_KEY`; tú solo
> tienes que usar esa misma frase al cifrar. No hay un secret por jugador.

## Cómo unirte (recomendado: desde la web, sin PR)

La forma más simple es la página **[⬆️ Subir tu extracto](https://fedegarlo.github.io/trader/subir.html)**
(enlazada desde el ranking):

1. Pídele al administrador que te añada como **colaborador con permiso Write**
   y que te diga la **frase de paso de la liga**.
2. Exporta tu extracto desde la app de Revolut
   (**Inversiones → ⋯ → Extractos → CSV**).
3. En la web, rellena tu id, nombre y la **frase compartida**, y elige el CSV.
   El extracto **se cifra en tu propio navegador** (nunca sale en claro) y la
   web valida que es un extracto de Revolut legible.
4. Pega un [token fine-grained](https://github.com/settings/tokens?type=beta)
   con permiso **Contents: Read and write** sobre este repo y pulsa *Subir sin
   PR*: hace un commit directo de `player.json` y `trades.csv.enc`.

Para actualizar tus operaciones basta con volver a exportar el extracto y
subirlo de nuevo (misma frase). El administrador **no tiene que hacer nada**.

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
