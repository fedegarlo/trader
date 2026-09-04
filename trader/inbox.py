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
   JSON ``id -> {email|emails, name, currency, show_amounts, goal, show_goal}``;
   un jugador puede tener varias direcciones).
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

Hay un camino paralelo **sin IMAP** (:func:`ingest_csv`) para ingerir un CSV
ya en mano —misma validación, fusión y cifrado—. Lo usa la CLI
``python -m trader ingest-csv`` y el workflow ``ingest-csv.yml`` (p.ej. la
rutina automática de Steve de Federico).
"""

from __future__ import annotations

import csv
import email
import imaplib
import io
import json
import os
import re
from dataclasses import dataclass, field
from datetime import date
from email.message import Message
from email.utils import parseaddr

from . import revolut, revolut_pdf, secretbox
from .players import DEFAULT_GOAL

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
    goal: float = DEFAULT_GOAL
    show_goal: bool = False


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

    # ingested | unchanged | unauthorized | auth_failed | no_report | invalid_report
    status: str
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
    unchanged: list[str] = field(default_factory=list)  # extracto válido sin novedades
    skipped: list[Result] = field(default_factory=list)  # con motivo


# Comillas dobles "de imprenta" que iOS y macOS ponen automáticamente al
# escribir `"`. Copiar el JSON de la documentación a la caja de texto de una
# Variable del repo desde el móvil basta para colar alguna: el JSON deja de ser
# válido y la ingesta se cae entera sin haber leído el buzón.
_SMART_DQUOTES = "“”„‟«»″"


def _loads_player_emails(raw: str) -> dict:
    """``json.loads`` tolerante con las comillas tipográficas del móvil.

    Primero se intenta el JSON tal cual: si es válido, se respeta al pie de la
    letra (un nombre puede llevar comillas tipográficas a propósito). Solo si
    falla se reintenta con las comillas dobles curvas convertidas en rectas,
    que es el error de copia habitual. Si sigue sin ser válido, el mensaje dice
    qué hay que arreglar y dónde, en vez de soltar un traceback de json.
    """
    try:
        return json.loads(raw)
    except json.JSONDecodeError as first_error:
        fixed = raw.translate({ord(q): '"' for q in _SMART_DQUOTES})
        if fixed != raw:
            try:
                data = json.loads(fixed)
            except json.JSONDecodeError:
                pass
            else:
                print("inbox: PLAYER_EMAILS traía comillas tipográficas "
                      "(“ ”); las he interpretado como comillas normales. "
                      "Conviene corregir la Variable del repositorio.")
                return data
        raise ValueError(
            f"PLAYER_EMAILS no es JSON válido ({first_error.msg}, línea "
            f"{first_error.lineno} columna {first_error.colno}). Revisa la "
            "Variable del repositorio: debe ser un objeto id -> datos con "
            'comillas rectas ("), p. ej. {"fede": {"email": "fede@mail.com"}}.'
        ) from first_error


def _collect_player_addresses(cfg: dict) -> list[str]:
    """Direcciones de un jugador: ``email`` y/o ``emails``, string o lista.

    Conserva el orden de aparición y elimina duplicados (sin distinguir
    mayúsculas). Las cadenas vacías se ignoran.
    """
    seen: set[str] = set()
    addresses: list[str] = []
    for key in ("email", "emails"):
        if key not in cfg:
            continue
        value = cfg[key]
        items = value if isinstance(value, list) else [value]
        for item in items:
            if item is None:
                continue
            address = str(item).strip().lower()
            if not address or address in seen:
                continue
            seen.add(address)
            addresses.append(address)
    return addresses


def parse_player_emails(raw: str | None) -> dict[str, PlayerCfg]:
    """Parsea ``PLAYER_EMAILS`` a un mapa ``email (minúsculas) -> PlayerCfg``.

    Cada jugador puede tener una o varias direcciones; todas apuntan al mismo
    ``player_id``. Se acepta ``"email"`` (string o lista), ``"emails"`` (lista
    o string), o las dos a la vez. Forma corta: ``id -> "correo"``.

    Formato esperado (JSON)::

        {
          "fede": {"emails": ["fgarcialorca@gmail.com", "fedegarcia@icloud.com"],
                   "name": "Fede", "currency": "USD", "show_amounts": true,
                   "goal": 14000, "show_goal": true},
          "ana":  {"email": "ana@gmail.com", "name": "Ana", "currency": "EUR"}
        }
    """
    if not raw or not raw.strip():
        return {}
    data = _loads_player_emails(raw)
    out: dict[str, PlayerCfg] = {}
    for player_id, cfg in data.items():
        if isinstance(cfg, str):  # forma corta: id -> email
            cfg = {"email": cfg}
        addresses = _collect_player_addresses(cfg)
        if not addresses:
            continue
        player = PlayerCfg(
            player_id=player_id,
            email=addresses[0],
            name=str(cfg.get("name", player_id)),
            currency=str(cfg.get("currency", "USD")),
            show_amounts=bool(cfg.get("show_amounts", False)),
            goal=float(cfg.get("goal") or DEFAULT_GOAL),
            show_goal=bool(cfg.get("show_goal", False)),
        )
        for address in addresses:
            out[address] = player
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


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


@dataclass
class MergeStats:
    """Qué ha aportado el extracto recibido frente al que ya estaba guardado."""

    total: int = 0      # operaciones del extracto recibido
    new: int = 0        # de esas, las que no estaban ya registradas
    kept: int = 0       # operaciones anteriores conservadas (fuera de su periodo)
    covers: tuple[date, date] | None = None  # periodo que cubre el extracto

    @property
    def period(self) -> str:
        if not self.covers:
            return "sin fechas"
        lo, hi = self.covers
        return lo.isoformat() if lo == hi else f"{lo.isoformat()}…{hi.isoformat()}"


def _rows_with_dates(text: str) -> tuple[list[str], list[tuple[date | None, dict]]]:
    """(campos, [(fecha, fila)]) del CSV, conservando las filas tal cual.

    La fecha se obtiene con el mismo criterio que el parser (:mod:`revolut`);
    las filas sin fecha reconocible salen con ``None``.
    """
    reader = csv.DictReader(io.StringIO(text or ""))
    if not reader.fieldnames:
        return [], []
    fields = {name.strip().lower(): name for name in reader.fieldnames}
    out: list[tuple[date | None, dict]] = []
    for row in reader:
        raw = row.get(fields.get("date", ""), "") or ""
        try:
            day = revolut._parse_date(raw)
        except ValueError:
            day = None
        out.append((day, row))
    return list(reader.fieldnames), out


def _signatures(text: str) -> dict[tuple, int]:
    """Recuento de operaciones por «firma» (día, tipo, ticker, cantidad, importe).

    Sirve para contar cuántas operaciones del extracto recibido son realmente
    nuevas, sin depender del formato exacto de la fila.
    """
    counts: dict[tuple, int] = {}
    events, _ = revolut.parse_csv(text or "")
    for ev in events:
        key = (ev.day, ev.kind, ev.ticker, round(ev.quantity, 6), round(ev.total, 2))
        counts[key] = counts.get(key, 0) + 1
    return counts


def merge_statements(old_csv: str | None, new_csv: str) -> tuple[str, MergeStats]:
    """Combina el extracto guardado con el recién recibido.

    El extracto nuevo **manda en el periodo que cubre** (de su primera a su
    última operación): esas filas sustituyen a las guardadas, así que corregir
    o reenviar un extracto sigue funcionando. Fuera de ese periodo se conservan
    las operaciones que ya había, de modo que un extracto **parcial** (solo el
    mes en curso) o **antiguo** (exportado antes de las últimas operaciones)
    nunca borra lo ya registrado.

    Si no hay nada que conservar se devuelve el CSV recibido tal cual, sin
    reformatear: lo normal es que el extracto sea el histórico completo.
    """
    new_fields, new_rows = _rows_with_dates(new_csv)
    dated = [d for d, _row in new_rows if d is not None]
    stats = MergeStats(total=sum(_signatures(new_csv).values()),
                       covers=(min(dated), max(dated)) if dated else None)

    old_counts = _signatures(old_csv or "")
    new_counts = _signatures(new_csv)
    stats.new = sum(max(0, n - old_counts.get(key, 0))
                    for key, n in new_counts.items())

    if not dated or not old_csv:
        return new_csv, stats

    lo, hi = stats.covers
    old_fields, old_rows = _rows_with_dates(old_csv)
    keep = [(d, row) for d, row in old_rows if d is not None and (d < lo or d > hi)]
    stats.kept = len(keep)
    if not keep:
        return new_csv, stats

    fields = list(new_fields)
    fields += [name for name in old_fields if name not in fields]
    rows = sorted(keep + [(d, row) for d, row in new_rows if d is not None],
                  key=lambda item: item[0])
    rows += [(None, row) for d, row in new_rows if d is None]

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore",
                            lineterminator="\n")
    writer.writeheader()
    for _day, row in rows:
        writer.writerow({name: row.get(name, "") for name in fields})
    return buf.getvalue(), stats


def write_extract(cfg: PlayerCfg, csv_text: str, passphrase: str,
                  players_dir: str) -> tuple[bool, MergeStats]:
    """Guarda el extracto en ``players/<id>/`` y dice si ha cambiado algo.

    El CSV recibido se **fusiona** con el que ya hubiera (:func:`merge_statements`)
    y solo se reescribe el fichero cifrado si el resultado es distinto del
    guardado: cifrar dos veces el mismo CSV da bytes distintos (la sal es
    aleatoria), y eso hacía que un extracto sin novedades pareciese una ingesta
    con datos nuevos. ``player.json`` se crea solo si no existe, para no pisar
    ajustes que el jugador ya tuviera.
    """
    pdir = os.path.join(players_dir, cfg.player_id)
    os.makedirs(pdir, exist_ok=True)

    config_path = os.path.join(pdir, "player.json")
    if not os.path.exists(config_path):
        with open(config_path, "w", encoding="utf-8") as fh:
            json.dump({
                "display_name": cfg.name,
                "currency": cfg.currency,
                "show_amounts": cfg.show_amounts,
                "goal": cfg.goal,
                "show_goal": cfg.show_goal,
            }, fh, ensure_ascii=False, indent=2)
            fh.write("\n")

    path = os.path.join(pdir, "trades.csv.enc")
    stored: str | None = None
    if os.path.exists(path):
        try:
            stored = secretbox.decrypt_file(path, passphrase).decode("utf-8-sig")
        except (secretbox.DecryptError, UnicodeDecodeError):
            stored = None  # no se puede leer lo anterior: manda el nuevo

    merged, stats = merge_statements(stored, csv_text)
    # Se compara por operaciones, no por texto: un cambio de formato del export
    # (columnas nuevas, comillas distintas) no es un dato nuevo y no merece ni
    # reescritura ni commit.
    if stored is not None and _signatures(merged) == _signatures(stored):
        return False, stats

    with open(path, "wb") as fh:
        fh.write(secretbox.encrypt(merged.encode("utf-8"), passphrase))
    return True, stats


# Id de jugador = nombre de carpeta en players/<id>/. Nada de barras ni
# puntos: el CSV directo no pasa por el mapa de remitentes del buzón.
_PLAYER_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def player_cfg_for(player_id: str, players_dir: str = "players",
                   emails_raw: str | None = None) -> PlayerCfg:
    """Arma un ``PlayerCfg`` para la ingesta directa (sin email).

    Toma los datos de ``PLAYER_EMAILS`` (el mismo JSON que el buzón) y, si ya
    existe ``players/<id>/player.json``, esos campos mandan: así no se pisan
    los ajustes que el jugador ya tenía (``write_extract`` tampoco los
    reescribe).
    """
    emails_raw = emails_raw if emails_raw is not None else os.environ.get("PLAYER_EMAILS")
    from_emails: PlayerCfg | None = None
    for cfg in parse_player_emails(emails_raw).values():
        if cfg.player_id == player_id:
            from_emails = cfg
            break

    config: dict = {}
    config_path = os.path.join(players_dir, player_id, "player.json")
    if os.path.isfile(config_path):
        with open(config_path, encoding="utf-8") as fh:
            config = json.load(fh) or {}

    def _pick(file_key: str, attr: str, default):
        if file_key in config and config[file_key] is not None:
            return config[file_key]
        if from_emails is not None:
            return getattr(from_emails, attr)
        return default

    name = str(_pick("display_name", "name", player_id) or player_id)
    currency = str(_pick("currency", "currency", "USD") or "USD")
    show_amounts = bool(_pick("show_amounts", "show_amounts", False))
    goal = float(_pick("goal", "goal", DEFAULT_GOAL) or DEFAULT_GOAL)
    show_goal = bool(_pick("show_goal", "show_goal", False))
    email = from_emails.email if from_emails else ""
    return PlayerCfg(
        player_id=player_id,
        email=email,
        name=name,
        currency=currency,
        show_amounts=show_amounts,
        goal=goal,
        show_goal=show_goal,
    )


def ingest_csv(player_id: str, csv_text: str, passphrase: str,
               players_dir: str = "players",
               emails_raw: str | None = None) -> Result:
    """Ingesta un extracto CSV sin pasar por IMAP.

    Misma validación, fusión y cifrado que :func:`process_message`:
    ``revolut.parse_csv`` + :func:`write_extract`. No toca el buzón.
    """
    if not _PLAYER_ID_RE.fullmatch(player_id or ""):
        return Result("unauthorized", detail=f"player_id inválido: {player_id!r}")

    cfg = player_cfg_for(player_id, players_dir, emails_raw)
    events, warnings = revolut.parse_csv(csv_text or "")
    if not events:
        return Result("invalid_report", player_id,
                      "el extracto CSV no tiene operaciones reconocibles",
                      warnings)

    changed, stats = write_extract(cfg, csv_text, passphrase, players_dir)
    detail = (f"{_plural(stats.total, 'operación', 'operaciones')} "
              f"(CSV, {stats.period}), "
              f"{_plural(stats.new, 'nueva', 'nuevas')}")
    if stats.kept:
        detail += (", " + _plural(stats.kept, "anterior conservada",
                                  "anteriores conservadas") + " fuera de ese periodo")
    if not changed:
        return Result("unchanged", player_id,
                      detail + "; el extracto no aporta nada que no estuviera ya "
                      "registrado", warnings)
    return Result("ingested", player_id,
                  detail + f"; cifrado en players/{player_id}/", warnings)


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

    events, parse_warnings = revolut.parse_csv(csv_text)
    # Las filas que el parser no entiende se avisaban solo en el ranking; aquí
    # también, que es donde se ve si un extracto ha entrado entero o a medias.
    warnings += parse_warnings
    if not events:
        return Result("invalid_report", cfg.player_id,
                      f"{sender}: el extracto {kind.upper()} no tiene operaciones "
                      "reconocibles", warnings)

    changed, stats = write_extract(cfg, csv_text, passphrase, players_dir)
    detail = (f"{sender}: {_plural(stats.total, 'operación', 'operaciones')} "
              f"({kind.upper()}, {stats.period}), "
              f"{_plural(stats.new, 'nueva', 'nuevas')}")
    if stats.kept:
        detail += (", " + _plural(stats.kept, "anterior conservada",
                                  "anteriores conservadas") + " fuera de ese periodo")
    if not changed:
        return Result("unchanged", cfg.player_id,
                      detail + "; el extracto no aporta nada que no estuviera ya "
                      "registrado", warnings)
    return Result("ingested", cfg.player_id,
                  detail + f"; cifrado en players/{cfg.player_id}/", warnings)


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
            elif result.status == "unchanged":
                # El correo era válido, pero el extracto no traía nada nuevo
                # (típico: se exporta antes de que Revolut refleje el día). No
                # se reescribe nada, para que un commit signifique datos nuevos.
                summary.unchanged.append(result.player_id)
                print(f"  ℹ️  {result.detail}")
            else:
                summary.skipped.append(result)
                print(f"  ⚠️  [{result.status}] {result.detail}")
            for warning in result.warnings:
                print(f"     ⚠️  {warning}")
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
