"""Ingesta de extractos por email (IMAP), sin token de GitHub por jugador.

Idea: cada jugador **envía su extracto como adjunto a un buzón** de la liga,
en cualquiera de los dos formatos de Revolut: el CSV que exporta la app o el
PDF de cuenta ("Account Statement"). Un workflow programado ejecuta este
módulo, que:

1. Se conecta al buzón por IMAP y lee los correos no vistos.
2. **Verifica el remitente por DMARC** (no por el ``From:`` a secas, que es
   falsificable): mira la cabecera ``Authentication-Results`` que estampa el
   propio servidor receptor y exige ``dmarc=pass`` (o un ``dkim=pass``
   alineado con el dominio del remitente). Así, quien controla la dirección
   de correo es quien puede subir en su nombre — una frontera de seguridad
   equivalente a "tienes un token de GitHub".
3. Mapea el remitente a un jugador con ``PLAYER_EMAILS`` (Variable del repo,
   JSON ``id -> {email, name, currency, show_amounts}``).
4. Valida que el adjunto es un extracto de Revolut legible; si viene en PDF,
   lo convierte antes al CSV de la app (:mod:`trader.revolut_pdf`).
5. **Cifra el CSV con la frase de la liga** (``TRADER_KEY``) y lo escribe en
   ``players/<id>/trades.csv.enc``. El jugador manda el extracto en claro a
   un buzón privado; el cifrado del fichero público lo hace el bot.

El jugador ya no necesita token de GitHub, ni ser colaborador, ni cifrar en
el navegador, ni conocer la frase: solo enviar un email con su extracto.

Como es *el bot* quien decide en qué carpeta escribe (según el remitente
verificado), un jugador no puede tocar la carpeta de otro por construcción.

Los correos procesados se marcan como leídos para no reprocesarlos, **salvo
los que no traen el informe esperado** (sin adjunto o con un fichero que no es
un extracto legible): esos se dejan sin leer, de modo que sigan a la vista en
el buzón y se reintenten en cuanto llegue el fichero correcto.
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

from . import revolut, revolut_pdf, secretbox

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


# Estados en los que el correo viene de un jugador legítimo pero **no trae el
# informe esperado** (falta el adjunto o no es un extracto legible). En esos
# casos dejamos el correo sin leer: así sigue visible en el buzón, el jugador
# ve que su envío no ha entrado y basta con responder con el fichero correcto
# para que la siguiente pasada lo ingiera. Los correos rechazados por
# remitente/autenticación sí se marcan como leídos, para no acumular ruido de
# spam que se reprocesaría en cada ejecución.
_KEEP_UNREAD_STATUSES = frozenset({"no_report", "invalid_report"})


@dataclass
class Result:
    """Resultado de procesar un mensaje."""

    status: str            # ingested | unauthorized | auth_failed | no_report | invalid_report
    player_id: str | None = None
    detail: str = ""
    warnings: list[str] = field(default_factory=list)

    @property
    def ingested(self) -> bool:
        return self.status == "ingested"

    @property
    def keep_unread(self) -> bool:
        """¿Hay que dejar el correo sin leer para que se pueda reintentar?"""
        return self.status in _KEEP_UNREAD_STATUSES


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


def extract_statement_attachment(msg: Message) -> tuple[bytes, str] | None:
    """Primer adjunto que parezca un extracto: ``(contenido, "csv"|"pdf")``.

    Se aceptan las dos formas en que Revolut entrega el extracto: el CSV que
    exporta la app y el PDF de cuenta ("Account Statement") que manda por
    correo. Si vienen los dos, gana el CSV (es el formato nativo). Devuelve
    ``None`` si el correo no trae ninguno.
    """
    found: dict[str, bytes] = {}
    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue
        filename = (part.get_filename() or "").lower()
        ctype = (part.get_content_type() or "").lower()
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        if filename.endswith(".csv") or ctype in (
                "text/csv", "application/csv", "application/vnd.ms-excel"):
            kind = "csv"
        elif filename.endswith(".pdf") or ctype == "application/pdf" \
                or revolut_pdf.looks_like_pdf(payload):
            # Algunos clientes mandan el PDF como octet-stream: la firma del
            # fichero ('%PDF') lo identifica igual.
            kind = "pdf"
        else:
            continue
        found.setdefault(kind, payload)

    for kind in ("csv", "pdf"):
        if kind in found:
            return found[kind], kind
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

    attachment = extract_statement_attachment(msg)
    if attachment is None:
        return Result("no_report", cfg.player_id, f"{sender}: sin adjunto CSV ni PDF")

    payload, kind = attachment
    warnings: list[str] = []
    if kind == "pdf":
        # El PDF se convierte al CSV de la app: lo que se guarda cifrado es
        # siempre un CSV, así que el resto del sistema no se entera.
        try:
            csv_text, warnings = revolut_pdf.pdf_to_csv(payload)
        except revolut_pdf.PdfError as exc:
            return Result("invalid_report", cfg.player_id, f"{sender}: {exc}")
    else:
        csv_text = _decode_csv(payload)

    events, _ = revolut.parse_csv(csv_text)
    if not events:
        return Result("invalid_report", cfg.player_id,
                      f"{sender}: el extracto {kind.upper()} no tiene operaciones "
                      "reconocibles")

    write_extract(cfg, csv_text, passphrase, players_dir)
    return Result("ingested", cfg.player_id,
                  f"{sender}: {len(events)} operaciones ({kind.upper()}), cifrado "
                  f"en players/{cfg.player_id}/", warnings)


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
                for warning in result.warnings:
                    print(f"     ⚠️  {warning}")
            else:
                summary.skipped.append(result)
                print(f"  ⚠️  [{result.status}] {result.detail}")
            # Marcar como visto para no reprocesarlo (salvo simulacro). Si el
            # correo no traía el informe esperado, lo dejamos sin leer para que
            # siga a la vista y se pueda reintentar con el fichero correcto.
            if dry_run:
                continue
            if result.keep_unread:
                print("     ↩️  se deja sin leer (falta el informe esperado)")
                continue
            conn.store(num, "+FLAGS", "\\Seen")
    finally:
        try:
            conn.close()
        except Exception:
            pass
        conn.logout()

    return summary
