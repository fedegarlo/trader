import json
import os
from email.message import EmailMessage

import pytest

from pdfbuild import make_pdf
from test_revolut_pdf import STATEMENT
from trader import inbox, secretbox

DATA = os.path.join(os.path.dirname(__file__), "data")
with open(os.path.join(DATA, "sample.csv"), "rb") as _fh:
    SAMPLE_CSV = _fh.read()

SAMPLE_PDF = make_pdf(STATEMENT)          # extracto de cuenta de Revolut en PDF

# Cabecera Authentication-Results típica de Gmail para un correo que pasa DMARC.
DMARC_PASS = ("mx.google.com; dkim=pass header.i=@icloud.com header.s=sig1; "
              "spf=pass (google.com: domain of fede@icloud.com) smtp.mailfrom=fede@icloud.com; "
              "dmarc=pass (p=QUARANTINE sp=QUARANTINE dis=NONE) header.from=icloud.com")


def _make_email(sender="fede@icloud.com", *, auth=DMARC_PASS,
                attach=SAMPLE_CSV, filename="extracto.csv", ctype="text/csv"):
    msg = EmailMessage()
    msg["From"] = f"Fede <{sender}>"
    msg["To"] = "liga.trader@gmail.com"
    msg["Subject"] = "Mi extracto"
    if auth is not None:
        msg["Authentication-Results"] = auth
    msg.set_content("Adjunto mi extracto.")
    if attach is not None:
        maintype, _, subtype = ctype.partition("/")
        msg.add_attachment(attach, maintype=maintype, subtype=subtype,
                           filename=filename)
    return msg


def _emails_map():
    return inbox.parse_player_emails(
        '{"fede": {"email": "fede@icloud.com", "name": "Fede 🚀", "currency": "USD"}}')


# ----- parse_player_emails -----

def test_parse_player_emails_rich_and_short():
    m = inbox.parse_player_emails(
        '{"fede": {"email": "FEDE@icloud.com", "name": "F", "show_amounts": true},'
        ' "ana": "ana@gmail.com"}')
    assert set(m) == {"fede@icloud.com", "ana@gmail.com"}          # normaliza a minúsculas
    assert m["fede@icloud.com"].show_amounts is True
    assert m["ana@gmail.com"].player_id == "ana"
    assert m["ana@gmail.com"].currency == "USD"                     # valor por defecto


def test_parse_player_emails_empty():
    assert inbox.parse_player_emails("") == {}
    assert inbox.parse_player_emails(None) == {}


def test_parse_player_emails_tolera_comillas_tipograficas():
    # Editar la Variable del repo desde el móvil convierte los `"` en `“ ”`.
    # El JSON deja de ser válido, pero la intención se entiende: se acepta.
    m = inbox.parse_player_emails(
        '{"fede": {"email": "fede@icloud.com", "show_amounts": false,'
        ' “show_goal”: true}}')
    assert m["fede@icloud.com"].show_goal is True


def test_parse_player_emails_respeta_comillas_tipograficas_en_los_valores():
    # Si el JSON ya es válido no se toca: las comillas curvas de un nombre
    # están puestas a propósito.
    m = inbox.parse_player_emails(
        '{"fede": {"email": "fede@icloud.com", "name": "Fede “el rápido”"}}')
    assert m["fede@icloud.com"].name == "Fede “el rápido”"


def test_parse_player_emails_json_roto_explica_el_problema():
    with pytest.raises(ValueError, match="PLAYER_EMAILS no es JSON válido"):
        inbox.parse_player_emails('{"fede": ')


def test_parse_player_emails_emails_array_maps_all_to_same_player():
    m = inbox.parse_player_emails(json.dumps({
        "fede": {
            "emails": ["fgarcialorca@gmail.com", "fedegarcia@icloud.com"],
            "name": "Fede",
            "currency": "USD",
            "show_amounts": True,
            "goal": 14000,
            "show_goal": True,
        },
        "ana": {"email": "ana@gmail.com", "name": "Ana", "currency": "EUR"},
    }))
    assert set(m) == {
        "fgarcialorca@gmail.com", "fedegarcia@icloud.com", "ana@gmail.com",
    }
    assert m["fgarcialorca@gmail.com"].player_id == "fede"
    assert m["fedegarcia@icloud.com"].player_id == "fede"
    assert m["fgarcialorca@gmail.com"] is m["fedegarcia@icloud.com"]
    assert m["ana@gmail.com"].player_id == "ana"
    assert m["ana@gmail.com"].email == "ana@gmail.com"


