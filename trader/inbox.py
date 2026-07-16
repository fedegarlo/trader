"""Ingesta de extractos por email (IMAP), sin token de GitHub por jugador.

Idea: cada jugador **envía su extracto CSV como adjunto a un buzón** de la
liga. Un workflow programado ejecuta este módulo, que:

1. Se conecta al buzón por IMAP y lee los correos no vistos.
2. **Verifica el remitente por DMARC** (no por el ``From:`` a secas, que es
   falsificable): mira la cabecera ``Authentication-Results`` que estampa el
   propio servidor receptor y exige ``dmarc=pass`` (o un ``dkim=pass``
   alineado con el dominio del remitente). Así, quien controla la dirección
   de correo es quien puede subir en su nombre — una frontera de seguridad
   equivalente a "tienes un token de GitHub".
3. Mapea el remitente a un jugador con ``PLAYER_EMAILS`` (Variable del repo,
   JSON ``id -> {email, name, currency, show_amounts}``).
4. Valida que el adjunto es un extracto de Revolut legible.
5. **Cifra el CSV con la frase de la liga** (``TRADER_KEY``) y lo escribe en
   ``players/<id>/trades.csv.enc``. El jugador manda el CSV en claro a un
   buzón privado; el cifrado del fichero público lo hace el bot.

El jugador ya no necesita token de GitHub, ni ser colaborador, ni cifrar en
el navegador, ni conocer la frase: solo enviar un email con su extracto.

Como es *el bot* quien decide en qué carpeta escribe (según el remitente
verificado), un jugador no puede tocar la carpeta de otro por construcción.
"""

from __future__ import annotations

import email
import imaplib
import json
import os
import re
from dataclasses import dataclass, field
from email.message import Message
from email.utils import parseaddr

from . import revolut, secretbox

# Cabecera que estampa el servidor receptor con el veredicto de autenticación.
def _env(name: str) -> str | None:
    """Valor de una variable de entorno, tratando la cadena vacía como ausente
    (GitHub Actions inyecta los secrets/variables sin definir como ``""``)."""
    value = os.environ.get(name)
    return value if value else None


_AUTH_HEADER = "Authentication-Results"
_METHOD_RE = re.compile(r"\b(dmarc|dkim|spf)\s*=\s*(\w+)", re.IGNORECASE)
_HEADER_D_RE = re.compile(r"header\.(?:d|i|from)\s*=\s*@?([^\s;()]+)", re.IGNORECASE)


@dataclass
class PlayerCfg:
    """Configuración de un jugador tomada de la Variable ``PLAYER_EMAILS``."""

    player_id: str
    email: str
    name: str
    currency: str = "USD"
    show_amounts: bool = False


@dataclass
class Result:
    """Resultado de procesar un mensaje."""

    status: str            # ingested | unauthorized | auth_failed | no_csv | invalid_csv
    player_id: str | None = None
    detail: str = ""

    @property
    def ingested(self) -> bool:
        return self.status == "ingested"


@dataclass
class RunSummary:
    ingested: list[str] = field(default_factory=list)   # ids actualizados
    skipped: list[Result] = field(default_factory=list)  # con motivo


def parse_player_emails(raw: str | None) -> dict[str, PlayerCfg]:
    """Parsea ``PLAYER_EMAILS`` a un mapa ``email (minúsculas) -> PlayerCfg``.

    Formato esperado (JSON)::

        {
          "fede": {"email": "fede@icloud.com", "name": "Fede 🚀",
                   "currency": "USD", "show_amounts": false},
          "ana":  {"email": "ana@gmail.com", "name": "Ana", "currency": "EUR"}
        }
    """
    if not raw or not raw.strip():
        return {}
    data = json.loads(raw)
    out: dict[str, PlayerCfg] = {}
    for player_id, cfg in data.items():
        if isinstance(cfg, str):  # forma corta: id -> email
            cfg = {"email": cfg}
        address = str(cfg.get("email", "")).strip().lower()
        if not address:
            continue
        out[address] = PlayerCfg(
            player_id=player_id,
            email=address,
            name=str(cfg.get("name", player_id)),
            currency=str(cfg.get("currency", "USD")),
            show_amounts=bool(cfg.get("show_amounts", False)),
        )
    return out


