"""CLI: python -m trader <comando>

Comandos:
  encrypt   Cifra un extracto CSV para poder subirlo al repositorio.
  decrypt   Descifra un fichero .csv.enc (para comprobarlo en local).
  report    Calcula la serie diaria de un jugador y la muestra por pantalla.
  ranking   Calcula todos los jugadores y genera docs/ranking.md + data/public/.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys

from . import players as players_mod
from . import report as report_mod
from . import secretbox, webpage
from .portfolio import compute_daily_series
from .prices import PriceCache


def _passphrase(args_key: str | None, env_first: str | None = None, confirm: bool = False) -> str:
    if args_key:
        return args_key
    if env_first and os.environ.get(env_first):
        return os.environ[env_first]
    if os.environ.get("TRADER_KEY"):
        return os.environ["TRADER_KEY"]
    phrase = getpass.getpass("Frase de paso: ")
    if confirm and getpass.getpass("Repite la frase: ") != phrase:
        sys.exit("Las frases no coinciden")
    return phrase


def cmd_encrypt(args: argparse.Namespace) -> None:
    out = args.out or args.file + ".enc"
    secretbox.encrypt_file(args.file, out, _passphrase(args.key, confirm=True))
    print(f"Cifrado: {out}")


def cmd_decrypt(args: argparse.Namespace) -> None:
    data = secretbox.decrypt_file(args.file, _passphrase(args.key))
    if args.out:
        with open(args.out, "wb") as fh:
            fh.write(data)
        print(f"Descifrado: {args.out}")
    else:
        sys.stdout.write(data.decode("utf-8-sig"))


def cmd_report(args: argparse.Namespace) -> None:
    env = players_mod.env_var_for(args.player)
    player = players_mod.load_player(args.players_dir, args.player, args.key or os.environ.get(env))
    for warning in player.warnings:
        print(f"AVISO: {warning}", file=sys.stderr)
    if not player.events:
        sys.exit(f"El jugador '{args.player}' no tiene operaciones legibles")

    prices = PriceCache(cache_dir=args.prices_dir, offline=args.offline)
    series = compute_daily_series(player.events, prices)
    print(report_mod.player_daily_table(player, series, last_n=args.days))
    last = series[-1]
    print(f"\nAcumulado desde {series[0].day.isoformat()}: {last.cumulative_return * 100:+.2f}%")


def cmd_ranking(args: argparse.Namespace) -> None:
    ids = players_mod.discover_players(args.players_dir)
    prices = PriceCache(cache_dir=args.prices_dir, offline=args.offline,
                        refresh=getattr(args, "refresh", False))
    computed = []
    pending = []  # extractos subidos pero que no se han podido descifrar
    for player_id in ids:
        player = players_mod.load_player(args.players_dir, player_id)
        for warning in player.warnings:
            print(f"AVISO [{player_id}]: {warning}", file=sys.stderr)
        if not player.events:
            if player.undecryptable:
                pending.append({"id": player_id, "name": player.display_name})
                print(f"AVISO [{player_id}]: extracto sin descifrar (¿frase incorrecta?), "
                      "se omite", file=sys.stderr)
            else:
                print(f"AVISO [{player_id}]: sin operaciones, se omite", file=sys.stderr)
            continue
        series = compute_daily_series(player.events, prices)
        report_mod.write_player_json(player, series, args.public_dir)
        computed.append((player, series))

    content = report_mod.write_ranking(computed, out_path=args.out)
    webpage.write_index(computed, out_path=args.html_out, pending=pending)
    with open(args.pending_out, "w", encoding="utf-8") as fh:
        json.dump(pending, fh, ensure_ascii=False)
    print(content)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="trader", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_enc = sub.add_parser("encrypt", help="cifrar un CSV")
    p_enc.add_argument("file")
    p_enc.add_argument("--out")
    p_enc.add_argument("--key", help="frase de paso (mejor por prompt o TRADER_KEY)")
    p_enc.set_defaults(func=cmd_encrypt)

    p_dec = sub.add_parser("decrypt", help="descifrar un .csv.enc")
    p_dec.add_argument("file")
    p_dec.add_argument("--out")
    p_dec.add_argument("--key")
    p_dec.set_defaults(func=cmd_decrypt)

    p_rep = sub.add_parser("report", help="informe diario de un jugador")
    p_rep.add_argument("player")
    p_rep.add_argument("--players-dir", default="players")
    p_rep.add_argument("--prices-dir", default="data/prices")
    p_rep.add_argument("--days", type=int, default=30)
    p_rep.add_argument("--key")
    p_rep.add_argument("--offline", action="store_true", help="no descargar precios")
    p_rep.set_defaults(func=cmd_report)

    p_rank = sub.add_parser("ranking", help="ranking de todos los jugadores")
    p_rank.add_argument("--players-dir", default="players")
    p_rank.add_argument("--prices-dir", default="data/prices")
    p_rank.add_argument("--public-dir", default="data/public")
    p_rank.add_argument("--out", default="docs/ranking.md")
    p_rank.add_argument("--html-out", default="docs/index.html")
    p_rank.add_argument("--pending-out", default="pending.json",
                        help="lista de extractos sin descifrar (para avisar en CI)")
    p_rank.add_argument("--offline", action="store_true")
    p_rank.add_argument("--refresh", action="store_true",
                        help="volver a descargar precios aunque haya caché")
    p_rank.set_defaults(func=cmd_ranking)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