def test_parse_player_emails_accepts_email_as_list():
    m = inbox.parse_player_emails(
        '{"fede": {"email": ["A@x.com", "b@y.com"], "name": "Fede"}}')
    assert set(m) == {"a@x.com", "b@y.com"}
    assert m["a@x.com"].player_id == m["b@y.com"].player_id == "fede"


def test_parse_player_emails_dedupes_duplicate_addresses():
    m = inbox.parse_player_emails(json.dumps({
        "fede": {
            "email": "fede@icloud.com",
            "emails": ["FEDE@icloud.com", "fgarcialorca@gmail.com",
                       "fgarcialorca@gmail.com", ""],
        },
    }))
    assert set(m) == {"fede@icloud.com", "fgarcialorca@gmail.com"}
    assert m["fede@icloud.com"].player_id == "fede"
    assert m["fgarcialorca@gmail.com"].player_id == "fede"
    assert m["fede@icloud.com"] is m["fgarcialorca@gmail.com"]


def test_process_accepts_any_registered_address_for_the_player(tmp_path):
    emails = inbox.parse_player_emails(json.dumps({
        "fede": {
            "emails": ["fgarcialorca@gmail.com", "fedegarcia@icloud.com"],
            "name": "Fede",
        },
    }))
    gmail_auth = ("mx.google.com; dkim=pass header.i=@gmail.com; "
                  "dmarc=pass header.from=gmail.com")
    for sender, auth in (
            ("fgarcialorca@gmail.com", gmail_auth),
            ("fedegarcia@icloud.com", DMARC_PASS)):
        res = inbox.process_message(
            _make_email(sender=sender, auth=auth), emails, "clave-liga",
            str(tmp_path))
        assert res.player_id == "fede"
        assert res.status in {"ingested", "unchanged"}
        assert res.status != "unauthorized"


# ----- verify_sender_auth -----

def test_auth_dmarc_pass():
    ok, why = inbox.verify_sender_auth(_make_email(), "icloud.com")
    assert ok and "dmarc=pass" in why


def test_auth_missing_header():
    ok, why = inbox.verify_sender_auth(_make_email(auth=None), "icloud.com")
    assert not ok and "Authentication-Results" in why


def test_auth_dkim_pass_aligned_without_dmarc():
    hdr = "mx.google.com; dkim=pass header.i=@icloud.com; dmarc=none"
    ok, why = inbox.verify_sender_auth(_make_email(auth=hdr), "icloud.com")
    assert ok and "dkim=pass" in why


def test_auth_dkim_pass_not_aligned():
    hdr = "mx.google.com; dkim=pass header.i=@evil.com; dmarc=none"
    ok, _ = inbox.verify_sender_auth(_make_email(auth=hdr), "icloud.com")
    assert not ok


def test_auth_fail_is_rejected():
    hdr = "mx.google.com; dkim=fail; spf=fail; dmarc=fail"
    ok, _ = inbox.verify_sender_auth(_make_email(auth=hdr), "icloud.com")
    assert not ok


def test_auth_only_trusts_topmost_header():
    # Un atacante incluye una cabecera falsa en el mensaje; la verdadera (la que
    # añade nuestro servidor) va arriba y dice fail -> se rechaza.
    msg = EmailMessage()
    msg["From"] = "fede@icloud.com"
    msg["Authentication-Results"] = "mx.google.com; dmarc=fail"       # real (arriba)
    msg["Authentication-Results"] = "mx.google.com; dmarc=pass"       # falsa (debajo)
    ok, _ = inbox.verify_sender_auth(msg, "icloud.com")
    assert not ok


def test_auth_trusted_authserv_mismatch():
    ok, why = inbox.verify_sender_auth(_make_email(), "icloud.com",
                                       trusted_authserv="mx.google.com")
    assert ok  # coincide
    ok2, why2 = inbox.verify_sender_auth(_make_email(), "icloud.com",
                                         trusted_authserv="mx.otra.com")
    assert not ok2 and "authserv" in why2


