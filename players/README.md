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

## Cómo unirte a la competición

1. Exporta tu extracto desde la app de Revolut:
   **Inversiones → ⋯ → Extractos → Extracto de la cuenta (Excel/CSV)**.
2. Crea tu directorio `players/<tu-id>/` con un `player.json`:

   ```json
   {
     "display_name": "Tu Nombre",
     "currency": "USD",
     "show_amounts": false
   }
   ```

   Con `show_amounts: false` el ranking público solo muestra porcentajes;
   tus importes no se publican.
3. Elige una frase de paso y cifra tu extracto:

   ```bash
   python -m trader encrypt extracto.csv --out players/<tu-id>/trades.csv.enc
   ```

4. Sube `player.json` y `trades.csv.enc` en un pull request. **Jamás subas el
   CSV sin cifrar** (el `.gitignore` ayuda, pero revisa el diff).
5. Pide al administrador del repositorio que cree el secret
   `PLAYER_<TU_ID>_KEY` con tu frase de paso
   (Settings → Secrets and variables → Actions) y que añada la línea
   correspondiente en `.github/workflows/ranking.yml`.

Para actualizar tus operaciones, vuelve a exportar el extracto completo,
cífralo con la misma frase y reemplaza el `.csv.enc`.
