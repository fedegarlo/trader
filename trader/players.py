"""Descubrimiento y carga de jugadores.

Cada jugador tiene un directorio ``players/<id>/`` con:

* ``player.json`` — configuración pública (nombre a mostrar, divisa,
  si se muestran importes en el ranking...).
* ``trades.csv.enc`` — extracto de Revolut cifrado (uno o varios ficheros
  ``*.csv.enc``; se concatenan).
* opcionalmente ``*.csv`` en claro, solo para pruebas locales.

La frase de paso de cada jugador se lee de la variable de entorno
``PLAYER_<ID>_KEY`` (id en mayúsculas, guiones como ``_``), que en GitHub
Actions se inyecta desde los *secrets* del repositorio.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from . import revolut, secretbox
from .revolut import Event


@dataclass
class Player:
    player_id: str
    display_name: str
    currency: str = "USD"
    show_amounts: bool = False
    events: list[Event] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def env_var_for(player_id: str) -> str:
    return "PLAYER_" + player_id.upper().replace("-", "_") + "_KEY"


def passphrase_from_env(player_id: str) -> str | None:
    """Frase de paso de un jugador desde el entorno.

    Primero la variable propia ``PLAYER_<ID>_KEY`` (por si algún jugador usa
    una frase distinta, como el demo); si no, la frase **compartida** de la
    liga ``TRADER_KEY``, con la que se cifran todos los extractos. Así, dar de
    alta a un jugador nuevo no requiere ningún secret adicional.
    """
    env = env_var_for(player_id)
    if os.environ.get(env):
        return os.environ[env]
    return os.environ.get("TRADER_KEY")


def load_player(players_dir: str, player_id: str, passphrase: str | None = None) -> Player:
    pdir = os.path.join(players_dir, player_id)
    config_path = os.path.join(pdir, "player.json")
    config = {}
    if os.path.exists(config_path):
        with open(config_path, encoding="utf-8") as fh:
            config = json.load(fh)

    player = Player(
        player_id=player_id,
        display_name=config.get("display_name", player_id),
        currency=config.get("currency", "USD"),
        show_amounts=bool(config.get("show_amounts", False)),
    )

    passphrase = passphrase or passphrase_from_env(player_id)

    texts: list[str] = []
    for name in sorted(os.listdir(pdir)):
        path = os.path.join(pdir, name)
        if name.endswith(".csv.enc"):
            if not passphrase:
                player.warnings.append(
                    f"{name}: sin clave (variable {env_var_for(player_id)} no definida), omitido"
                )
                continue
            try:
                texts.append(secretbox.decrypt_file(path, passphrase).decode("utf-8-sig"))
            except secretbox.DecryptError as exc:
                player.warnings.append(f"{name}: {exc}")
        elif name.endswith(".csv"):
            with open(path, encoding="utf-8-sig") as fh:
                texts.append(fh.read())

    for text in texts:
        events, warnings = revolut.parse_csv(text)
        player.events.extend(events)
        player.warnings.extend(warnings)

    player.events.sort(key=lambda ev: ev.day)
    return player


def discover_players(players_dir: str = "players") -> list[str]:
    if not os.path.isdir(players_dir):
        return []
    return sorted(
        name for name in os.listdir(players_dir)
        if os.path.isdir(os.path.join(players_dir, name)) and not name.startswith((".", "_"))
    )