# ----- extract_statement_attachment -----

def test_extract_csv_by_extension():
    assert inbox.extract_statement_attachment(_make_email()) == (SAMPLE_CSV, "csv")


def test_extract_none_when_absent():
    assert inbox.extract_statement_attachment(_make_email(attach=None)) is None


def test_extract_pdf_by_extension():
    msg = _make_email(attach=SAMPLE_PDF, filename="extracto.pdf",
                      ctype="application/pdf")
    assert inbox.extract_statement_attachment(msg) == (SAMPLE_PDF, "pdf")


def test_extract_pdf_sent_as_octet_stream():
    # Algunos clientes de correo mandan el PDF sin tipo ni extensión.
    msg = _make_email(attach=SAMPLE_PDF, filename="adjunto",
                      ctype="application/octet-stream")
    assert inbox.extract_statement_attachment(msg) == (SAMPLE_PDF, "pdf")


def test_extract_ignores_other_attachments():
    msg = _make_email(attach=b"\x89PNG\r\n", filename="foto.png",
                      ctype="image/png")
    assert inbox.extract_statement_attachment(msg) is None


# ----- process_message (extremo a extremo) -----

def test_process_ingests_and_encrypts(tmp_path):
    res = inbox.process_message(_make_email(), _emails_map(), "clave-liga",
                                str(tmp_path))
    assert res.ingested and res.player_id == "fede"
    enc = tmp_path / "fede" / "trades.csv.enc"
    assert secretbox.decrypt_file(str(enc), "clave-liga") == SAMPLE_CSV
    cfg = (tmp_path / "fede" / "player.json").read_text(encoding="utf-8")
    assert "Fede" in cfg and "USD" in cfg


def test_process_does_not_overwrite_existing_player_json(tmp_path):
    pdir = tmp_path / "fede"
    pdir.mkdir()
    (pdir / "player.json").write_text('{"display_name": "Custom", "show_amounts": true}',
                                      encoding="utf-8")
    inbox.process_message(_make_email(), _emails_map(), "k", str(tmp_path))
    assert "Custom" in (pdir / "player.json").read_text(encoding="utf-8")


def test_process_rejects_unknown_sender(tmp_path):
    res = inbox.process_message(_make_email(sender="intruso@x.com"),
                                _emails_map(), "k", str(tmp_path))
    assert res.status == "unauthorized"
    assert not (tmp_path / "fede").exists()


def test_process_rejects_failed_auth(tmp_path):
    msg = _make_email(auth="mx.google.com; dmarc=fail")
    res = inbox.process_message(msg, _emails_map(), "k", str(tmp_path))
    assert res.status == "auth_failed"
    assert not (tmp_path / "fede").exists()


def test_process_rejects_missing_attachment(tmp_path):
    res = inbox.process_message(_make_email(attach=None), _emails_map(), "k",
                                str(tmp_path))
    assert res.status == "no_report"


def test_process_rejects_invalid_csv(tmp_path):
    res = inbox.process_message(_make_email(attach=b"esto,no,es,revolut\n1,2,3,4\n"),
                                _emails_map(), "k", str(tmp_path))
    assert res.status == "invalid_report"
    assert not (tmp_path / "fede").exists()


def test_process_ingests_pdf_statement_as_csv(tmp_path):
    msg = _make_email(attach=SAMPLE_PDF, filename="extracto.pdf",
                      ctype="application/pdf")
    res = inbox.process_message(msg, _emails_map(), "clave-liga", str(tmp_path))
    assert res.ingested and "PDF" in res.detail
    # Lo que se guarda cifrado es el CSV equivalente, no el PDF.
    stored = secretbox.decrypt_file(str(tmp_path / "fede" / "trades.csv.enc"),
                                    "clave-liga").decode()
    assert stored.startswith("Date,Ticker,Type,")
    assert "BUY - MARKET" in stored and "NVDA" in stored


