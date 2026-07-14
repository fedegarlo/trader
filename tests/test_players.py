"""Carga de la frase de paso de cada jugador desde el entorno."""

import json

from trader import players


def test_env_var_for():
    assert players.env_var_for("fede") == "PLAYER_FEDE_KEY"
    assert players.env_var_for("juan-lopez") == "PLAYER_JUAN_LOPEZ_KEY"


def test_passphrase_from_explicit_env(monkeypatch):
    monkeypatch.setenv("PLAYER_FEDE_KEY", "directa")
    monkeypatch.delenv("TRADER_SECRETS_JSON", raising=False)
    assert players.passphrase_from_env("fede") == "directa"


def test_passphrase_from_secrets_json(monkeypatch):
    monkeypatch.delenv("PLAYER_FEDE_KEY", raising=False)
    monkeypatch.setenv("TRADER_SECRETS_JSON",
                       json.dumps({"PLAYER_FEDE_KEY": "desde-json", "otra": "x"}))
    assert players.passphrase_from_env("fede") == "desde-json"


def test_explicit_env_wins_over_json(monkeypatch):
    monkeypatch.setenv("PLAYER_FEDE_KEY", "directa")
    monkeypatch.setenv("TRADER_SECRETS_JSON", json.dumps({"PLAYER_FEDE_KEY": "json"}))
    assert players.passphrase_from_env("fede") == "directa"


def test_missing_passphrase(monkeypatch):
    monkeypatch.delenv("PLAYER_FEDE_KEY", raising=False)
    monkeypatch.delenv("TRADER_SECRETS_JSON", raising=False)
    assert players.passphrase_from_env("fede") is None


def test_malformed_secrets_json(monkeypatch):
    monkeypatch.delenv("PLAYER_FEDE_KEY", raising=False)
    monkeypatch.setenv("TRADER_SECRETS_JSON", "no es json")
    assert players.passphrase_from_env("fede") is None
