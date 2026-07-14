"""Carga de la frase de paso de cada jugador desde el entorno."""

from trader import players


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
    # Una clave propia (p.ej. el demo) tiene prioridad sobre la compartida.
    monkeypatch.setenv("TRADER_KEY", "frase-de-la-liga")
    monkeypatch.setenv("PLAYER_DEMO_KEY", "demo")
    assert players.passphrase_from_env("demo") == "demo"


def test_missing_passphrase(monkeypatch):
    monkeypatch.delenv("PLAYER_FEDE_KEY", raising=False)
    monkeypatch.delenv("TRADER_KEY", raising=False)
    assert players.passphrase_from_env("fede") is None