def test_process_prefers_csv_when_both_attached(tmp_path):
    msg = _make_email()
    msg.add_attachment(SAMPLE_PDF, maintype="application", subtype="pdf",
                       filename="extracto.pdf")
    res = inbox.process_message(msg, _emails_map(), "clave-liga", str(tmp_path))
    assert res.ingested and "CSV" in res.detail
    stored = secretbox.decrypt_file(str(tmp_path / "fede" / "trades.csv.enc"),
                                    "clave-liga")
    assert stored == SAMPLE_CSV


def test_process_rejects_pdf_that_is_not_a_statement(tmp_path):
    msg = _make_email(attach=make_pdf(["Factura de la luz", "Total 42,00 EUR"]),
                      filename="factura.pdf", ctype="application/pdf")
    res = inbox.process_message(msg, _emails_map(), "k", str(tmp_path))
    assert res.status == "invalid_report" and res.keep_unread
    assert not (tmp_path / "fede").exists()


# ----- fusión con el extracto ya guardado -----

HEADER = SAMPLE_CSV.decode().splitlines()[0] + "\n"


def _row(day, ticker, kind="BUY - MARKET", qty="1", price="$10.00", total="$10.00"):
    return f"{day}T14:00:00.000000Z,{ticker},{kind},{qty},{price},{total},USD,1.00\n"


def _csv(*rows) -> bytes:
    return (HEADER + "".join(rows)).encode()


def _stored(tmp_path, key="clave-liga") -> str:
    return secretbox.decrypt_file(str(tmp_path / "fede" / "trades.csv.enc"),
                                  key).decode()


def test_same_statement_twice_does_not_rewrite(tmp_path):
    """Reenviar el mismo extracto no es una ingesta nueva.

    Cifrar dos veces el mismo CSV da bytes distintos (sal aleatoria), y eso
    hacía que un reenvío sin novedades pareciera datos nuevos y generara commit.
    """
    inbox.process_message(_make_email(), _emails_map(), "clave-liga", str(tmp_path))
    blob = (tmp_path / "fede" / "trades.csv.enc").read_bytes()

    res = inbox.process_message(_make_email(), _emails_map(), "clave-liga",
                                str(tmp_path))
    assert res.status == "unchanged" and not res.ingested
    assert "0 nuevas" in res.detail
    assert (tmp_path / "fede" / "trades.csv.enc").read_bytes() == blob


def test_new_operations_are_counted_and_stored(tmp_path):
    inbox.process_message(_make_email(attach=_csv(_row("2026-07-01", "AAPL"))),
                          _emails_map(), "clave-liga", str(tmp_path))
    res = inbox.process_message(
        _make_email(attach=_csv(_row("2026-07-01", "AAPL"),
                                _row("2026-07-02", "MSFT"))),
        _emails_map(), "clave-liga", str(tmp_path))
    assert res.ingested and "1 nueva" in res.detail
    assert "MSFT" in _stored(tmp_path)


def test_stale_statement_keeps_later_operations(tmp_path):
    """Un extracto exportado *antes* de las últimas operaciones no las borra."""
    inbox.process_message(
        _make_email(attach=_csv(_row("2026-07-01", "AAPL"),
                                _row("2026-07-06", "NVDA"))),
        _emails_map(), "clave-liga", str(tmp_path))
    # Reenvía uno viejo, que solo llega hasta el 01: la de NVDA sigue estando.
    res = inbox.process_message(_make_email(attach=_csv(_row("2026-07-01", "AAPL"))),
                                _emails_map(), "clave-liga", str(tmp_path))
    assert res.status == "unchanged"        # no aporta ni pierde nada
    assert "NVDA" in _stored(tmp_path)


def test_partial_statement_keeps_earlier_history(tmp_path):
    """Un extracto solo del mes en curso no borra el histórico anterior."""
    inbox.process_message(
        _make_email(attach=_csv(_row("2026-07-01", "AAPL"),
                                _row("2026-07-02", "MSFT"))),
        _emails_map(), "clave-liga", str(tmp_path))
    res = inbox.process_message(_make_email(attach=_csv(_row("2026-08-03", "NVDA"))),
                                _emails_map(), "clave-liga", str(tmp_path))
    assert res.ingested and "1 nueva" in res.detail and "conservada" in res.detail
    stored = _stored(tmp_path)
    assert "AAPL" in stored and "MSFT" in stored and "NVDA" in stored