def _domains_aligned(a: str, b: str) -> bool:
    """¿Dominios alineados a nivel organizativo? (uno es sufijo del otro)."""
    a, b = a.strip(".").lower(), b.strip(".").lower()
    if not a or not b:
        return False
    if a == b:
        return True
    return a.endswith("." + b) or b.endswith("." + a)


def verify_sender_auth(msg: Message, from_domain: str,
                       trusted_authserv: str | None = None) -> tuple[bool, str]:
    """¿El mensaje pasa la autenticación del dominio del remitente?

    Solo se mira la cabecera ``Authentication-Results`` **más reciente** (la
    que añade el último salto, es decir, nuestro propio servidor receptor):
    va siempre arriba del todo, por encima de cualquier cabecera falsificada
    que el atacante hubiera incluido en el mensaje original. Se exige
    ``dmarc=pass`` (que ya garantiza alineación), o en su defecto un
    ``dkim=pass`` cuyo dominio firmante esté alineado con el ``From:``.
    """
    headers = msg.get_all(_AUTH_HEADER)
    if not headers:
        return False, "sin cabecera Authentication-Results (no verificable)"
    top = str(headers[0])

    if trusted_authserv:
        authserv_id = top.split(";", 1)[0].strip().split()[0] if top.strip() else ""
        if not _domains_aligned(authserv_id, trusted_authserv):
            return False, f"authserv-id inesperado '{authserv_id}'"

    results = {m.group(1).lower(): m.group(2).lower() for m in _METHOD_RE.finditer(top)}
    if results.get("dmarc") == "pass":
        return True, "dmarc=pass"
    if results.get("dkim") == "pass":
        for m in _HEADER_D_RE.finditer(top):
            if _domains_aligned(m.group(1), from_domain):
                return True, f"dkim=pass alineado ({m.group(1)})"
        return False, "dkim=pass pero no alineado con el remitente"
    got = ", ".join(f"{k}={v}" for k, v in results.items()) or "sin veredictos"
    return False, f"no pasa DMARC/DKIM ({got})"


def extract_csv_attachment(msg: Message) -> bytes | None:
    """Devuelve el primer adjunto que parezca un CSV, o ``None``."""
    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue
        filename = part.get_filename() or ""
        ctype = (part.get_content_type() or "").lower()
        is_csv = filename.lower().endswith(".csv") or ctype in (
            "text/csv", "application/csv", "application/vnd.ms-excel")
        if not is_csv:
            continue
        payload = part.get_payload(decode=True)
        if payload:
            return payload
    return None


