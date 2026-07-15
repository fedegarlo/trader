"""Carga de la frase de paso de cada jugador desde el entorno."""

import json

from trader import players, secretbox


def test_env_var_for():
    assert players.env_var_for("fede") == "PLAYER_FEDE_KEY"
    assert players.env_var_for("juan-lopez") == "PLAYER_JUAN_LOPEZ_KEY"


def test_shared_key_for_all_players(monkeypatch):
    # La liga usa una sola frase compartida: TRADER_KEY vale para cualquiera.
    monkeypatch.delenv("PLAYER_FEDE_KEY", raising=False)
    monkeypatch.setenv("TRADER_KEY", "frase-de-la-liga")
    assert players.passphrase_from_env("fede") == "frase-de-la-liga"
    assert players.passphrase_from_env("otro") == "frase-de-la-liga"


def test_player_key_overrides_shared(monkeypatch):
    # Una clave propia tiene prioridad sobre la compartida.
    monkeypatch.setenv("TRADER_KEY", "frase-de-la-liga")
    monkeypatch.setenv("PLAYER_JUAN_KEY", "frase-propia")
    assert players.passphrase_from_env("juan") == "frase-propia"


def test_missing_passphrase(monkeypatch):
    monkeypatch.delenv("PLAYER_FEDE_KEY", raising=False)
    monkeypatch.delenv("TRADER_KEY", raising=False)
    assert players.passphrase_from_env("fede") is None


def _make_player(tmp_path, player_id, enc_passphrase):
    pdir = tmp_path / player_id
    pdir.mkdir()
    (pdir / "player.json").write_text(json.dumps({"display_name": "Ana"}))
    blob = secretbox.encrypt(b"Date,Ticker,Type\n2026-01-01,AAPL,BUY - MARKET\n", enc_passphrase)
    (pdir / "trades.csv.enc").write_bytes(blob)
    return str(tmp_path)


def test_undecryptable_when_wrong_passphrase(tmp_path):
    # El extracto se cifró con una frase distinta a la de la liga.
    players_dir = _make_player(tmp_path, "ana", "frase-de-ana")
    player = players.load_player(players_dir, "ana", passphrase="frase-de-la-liga")
    assert player.enc_count == 1
    assert player.decrypt_failures == 1
    assert player.undecryptable is True
    assert player.events == []


def test_not_undecryptable_with_right_passphrase(tmp_path):
    players_dir = _make_player(tmp_path, "ana", "frase-de-la-liga")
    player = players.load_player(players_dir, "ana", passphrase="frase-de-la-liga")
    assert player.decrypt_failures == 0
    assert player.undecryptable is False
    assert len(player.events) == 1