def test_statement_corrects_its_own_period(tmp_path):
    """Dentro del periodo que cubre, el extracto nuevo manda (permite corregir)."""
    inbox.process_message(
        _make_email(attach=_csv(_row("2026-07-01", "AAPL", qty="1"),
                                _row("2026-07-02", "MSFT"))),
        _emails_map(), "clave-liga", str(tmp_path))
    inbox.process_message(
        _make_email(attach=_csv(_row("2026-07-01", "AAPL", qty="2"),
                                _row("2026-07-02", "MSFT"))),
        _emails_map(), "clave-liga", str(tmp_path))
    stored = _stored(tmp_path)
    assert stored.count("AAPL") == 1                 # no se duplica la corregida
    assert ",AAPL,BUY - MARKET,2," in stored


def test_merge_keeps_new_statement_verbatim_when_nothing_to_keep():
    merged, stats = inbox.merge_statements(None, SAMPLE_CSV.decode())
    assert merged == SAMPLE_CSV.decode()             # no se reformatea
    assert stats.total == 7 and stats.new == 7 and stats.kept == 0
    assert stats.period == "2026-07-01…2026-07-04"


def test_unreadable_rows_are_reported(tmp_path):
    """Las filas que el parser no entiende se avisan también en la ingesta."""
    raw = _csv(_row("2026-07-01", "AAPL"),
               "2026-07-02T14:00:00.000000Z,AAPL,MARCIANADA,1,$1.00,$1.00,USD,1.00\n")
    res = inbox.process_message(_make_email(attach=raw), _emails_map(),
                                "clave-liga", str(tmp_path))
    assert res.ingested
    assert any("MARCIANADA" in w for w in res.warnings)


# ----- marcado como leído -----

def test_keep_unread_only_when_report_missing():
    # Sin informe (o ilegible): se deja sin leer para poder reintentar.
    assert inbox.Result("no_report").keep_unread
    assert inbox.Result("invalid_report").keep_unread
    # Ingerido, sin novedades o descartado: se marca como leído.
    assert not inbox.Result("ingested").keep_unread
    assert not inbox.Result("unchanged").keep_unread
    assert not inbox.Result("unauthorized").keep_unread
    assert not inbox.Result("auth_failed").keep_unread


class _FakeIMAP:
    """Buzón IMAP de mentira con los mensajes que se le pasen."""

    def __init__(self, messages):
        self._messages = messages          # num (bytes) -> EmailMessage
        self.stored = []                   # (num, flags) de cada store()

    def login(self, *_a):
        return "OK", []

    def select(self, *_a):
        return "OK", []

    def search(self, _charset, *_criteria):
        return "OK", [b" ".join(self._messages)]

    def fetch(self, num, _parts):
        return "OK", [(b"1 (BODY[] {1})", self._messages[num].as_bytes())]

    def store(self, num, flags, value):
        self.stored.append((num, f"{flags} {value}"))
        return "OK", []

    def close(self):
        return "OK", []

    def logout(self):
        return "OK", []


def _run_with_mailbox(monkeypatch, tmp_path, messages):
    fake = _FakeIMAP(messages)
    monkeypatch.setattr(inbox.imaplib, "IMAP4_SSL", lambda *a, **k: fake)
    monkeypatch.setenv("PLAYER_EMAILS",
                       '{"fede": {"email": "fede@icloud.com", "name": "Fede"}}')
    summary = inbox.run("clave", str(tmp_path), user="buzon@x.com", password="pw")
    return fake, summary


def test_run_does_not_mark_as_read_without_report(monkeypatch, tmp_path):
    fake, summary = _run_with_mailbox(monkeypatch, tmp_path,
                                      {b"1": _make_email(attach=None)})
    assert [r.status for r in summary.skipped] == ["no_report"]
    assert fake.stored == []          # el correo sigue sin leer


def test_run_does_not_mark_as_read_with_unreadable_report(monkeypatch, tmp_path):
    msg = _make_email(attach=b"esto,no,es,revolut\n1,2,3,4\n")
    fake, summary = _run_with_mailbox(monkeypatch, tmp_path, {b"1": msg})
    assert [r.status for r in summary.skipped] == ["invalid_report"]
    assert fake.stored == []