def _decode_csv(payload: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    return payload.decode("utf-8", errors="replace")


def write_extract(cfg: PlayerCfg, csv_text: str, passphrase: str,
                  players_dir: str) -> None:
    """Cifra el CSV y lo escribe en ``players/<id>/``; crea ``player.json``
    solo si no existe (para no pisar ajustes que el jugador ya tuviera)."""
    pdir = os.path.join(players_dir, cfg.player_id)
    os.makedirs(pdir, exist_ok=True)

    config_path = os.path.join(pdir, "player.json")
    if not os.path.exists(config_path):
        with open(config_path, "w", encoding="utf-8") as fh:
            json.dump({
                "display_name": cfg.name,
                "currency": cfg.currency,
                "show_amounts": cfg.show_amounts,
            }, fh, ensure_ascii=False, indent=2)
            fh.write("\n")

    blob = secretbox.encrypt(csv_text.encode("utf-8"), passphrase)
    with open(os.path.join(pdir, "trades.csv.enc"), "wb") as fh:
        fh.write(blob)


def process_message(msg: Message, emails: dict[str, PlayerCfg], passphrase: str,
                    players_dir: str, trusted_authserv: str | None = None) -> Result:
    """Verifica, valida e ingesta un mensaje. No hace I/O de IMAP."""
    sender = parseaddr(msg.get("From", ""))[1].strip().lower()
    if not sender:
        return Result("unauthorized", detail="sin remitente")
    cfg = emails.get(sender)
    if cfg is None:
        return Result("unauthorized", detail=f"remitente no registrado: {sender}")

    from_domain = sender.split("@", 1)[1] if "@" in sender else ""
    ok, why = verify_sender_auth(msg, from_domain, trusted_authserv)
    if not ok:
        return Result("auth_failed", cfg.player_id, f"{sender}: {why}")

    payload = extract_csv_attachment(msg)
    if payload is None:
        return Result("no_csv", cfg.player_id, f"{sender}: sin adjunto CSV")

    csv_text = _decode_csv(payload)
    events, _ = revolut.parse_csv(csv_text)
    if not events:
        return Result("invalid_csv", cfg.player_id,
                      f"{sender}: el CSV no tiene operaciones reconocibles")

    write_extract(cfg, csv_text, passphrase, players_dir)
    return Result("ingested", cfg.player_id,
                  f"{sender}: {len(events)} operaciones, cifrado en players/{cfg.player_id}/")


def run(passphrase: str, players_dir: str = "players", *, dry_run: bool = False,
        host: str | None = None, port: int = 993, user: str | None = None,
        password: str | None = None, mailbox: str = "INBOX",
        emails_raw: str | None = None,
        trusted_authserv: str | None = None) -> RunSummary:
    """Lee el buzón IMAP y procesa los correos no vistos.

    Los parámetros de conexión se toman de los argumentos o del entorno
    (``IMAP_HOST``, ``IMAP_PORT``, ``IMAP_USER``, ``IMAP_PASS``,
    ``IMAP_MAILBOX``, ``INBOX_TRUSTED_AUTHSERV``) y el mapa de jugadores de
    ``PLAYER_EMAILS``. Si falta configuración esencial, no hace nada (para que
    el CI sin secrets no falle).
    """
    # En GitHub Actions, un secret/variable no definido llega como cadena
    # vacía (no ausente), así que hay que tratar "" como "no configurado".
    host = host or _env("IMAP_HOST") or "imap.gmail.com"
    user = user or _env("IMAP_USER")
    password = password or _env("IMAP_PASS")
    port = int(_env("IMAP_PORT") or port)
    mailbox = _env("IMAP_MAILBOX") or mailbox
    trusted_authserv = trusted_authserv or _env("INBOX_TRUSTED_AUTHSERV")
    emails = parse_player_emails(emails_raw if emails_raw is not None
                                 else os.environ.get("PLAYER_EMAILS"))

    summary = RunSummary()
    if not (user and password):
        print("inbox: faltan credenciales IMAP (IMAP_USER/IMAP_PASS); no hago nada.")
        return summary
    if not emails:
        print("inbox: PLAYER_EMAILS vacío; no hay remitentes autorizados.")
        return summary

    conn = imaplib.IMAP4_SSL(host, port)
    try:
        conn.login(user, password)
        conn.select(mailbox)
        typ, data = conn.search(None, "UNSEEN")
        if typ != "OK":
            print(f"inbox: búsqueda IMAP fallida: {typ}")
            return summary
        msg_ids = data[0].split()
        print(f"inbox: {len(msg_ids)} correo(s) nuevo(s) en {mailbox}.")

        for num in msg_ids:
            typ, raw = conn.fetch(num, "(BODY.PEEK[])")
            if typ != "OK" or not raw or not raw[0]:
                continue
            msg = email.message_from_bytes(raw[0][1])
            result = process_message(msg, emails, passphrase, players_dir,
                                     trusted_authserv)
            if result.ingested:
                summary.ingested.append(result.player_id)
                print(f"  ✅ {result.detail}")
            else:
                summary.skipped.append(result)
                print(f"  ⚠️  [{result.status}] {result.detail}")
            # Marcar como visto para no reprocesarlo (salvo simulacro).
            if not dry_run:
                conn.store(num, "+FLAGS", "\\Seen")
    finally:
        try:
            conn.close()
        except Exception:
            pass
        conn.logout()

    return summary
