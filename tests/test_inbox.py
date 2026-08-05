import os
from email.message import EmailMessage

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


# ----- marcado como leído -----

def test_keep_unread_only_when_report_missing():
    # Sin informe (o ilegible): se deja sin leer para poder reintentar.
    assert inbox.Result("no_report").keep_unread
    assert inbox.Result("invalid_report").keep_unread
    # Ingerido o descartado por remitente/autenticación: se marca como leído.
    assert not inbox.Result("ingested").keep_unread
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
