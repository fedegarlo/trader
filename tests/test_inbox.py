import os
from email.message import EmailMessage

from trader import inbox, secretbox

DATA = os.path.join(os.path.dirname(__file__), "data")
with open(os.path.join(DATA, "sample.csv"), "rb") as _fh:
    SAMPLE_CSV = _fh.read()

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


# ----- extract_csv_attachment -----

def test_extract_csv_by_extension():
    assert inbox.extract_csv_attachment(_make_email()) == SAMPLE_CSV


def test_extract_csv_none_when_absent():
    assert inbox.extract_csv_attachment(_make_email(attach=None)) is None


def test_extract_ignores_non_csv():
    msg = _make_email(attach=b"%PDF-1.4", filename="foto.pdf",
                      ctype="application/pdf")
    assert inbox.extract_csv_attachment(msg) is None


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
    assert res.status == "no_csv"


def test_process_rejects_invalid_csv(tmp_path):
    res = inbox.process_message(_make_email(attach=b"esto,no,es,revolut\n1,2,3,4\n"),
                                _emails_map(), "k", str(tmp_path))
    assert res.status == "invalid_csv"
    assert not (tmp_path / "fede").exists()


# ----- run(): variables de entorno vacías (GitHub Actions) -----

def test_run_empty_env_vars_do_not_crash(monkeypatch):
    # GitHub inyecta secrets/variables sin definir como "" (no ausentes):
    # IMAP_PORT="" no debe reventar con int(""), sino tratarse como no puesto.
    for var in ("IMAP_HOST", "IMAP_PORT", "IMAP_MAILBOX", "IMAP_USER",
                "IMAP_PASS", "INBOX_TRUSTED_AUTHSERV", "PLAYER_EMAILS"):
        monkeypatch.setenv(var, "")
    summary = inbox.run("clave")   # sin credenciales -> sale limpio, sin excepción
    assert summary.ingested == []