def test_run_marks_as_read_after_ingesting(monkeypatch, tmp_path):
    fake, summary = _run_with_mailbox(monkeypatch, tmp_path, {b"1": _make_email()})
    assert summary.ingested == ["fede"]
    assert fake.stored == [(b"1", "+FLAGS \\Seen")]


def test_run_marks_as_read_unauthorized_sender(monkeypatch, tmp_path):
    msg = _make_email(sender="intruso@x.com")
    fake, summary = _run_with_mailbox(monkeypatch, tmp_path, {b"1": msg})
    assert [r.status for r in summary.skipped] == ["unauthorized"]
    assert fake.stored == [(b"1", "+FLAGS \\Seen")]


# ----- run(): variables de entorno vacías (GitHub Actions) -----

def test_run_empty_env_vars_do_not_crash(monkeypatch):
    # GitHub inyecta secrets/variables sin definir como "" (no ausentes):
    # IMAP_PORT="" no debe reventar con int(""), sino tratarse como no puesto.
    for var in ("IMAP_HOST", "IMAP_PORT", "IMAP_MAILBOX", "IMAP_USER",
                "IMAP_PASS", "INBOX_TRUSTED_AUTHSERV", "PLAYER_EMAILS"):
        monkeypatch.setenv(var, "")
    summary = inbox.run("clave")   # sin credenciales -> sale limpio, sin excepción
    assert summary.ingested == []


# ----- objetivo de la liga en el alta por email -----

def test_parse_player_emails_reads_the_goal_config():
    m = inbox.parse_player_emails(
        '{"fede": {"email": "fede@icloud.com", "goal": 20000, "show_goal": true},'
        ' "ana": "ana@gmail.com"}')
    assert m["fede@icloud.com"].goal == 20000.0
    assert m["fede@icloud.com"].show_goal is True
    # por defecto, el objetivo de la liga y sin publicar el avance
    assert m["ana@gmail.com"].goal == 14000.0
    assert m["ana@gmail.com"].show_goal is False


def test_new_player_json_carries_the_goal_config(tmp_path):
    emails = inbox.parse_player_emails(
        '{"fede": {"email": "fede@icloud.com", "name": "Fede", "goal": 20000,'
        ' "show_goal": true}}')
    inbox.process_message(_make_email(), emails, "clave-liga", str(tmp_path))
    cfg = json.loads((tmp_path / "fede" / "player.json").read_text(encoding="utf-8"))
    assert cfg["goal"] == 20000.0 and cfg["show_goal"] is True


# ----- ingest-csv (camino sin IMAP) -----

def test_player_cfg_for_defaults_without_files(tmp_path):
    cfg = inbox.player_cfg_for("fede", str(tmp_path), emails_raw="")
    assert cfg.player_id == "fede"
    assert cfg.name == "fede"
    assert cfg.currency == "USD"
    assert cfg.show_amounts is False
    assert cfg.email == ""


def test_player_cfg_for_reads_player_emails(tmp_path):
    cfg = inbox.player_cfg_for("fede", str(tmp_path), emails_raw=json.dumps({
        "fede": {"email": "fede@icloud.com", "name": "Fede", "currency": "EUR",
                 "show_amounts": True, "goal": 20000, "show_goal": True},
    }))
    assert cfg.name == "Fede" and cfg.currency == "EUR"
    assert cfg.show_amounts is True and cfg.goal == 20000.0 and cfg.show_goal
    assert cfg.email == "fede@icloud.com"


def test_player_cfg_for_player_json_wins_over_emails(tmp_path):
    pdir = tmp_path / "fede"
    pdir.mkdir()
    (pdir / "player.json").write_text(json.dumps({
        "display_name": "Federico", "currency": "USD", "show_amounts": False,
        "goal": 14000, "show_goal": True,
    }), encoding="utf-8")
    cfg = inbox.player_cfg_for("fede", str(tmp_path), emails_raw=json.dumps({
        "fede": {"email": "fede@icloud.com", "name": "Otro", "currency": "EUR",
                 "show_amounts": True, "goal": 1, "show_goal": False},
    }))
    assert cfg.name == "Federico" and cfg.currency == "USD"
    assert cfg.show_amounts is False and cfg.goal == 14000.0 and cfg.show_goal
    assert cfg.email == "fede@icloud.com"   # el correo solo vive en PLAYER_EMAILS


def test_ingest_csv_encrypts_and_skips_imap(tmp_path, monkeypatch):
    """write_extract + parse_csv, sin tocar el buzón."""
    monkeypatch.delenv("IMAP_USER", raising=False)
    monkeypatch.delenv("IMAP_PASS", raising=False)
    res = inbox.ingest_csv("fede", SAMPLE_CSV.decode(), "clave-liga", str(tmp_path))
    assert res.ingested and res.player_id == "fede"
    assert "CSV" in res.detail and "nueva" in res.detail
    enc = tmp_path / "fede" / "trades.csv.enc"
    assert secretbox.decrypt_file(str(enc), "clave-liga") == SAMPLE_CSV
    cfg = json.loads((tmp_path / "fede" / "player.json").read_text(encoding="utf-8"))
    assert cfg["display_name"] == "fede"


def test_ingest_csv_uses_existing_player_json(tmp_path):
    pdir = tmp_path / "fede"
    pdir.mkdir()
    (pdir / "player.json").write_text(
        '{"display_name": "Fede", "currency": "USD", "show_amounts": true}',
        encoding="utf-8")
    inbox.ingest_csv("fede", SAMPLE_CSV.decode(), "clave-liga", str(tmp_path))
    cfg = json.loads((pdir / "player.json").read_text(encoding="utf-8"))
    assert cfg["display_name"] == "Fede" and cfg["show_amounts"] is True


def test_ingest_csv_same_statement_is_unchanged(tmp_path):
    inbox.ingest_csv("fede", SAMPLE_CSV.decode(), "clave-liga", str(tmp_path))
    blob = (tmp_path / "fede" / "trades.csv.enc").read_bytes()
    res = inbox.ingest_csv("fede", SAMPLE_CSV.decode(), "clave-liga", str(tmp_path))
    assert res.status == "unchanged" and not res.ingested
    assert "0 nuevas" in res.detail
    assert (tmp_path / "fede" / "trades.csv.enc").read_bytes() == blob


def test_ingest_csv_rejects_empty_or_invalid(tmp_path):
    empty = inbox.ingest_csv("fede", "", "clave-liga", str(tmp_path))
    assert empty.status == "invalid_report"
    bad = inbox.ingest_csv("fede", "esto,no,es,revolut\n1,2,3,4\n",
                           "clave-liga", str(tmp_path))
    assert bad.status == "invalid_report"
    assert not (tmp_path / "fede").exists()


def test_ingest_csv_rejects_invalid_player_id(tmp_path):
    res = inbox.ingest_csv("../evil", SAMPLE_CSV.decode(), "k", str(tmp_path))
    assert res.status == "unauthorized"
    assert list(tmp_path.iterdir()) == []


def test_cli_ingest_csv(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TRADER_KEY", "clave-liga")
    csv_path = tmp_path / "extracto.csv"
    csv_path.write_bytes(SAMPLE_CSV)
    from trader.__main__ import main
    main(["ingest-csv", "--player", "fede", "--players-dir", str(tmp_path),
          str(csv_path)])
    out = capsys.readouterr().out
    assert "ingerido" in out and "fede" in out
    assert secretbox.decrypt_file(str(tmp_path / "fede" / "trades.csv.enc"),
                                  "clave-liga") == SAMPLE_CSV


def test_cli_ingest_csv_rejects_invalid(tmp_path, monkeypatch):
    monkeypatch.setenv("TRADER_KEY", "clave-liga")
    csv_path = tmp_path / "basura.csv"
    csv_path.write_text("no,es,un,extracto\n1,2,3,4\n", encoding="utf-8")
    from trader.__main__ import main
    with pytest.raises(SystemExit) as exc:
        main(["ingest-csv", "--player", "fede", "--players-dir", str(tmp_path),
              str(csv_path)])
    assert exc.value.code == 1
    assert not (tmp_path / "fede").exists()
