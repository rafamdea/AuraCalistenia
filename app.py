from __future__ import annotations

import base64
import hashlib
import html
import json
import os
import re
import secrets
import shutil
import smtplib
import threading
import time
import urllib.parse
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from email.parser import BytesParser
from email.policy import default
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

try:
    import psycopg
except Exception:  # pragma: no cover - optional dependency until DATABASE_URL is used
    psycopg = None

try:
    import psycopg2
except Exception:  # pragma: no cover - compatibility fallback
    psycopg2 = None

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("AURA_DATA_DIR", str(BASE_DIR / "data")))
UPLOAD_DIR = Path(os.environ.get("AURA_UPLOAD_DIR", str(BASE_DIR / "uploads")))
INDEX_TEMPLATE = BASE_DIR / "index.html"
ADMIN_TEMPLATE = BASE_DIR / "admin.html"
PORTAL_TEMPLATE = BASE_DIR / "portal.html"

EVENTS_PATH = DATA_DIR / "events.json"
VIDEOS_PATH = DATA_DIR / "videos.json"
APPLICATIONS_PATH = DATA_DIR / "applications.json"
SUBMISSIONS_PATH = DATA_DIR / "submissions.json"
CHATS_PATH = DATA_DIR / "chats.json"
SESSIONS_PATH = DATA_DIR / "sessions.json"
SETTINGS_PATH = DATA_DIR / "settings.json"
CONTENT_PATH = DATA_DIR / "content.json"
PASSWORD_RESETS_PATH = DATA_DIR / "password_resets.json"

DATA_LOCK = threading.Lock()
ADMIN_SESSION_COOKIE = "aura_admin_session"
USER_SESSION_COOKIE = "aura_user_session"
SESSION_TTL = 12 * 60 * 60
RESET_TOKEN_TTL = 60 * 60
MAX_UPLOAD_BYTES = 50 * 1024 * 1024

ALLOWED_VIDEO_EXT = {".mp4", ".webm", ".ogg", ".mov"}
ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}


def normalize_database_url(raw_value: str) -> str:
    value = str(raw_value or "").strip()
    if not value:
        return ""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1].strip()
    lowered = value.lower()
    if lowered.startswith("psql "):
        match = re.search(r"(postgres(?:ql)?://[^\s'\"]+)", value)
        if match:
            value = match.group(1).strip()
    return value


def resolve_database_url() -> tuple[str, str]:
    candidates = [
        "DATABASE_URL",
        "AURA_DATABASE_URL",
        "NEON_DATABASE_URL",
        "POSTGRES_URL",
        "POSTGRESQL_URL",
    ]
    for key in candidates:
        cleaned = normalize_database_url(os.environ.get(key, ""))
        if cleaned:
            return cleaned, key
    return "", ""


DATABASE_URL, DATABASE_URL_SOURCE = resolve_database_url()
DB_TABLE = os.environ.get("AURA_DB_TABLE", "aura_state").strip() or "aura_state"
if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", DB_TABLE):
    DB_TABLE = "aura_state"
DAY_LABELS = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
DB_LAST_ERROR = ""
SMTP_LAST_ERROR = ""


@dataclass
class UploadedFile:
    filename: str
    file: BytesIO

PLACEHOLDER_SVG = """
<svg viewBox=\"0 0 320 220\" role=\"img\" aria-label=\"Video placeholder\">
  <rect width=\"320\" height=\"220\" fill=\"#0b1f17\" rx=\"20\"/>
  <polygon points=\"130,80 230,110 130,140\" fill=\"#48eaa9\"/>
  <rect x=\"20\" y=\"20\" width=\"280\" height=\"180\" fill=\"none\" stroke=\"#48eaa9\" stroke-width=\"2\" opacity=\"0.6\"/>
</svg>
""".strip()

DEFAULT_EVENTS = [
    {
        "id": "evt_1",
        "date": "16-19 ABR 2026",
        "location": "Colonia, Alemania",
        "title": "Calisthenics Cup 2026",
        "description": "FIBO Fitness Convention.",
        "tag": "Europa",
    },
    {
        "id": "evt_2",
        "date": "MAR/ABR 2026",
        "location": "Malaga, Espana",
        "title": "Copa Malaga",
        "description": "Fecha prevista entre marzo y abril.",
        "tag": "Nacional",
    },
    {
        "id": "evt_3",
        "date": "14-15 MAR 2026",
        "location": "O Porto, Portugal",
        "title": "Endurance Battles",
        "description": "Eagle Calisthenics.",
        "tag": "Europa",
    },
]

DEFAULT_VIDEOS = [
    {
        "id": "vid_1",
        "tag": "Dominadas",
        "title": "Disciplina en la barra",
        "description": "Serie limpia con foco militar.",
        "layout": "tall",
        "video_url": "FOTOS/dominadas.mp4",
        "file": "",
    },
    {
        "id": "vid_2",
        "tag": "Muscle up",
        "title": "Transición precisa",
        "description": "Explosivo y controlado.",
        "layout": "wide",
        "video_url": "FOTOS/muscle-up.mp4",
        "file": "",
    },
    {
        "id": "vid_3",
        "tag": "Pino",
        "title": "Línea en silencio",
        "description": "Balance y respiración.",
        "layout": "",
        "video_url": "FOTOS/pino-video.mp4",
        "file": "",
    },
    {
        "id": "vid_4",
        "tag": "Front lever",
        "title": "Horizonte quieto",
        "description": "Control total en estáticos.",
        "layout": "tall",
        "video_url": "FOTOS/front-lever.mp4",
        "file": "",
    },
    {
        "id": "vid_5",
        "tag": "Fondos",
        "title": "Fondo profundo",
        "description": "Ritmo de resistencia brutal.",
        "layout": "wide",
        "video_url": "FOTOS/fondos.mp4",
        "file": "",
    },
    {
        "id": "vid_6",
        "tag": "Back lever",
        "title": "Reversa total",
        "description": "Control posterior con aura.",
        "layout": "",
        "video_url": "FOTOS/back-lever.mp4",
        "file": "",
    },
]

DEFAULT_TRAINING_PLAN = {
    "title": "Plan 4 semanas - primera dominada",
    "weeks": [
        {
            "title": "Semana 01 - Base y técnica",
            "days": [
                "Dead hang 4x20s + retracción escapular 3x10",
                "Remo invertido 4x8 + hollow hold 3x20s",
                "Asistidas con banda 5x5 + negativas 3x3 (5s)",
                "Movilidad de hombro y core 15 min",
                "Isométricos arriba 4x10s + asistidas 4x6",
                "Remo anillas 4x8 + curl bíceps 3x12",
                "Descanso activo, caminar 20-30 min",
            ],
        },
        {
            "title": "Semana 02 - Fuerza inicial",
            "days": [
                "Dead hang 4x30s + retracción escapular 4x10",
                "Remo invertido 4x10 + plancha hollow 3x25s",
                "Asistidas banda ligera 5x4 + negativas 4x3",
                "Movilidad y activación de escápulas 15 min",
                "Isométricos mitad recorrido 4x8s + asistidas 4x5",
                "Remo supino 4x8 + curl bíceps 3x10",
                "Descanso activo",
            ],
        },
        {
            "title": "Semana 03 - Control y potencia",
            "days": [
                "Asistidas 6x3 + negativas 4x3 (6s)",
                "Remo pesado 4x6 + hollow rocks 3x15",
                "Isométricos arriba 5x8s + clusters 1-1-1",
                "Movilidad y compensación de hombro",
                "Asistidas mínima ayuda 5x3 + negativas 3x2",
                "Remo anillas 4x6 + face pulls 3x12",
                "Descanso",
            ],
        },
        {
            "title": "Semana 04 - Primer intento",
            "days": [
                "Test dominada + singles limpios 5x1",
                "Remo moderado 3x8 + core 3x20s",
                "Singles con pausa arriba 4x1 + negativas 2x2",
                "Movilidad y respiración",
                "Intentos controlados + series técnicas",
                "Trabajo ligero y estiramientos",
                "Descanso total",
            ],
        },
    ],
}

SPONSOR_PULLUP_URL = "https://pullup-dip.com/?ref=pullup-dip.com%3Fref%3Drafamdea&utm_source=influenzer"
SPONSOR_ZUMUB_URL = "https://www.zumub.com/ES/"

DEFAULT_CONTENT = {
    "hero": {
        "eyebrow": "Entrenamiento gratuito · 4 semanas",
        "title": "Calistenia con aura épica",
        "subtitle": (
            "Plan gratuito de 4 semanas para dominar dominadas, muscle up y pino con disciplina real."
        ),
    },
    "stats": [
        {"value": "4", "label": "Semanas intensas"},
        {"value": "7", "label": "Habilidades clave"},
        {"value": "GRATIS!", "label": "0€ costo de entrada"},
    ],
    "bio": {
        "eyebrow": "Biografía",
        "name": "Rafa Montero de Espinosa",
        "paragraphs": [
            (
                "Teniente de Navío, 27 años. En marzo de 2024 cambié el running por la "
                "calistenia desde cero: no podía hacer ni una dominada ni un fondo. En abril "
                "empecé con entrenador personal y un plan de fuerza base, templando disciplina "
                "militar y obsesión por la técnica."
            ),
            (
                "En octubre de 2025 volví a parques, barras y suelo. En pocos meses "
                "desbloqueé pino, front lever y back lever, y elevé la resistencia. Debuté "
                "en Málaga el 19 de diciembre y hoy me preparo para competir en resistencia "
                "con la meta de estar entre los mejores. Mi sello es la disciplina: cero "
                "alcohol, cero tabaco y una vida dedicada a progresar cada día."
            ),
        ],
        "signature": "Teniente de Navío · Entrenador",
        "image": "FOTOS/bio-creador.jpg",
        "image_caption": "",
    },
    "program": {
        "title": "Evolución del pino libre",
        "lead": (
            "En este programa trabajamos los puntos débiles que desbloquean cada skill. "
            "Aquí tienes la evolución del pino libre con las 4 progresiones clave."
        ),
        "highlight_title": "Progresiones que desbloquean el equilibrio",
        "highlight_text": (
            "Cada fase ataca un punto crítico: fuerza de empuje, entrada al pino, "
            "potencia en flexión asistida y control total de la línea corporal."
        ),
        "bullets": [
            "Empuje vertical y fuerza de hombro.",
            "Entrada al pino con asistencia y control.",
            "Flexiones de pino asistidas para potencia.",
            "Tensión corporal y equilibrio estable con las manos.",
        ],
        "image": "FOTOS/pino.jpg",
        "image_caption": "Pino libre en acción",
    },
    "contact": {
        "email": "rafamdeeales@gmail.com",
        "phone": "+34 644 660 583",
        "city": "Sevilla, España",
        "instagram": "@rafamdea",
    },
    "sponsors": [
        {
            "name": "PULLUP&DIP",
            "logo": "LOGOS/pullupanddip.png",
            "url": SPONSOR_PULLUP_URL,
        },
        {
            "name": "ZUMUB",
            "logo": "LOGOS/zumub.png",
            "url": SPONSOR_ZUMUB_URL,
        },
    ],
}


def hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    if salt is None:
        salt = secrets.token_bytes(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return base64.b64encode(salt).decode("ascii"), base64.b64encode(hashed).decode("ascii")


def verify_password(password: str, salt_b64: str, hash_b64: str) -> bool:
    try:
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
    except (ValueError, TypeError):
        return False
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return secrets.compare_digest(hashed, expected)


def db_enabled() -> bool:
    return bool(DATABASE_URL)


def remember_db_error(exc: Exception) -> None:
    global DB_LAST_ERROR
    DB_LAST_ERROR = f"{type(exc).__name__}: {exc}"


def remember_smtp_error(exc: Exception) -> None:
    global SMTP_LAST_ERROR
    SMTP_LAST_ERROR = f"{type(exc).__name__}: {exc}"


def clear_smtp_error() -> None:
    global SMTP_LAST_ERROR
    SMTP_LAST_ERROR = ""


def db_connect():
    if not db_enabled():
        return None
    if psycopg is not None:
        return psycopg.connect(DATABASE_URL, autocommit=True, connect_timeout=5)
    if psycopg2 is not None:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=5)
        conn.autocommit = True
        return conn
    raise RuntimeError("DATABASE_URL está definido pero no hay driver PostgreSQL instalado (psycopg/psycopg2).")


def db_key_for_path(path: Path) -> str:
    return path.name


def get_storage_status() -> dict:
    if not db_enabled():
        return {
            "mode": "local",
            "title": "Modo temporal (JSON local)",
            "detail": "Este modo se borra al redeploy. Configura DATABASE_URL (o NEON_DATABASE_URL) en Render para guardar de forma persistente.",
        }
    try:
        with db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT count(*) FROM {DB_TABLE}")
                row = cur.fetchone()
        count = int(row[0]) if row else 0
        global DB_LAST_ERROR
        DB_LAST_ERROR = ""
        return {
            "mode": "db_ok",
            "title": "Neon conectado",
            "detail": f"Guardado persistente activo ({DATABASE_URL_SOURCE or 'DATABASE_URL'}). Registros: {count}.",
        }
    except Exception as exc:
        remember_db_error(exc)
        return {
            "mode": "db_error",
            "title": "Error conectando con Neon",
            "detail": f"No se puede usar {DATABASE_URL_SOURCE or 'DATABASE_URL'} ahora mismo. Se usa JSON local temporal.",
            "debug": f"{type(exc).__name__}: {exc}",
        }


def db_bootstrap() -> None:
    if not db_enabled():
        return
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {DB_TABLE} (
                  key TEXT PRIMARY KEY,
                  value JSONB NOT NULL,
                  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )


def db_has_key(path: Path) -> bool:
    key = db_key_for_path(path)
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT 1 FROM {DB_TABLE} WHERE key = %s LIMIT 1", (key,))
            row = cur.fetchone()
    return bool(row)


def db_load_json(path: Path, default):
    key = db_key_for_path(path)
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT value FROM {DB_TABLE} WHERE key = %s LIMIT 1", (key,))
            row = cur.fetchone()
    if not row:
        return default
    value = row[0]
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return value


def db_save_json(path: Path, data) -> None:
    key = db_key_for_path(path)
    payload = json.dumps(data, ensure_ascii=True)
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {DB_TABLE} (key, value, updated_at)
                VALUES (%s, %s::jsonb, NOW())
                ON CONFLICT (key)
                DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
                """,
                (key, payload),
            )


def db_seed_json(path: Path, data) -> None:
    key = db_key_for_path(path)
    payload = json.dumps(data, ensure_ascii=True)
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {DB_TABLE} (key, value, updated_at)
                VALUES (%s, %s::jsonb, NOW())
                ON CONFLICT (key)
                DO NOTHING
                """,
                (key, payload),
            )


def save_json_local(path: Path, data) -> None:
    with DATA_LOCK:
        with path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=True)


def seed_json_key(path: Path, default) -> None:
    if db_enabled():
        payload = default
        try:
            if path.exists():
                with path.open("r", encoding="utf-8") as handle:
                    payload = json.load(handle)
        except Exception:
            payload = default
        try:
            db_seed_json(path, payload)
            return
        except Exception as exc:
            remember_db_error(exc)
    if path.exists():
        return
    save_json_local(path, default)


def load_json(path: Path, default):
    if db_enabled():
        try:
            return db_load_json(path, default)
        except Exception as exc:
            remember_db_error(exc)
    if not path.exists():
        return default
    with DATA_LOCK:
        try:
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except json.JSONDecodeError:
            return default


def save_json(path: Path, data) -> None:
    if db_enabled():
        try:
            db_save_json(path, data)
            return
        except Exception as exc:
            remember_db_error(exc)
    save_json_local(path, data)


def parse_bool_env(value: str | None, default_value: bool) -> bool:
    if value is None:
        return default_value
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_lookup_raw(key: str) -> tuple[str | None, str]:
    direct_variants = (key, key.upper(), key.lower())
    for candidate in direct_variants:
        if candidate in os.environ:
            return os.environ.get(candidate), candidate
    key_lower = key.lower()
    for candidate, raw in os.environ.items():
        if candidate.lower() == key_lower:
            return raw, candidate
    return None, ""


def env_first_with_source(*keys: str, default: str = "") -> tuple[str, str]:
    for key in keys:
        raw, source = env_lookup_raw(key)
        if raw is None:
            continue
        value = str(raw).strip()
        if value:
            return value, source or key
    return default, ""


def env_first(*keys: str, default: str = "") -> str:
    value, _ = env_first_with_source(*keys, default=default)
    return value


def parse_bool_env_keys_with_source(keys: list[str], default_value: bool) -> tuple[bool, str]:
    for key in keys:
        raw, source = env_lookup_raw(key)
        if raw is None or not str(raw).strip():
            continue
        return parse_bool_env(str(raw), default_value), source or key
    return default_value, ""


def parse_bool_env_keys(keys: list[str], default_value: bool) -> bool:
    value, _ = parse_bool_env_keys_with_source(keys, default_value)
    return value


def smtp_defaults_from_env() -> dict:
    host, host_source = env_first_with_source(
        "AURA_SMTP_HOST",
        "AURA_MAIL_HOST",
        "SMTP_HOST",
        "MAIL_HOST",
        "EMAIL_HOST",
        "GMAIL_SMTP_HOST",
    )
    username, username_source = env_first_with_source(
        "AURA_SMTP_USER",
        "AURA_SMTP_USERNAME",
        "AURA_MAIL_USER",
        "AURA_MAIL_USERNAME",
        "SMTP_USER",
        "SMTP_USERNAME",
        "MAIL_USER",
        "MAIL_USERNAME",
        "EMAIL_USER",
        "EMAIL_USERNAME",
        "GMAIL_USER",
        "GMAIL_EMAIL",
        "SMTP_LOGIN",
    )
    password, password_source = env_first_with_source(
        "AURA_SMTP_PASS",
        "AURA_SMTP_PASSWORD",
        "AURA_MAIL_PASS",
        "AURA_MAIL_PASSWORD",
        "SMTP_PASS",
        "SMTP_PASSWORD",
        "MAIL_PASS",
        "MAIL_PASSWORD",
        "EMAIL_PASS",
        "EMAIL_PASSWORD",
        "GMAIL_APP_PASSWORD",
        "GMAIL_PASS",
        "SMTP_APP_PASSWORD",
        "APP_PASSWORD",
    )
    from_name, from_source = env_first_with_source(
        "AURA_SMTP_FROM",
        "AURA_MAIL_FROM",
        "SMTP_FROM",
        "MAIL_FROM",
        "MAIL_FROM_NAME",
        "EMAIL_FROM",
        "FROM_NAME",
        default="AuraCalistenia",
    )
    admin_email, admin_source = env_first_with_source(
        "AURA_SMTP_ADMIN",
        "AURA_SMTP_ADMIN_EMAIL",
        "AURA_MAIL_ADMIN",
        "SMTP_ADMIN",
        "MAIL_ADMIN",
        "ADMIN_EMAIL",
        "SMTP_TO",
    )

    tls_keys = ["AURA_SMTP_TLS", "AURA_MAIL_TLS", "SMTP_TLS", "MAIL_TLS", "EMAIL_TLS"]
    ssl_keys = ["AURA_SMTP_SSL", "AURA_MAIL_SSL", "SMTP_SSL", "MAIL_SSL", "EMAIL_SSL"]
    enabled_keys = ["AURA_SMTP_ENABLED", "AURA_MAIL_ENABLED", "SMTP_ENABLED", "MAIL_ENABLED", "EMAIL_ENABLED"]

    use_ssl, ssl_source = parse_bool_env_keys_with_source(ssl_keys, False)
    use_tls, tls_source = parse_bool_env_keys_with_source(tls_keys, not use_ssl)

    port_raw, port_source = env_first_with_source(
        "AURA_SMTP_PORT",
        "AURA_MAIL_PORT",
        "SMTP_PORT",
        "MAIL_PORT",
        "EMAIL_PORT",
        "GMAIL_SMTP_PORT",
    )
    try:
        port = int(port_raw) if port_raw else (465 if use_ssl else 587)
    except ValueError:
        port = 465 if use_ssl else 587

    if host and ":" in host and not host.startswith(("http://", "https://")):
        host_part, port_part = host.rsplit(":", 1)
        if host_part and port_part.isdigit():
            host = host_part.strip()
            port = int(port_part)

    if not host and username.lower().endswith("@gmail.com"):
        host = "smtp.gmail.com"
    if username.lower().endswith("@gmail.com") and " " in password:
        password = password.replace(" ", "")
    if port == 465 and not use_ssl:
        use_ssl = True
        use_tls = False
    if use_ssl and use_tls:
        use_tls = False

    explicit_enabled, enabled_source = parse_bool_env_keys_with_source(enabled_keys, False)
    has_credentials = bool(host and username and password)
    enabled = explicit_enabled or has_credentials

    return {
        "enabled": enabled,
        "host": host,
        "port": port,
        "username": username,
        "password": password,
        "from_name": from_name,
        "admin_email": admin_email,
        "use_tls": use_tls,
        "use_ssl": use_ssl,
        "source_host": host_source,
        "source_port": port_source,
        "source_username": username_source,
        "source_password": password_source,
        "source_from_name": from_source,
        "source_admin_email": admin_source,
        "source_tls": tls_source,
        "source_ssl": ssl_source,
        "source_enabled": enabled_source,
    }


def ensure_data_files() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    if db_enabled():
        try:
            db_bootstrap()
        except Exception as exc:
            remember_db_error(exc)
    UPLOAD_DIR.mkdir(exist_ok=True)

    seed_json_key(EVENTS_PATH, DEFAULT_EVENTS)
    seed_json_key(VIDEOS_PATH, DEFAULT_VIDEOS)
    seed_json_key(APPLICATIONS_PATH, [])
    seed_json_key(SUBMISSIONS_PATH, [])
    seed_json_key(CHATS_PATH, [])
    seed_json_key(SESSIONS_PATH, {})

    salt, pw_hash = hash_password("admin")
    settings = {
        "admin": {"username": "admin", "salt": salt, "hash": pw_hash},
    }
    seed_json_key(SETTINGS_PATH, settings)

    seed_json_key(CONTENT_PATH, DEFAULT_CONTENT)
    seed_json_key(PASSWORD_RESETS_PATH, {})


def copy_default_plan() -> dict:
    return json.loads(json.dumps(DEFAULT_TRAINING_PLAN))


def copy_default_content() -> dict:
    return json.loads(json.dumps(DEFAULT_CONTENT))


def normalize_content(content: dict | None) -> dict:
    default = copy_default_content()
    if not isinstance(content, dict):
        return default

    hero = content.get("hero")
    if isinstance(hero, dict):
        for key in ("eyebrow", "title", "subtitle"):
            if hero.get(key):
                default["hero"][key] = str(hero.get(key))

    stats = content.get("stats")
    if isinstance(stats, list):
        cleaned_stats = []
        for stat in stats:
            if not isinstance(stat, dict):
                continue
            value = str(stat.get("value", "")).strip()
            label = str(stat.get("label", "")).strip()
            if value or label:
                cleaned_stats.append({"value": value, "label": label})
        if cleaned_stats:
            default["stats"] = cleaned_stats

    bio = content.get("bio")
    if isinstance(bio, dict):
        for key in ("eyebrow", "name", "signature", "image", "image_caption"):
            if bio.get(key):
                default["bio"][key] = str(bio.get(key))
        paragraphs = bio.get("paragraphs")
        if isinstance(paragraphs, list):
            cleaned = [str(p).strip() for p in paragraphs if str(p).strip()]
            if cleaned:
                default["bio"]["paragraphs"] = cleaned

    program = content.get("program")
    if isinstance(program, dict):
        for key in ("title", "lead", "highlight_title", "highlight_text", "image", "image_caption"):
            if program.get(key):
                default["program"][key] = str(program.get(key))
        bullets = program.get("bullets")
        if isinstance(bullets, list):
            cleaned = [str(b).strip() for b in bullets if str(b).strip()]
            if cleaned:
                default["program"]["bullets"] = cleaned

    contact = content.get("contact")
    if isinstance(contact, dict):
        for key in ("email", "phone", "city", "instagram"):
            if contact.get(key):
                default["contact"][key] = str(contact.get(key))

    sponsors = content.get("sponsors")
    if isinstance(sponsors, list):
        cleaned = []
        had_vitastrong = False
        for sponsor in sponsors:
            if not isinstance(sponsor, dict):
                continue
            name = str(sponsor.get("name", "")).strip()
            logo = str(sponsor.get("logo", "")).strip()
            url = str(sponsor.get("url", "")).strip()
            name_key = name.lower().replace(" ", "")
            if "vitastrong" in name.lower():
                had_vitastrong = True
                continue
            if name_key in {"pullup&dip", "pullupdip"} and not url:
                url = SPONSOR_PULLUP_URL
            elif name_key == "zumub" and not url:
                url = SPONSOR_ZUMUB_URL
            if name and logo:
                entry = {"name": name, "logo": logo}
                if url:
                    entry["url"] = url
                cleaned.append(entry)
        if had_vitastrong:
            has_pullup = any(
                str(item.get("name", "")).strip().lower().replace(" ", "") in {"pullup&dip", "pullupdip"}
                for item in cleaned
            )
            has_zumub = any(str(item.get("name", "")).strip().lower().replace(" ", "") == "zumub" for item in cleaned)
            if has_pullup and not has_zumub:
                cleaned.append({"name": "ZUMUB", "logo": "LOGOS/zumub.png", "url": SPONSOR_ZUMUB_URL})
        if cleaned:
            default["sponsors"] = cleaned

    return default


def load_content() -> dict:
    return normalize_content(load_json(CONTENT_PATH, DEFAULT_CONTENT))


def normalize_smtp_settings(settings: dict | None) -> dict:
    defaults = smtp_defaults_from_env()
    if not isinstance(settings, dict):
        return defaults
    normalized = defaults.copy()
    for key in ("enabled", "host", "port", "username", "password", "from_name", "admin_email", "use_tls", "use_ssl"):
        if key in settings:
            normalized[key] = settings.get(key)
    if not isinstance(normalized.get("port"), int):
        try:
            normalized["port"] = int(normalized.get("port", 587))
        except (TypeError, ValueError):
            normalized["port"] = 587
    normalized["enabled"] = bool(normalized.get("enabled"))
    normalized["use_tls"] = bool(normalized.get("use_tls"))
    normalized["use_ssl"] = bool(normalized.get("use_ssl"))
    normalized["host"] = str(normalized.get("host", "")).strip()
    normalized["username"] = str(normalized.get("username", "")).strip()
    normalized["password"] = str(normalized.get("password", "")).strip()
    normalized["from_name"] = str(normalized.get("from_name", "")).strip() or "AuraCalistenia"
    normalized["admin_email"] = str(normalized.get("admin_email", "")).strip()
    return normalized


def load_smtp_settings() -> dict:
    # SMTP se gestiona por entorno para no guardar secretos en la app.
    return normalize_smtp_settings(smtp_defaults_from_env())


def smtp_missing_fields(smtp_settings: dict) -> list[str]:
    missing = []
    if not str(smtp_settings.get("host", "")).strip():
        missing.append("AURA_SMTP_HOST")
    if not str(smtp_settings.get("username", "")).strip():
        missing.append("AURA_SMTP_USER")
    if not str(smtp_settings.get("password", "")).strip():
        missing.append("AURA_SMTP_PASS")
    return missing


def normalize_plan_item(item) -> dict:
    if isinstance(item, dict):
        rest_value = str(item.get("rest", "")).strip()
        if not rest_value:
            rest_value = str(item.get("accessories", "")).strip()
        status_value = str(item.get("status", "")).strip()
        if status_value not in {"done", "missed", ""}:
            status_value = ""
        return {
            "exercise": str(item.get("exercise", "")).strip(),
            "sets": str(item.get("sets", "")).strip(),
            "reps": str(item.get("reps", "")).strip(),
            "weight": str(item.get("weight", "")).strip(),
            "rest": rest_value,
            "notes": str(item.get("notes", "")).strip(),
            "status": status_value,
            "status_note": str(item.get("status_note", item.get("result_note", ""))).strip(),
            "student_note": str(item.get("student_note", item.get("feedback", ""))).strip(),
        }
    text = str(item).strip()
    if not text:
        return {}
    return {
        "exercise": text,
        "sets": "",
        "reps": "",
        "weight": "",
        "rest": "",
        "notes": "",
        "status": "",
        "status_note": "",
        "student_note": "",
    }


def normalize_plan_day(day) -> dict:
    items_source = []
    title = ""
    rest_flag = False
    status = ""
    status_note = ""
    feedback = ""
    if isinstance(day, dict):
        title = str(day.get("title", "")).strip()
        rest_flag = bool(day.get("rest", False))
        status = str(day.get("status", "")).strip()
        status_note = str(day.get("status_note", "")).strip()
        feedback = str(day.get("feedback", "")).strip()
        items = day.get("items")
        if isinstance(items, list):
            items_source = items
        else:
            items_source = [day]
    elif isinstance(day, list):
        items_source = day
    elif day is not None:
        items_source = [day]
    normalized_items = []
    for item in items_source:
        normalized = normalize_plan_item(item)
        if normalized and normalized.get("exercise"):
            normalized_items.append(normalized)
    return {
        "title": title,
        "rest": rest_flag,
        "items": normalized_items,
        "status": status,
        "status_note": status_note,
        "feedback": feedback,
    }


def normalize_plan(plan: dict | None) -> dict:
    default = copy_default_plan()
    if not isinstance(plan, dict):
        plan = {}
    weeks = plan.get("weeks")
    if not isinstance(weeks, list):
        weeks = []
    default_weeks = default.get("weeks")
    if not isinstance(default_weeks, list):
        default_weeks = []
    normalized = {
        "title": plan.get("title") or default.get("title", "Plan 4 semanas"),
        "weeks": [],
    }
    for index in range(4):
        source_week = weeks[index] if index < len(weeks) and isinstance(weeks[index], dict) else {}
        default_week = (
            default_weeks[index] if index < len(default_weeks) and isinstance(default_weeks[index], dict) else {}
        )
        title = source_week.get("title") or default_week.get("title", f"Semana {index + 1}")
        summary = str(source_week.get("summary", "")).strip()
        days = source_week.get("days")
        if not isinstance(days, list):
            days = []
        default_days = default_week.get("days")
        if not isinstance(default_days, list):
            default_days = []
        normalized_days = []
        for day_index in range(7):
            day_source = days[day_index] if day_index < len(days) else None
            if day_source is None and day_index < len(default_days):
                day_source = default_days[day_index]
            normalized_days.append(normalize_plan_day(day_source))
        normalized["weeks"].append({"title": title, "summary": summary, "days": normalized_days})
    return normalized


def ensure_application_fields(applications: list[dict]) -> list[dict]:
    changed = False
    for app in applications:
        if "approved" not in app:
            app["approved"] = False
            changed = True
        if not isinstance(app.get("approved"), bool):
            app["approved"] = bool(app.get("approved"))
            changed = True
        if "goal" not in app:
            app["goal"] = ""
            changed = True
        if "concerns" not in app:
            app["concerns"] = ""
            changed = True
        normalized_plan = normalize_plan(app.get("plan"))
        if app.get("plan") != normalized_plan:
            app["plan"] = normalized_plan
            changed = True
    if changed:
        save_json(APPLICATIONS_PATH, applications)
    return applications


def load_applications() -> list[dict]:
    return ensure_application_fields(load_json(APPLICATIONS_PATH, []))


def load_submissions() -> list[dict]:
    data = load_json(SUBMISSIONS_PATH, [])
    return data if isinstance(data, list) else []


def clean_sessions(sessions: dict) -> dict:
    now = time.time()
    return {token: data for token, data in sessions.items() if data.get("expires", 0) > now}


def clean_password_resets(tokens: dict) -> dict:
    now = int(time.time())
    cleaned: dict[str, dict] = {}
    for raw_token, data in (tokens or {}).items():
        if not isinstance(data, dict):
            continue
        token = str(raw_token).strip()
        username = str(data.get("username", "")).strip()
        email = str(data.get("email", "")).strip().lower()
        try:
            expires_at = int(data.get("expires_at", 0) or 0)
        except (TypeError, ValueError):
            expires_at = 0
        if not token or not username or not email or expires_at <= now:
            continue
        cleaned[token] = {
            "username": username,
            "email": email,
            "expires_at": expires_at,
        }
    return cleaned


def load_password_resets() -> dict[str, dict]:
    stored = load_json(PASSWORD_RESETS_PATH, {})
    if not isinstance(stored, dict):
        stored = {}
    cleaned = clean_password_resets(stored)
    if cleaned != stored:
        save_json(PASSWORD_RESETS_PATH, cleaned)
    return cleaned


def create_password_reset_token(username: str, email: str) -> str:
    tokens = load_password_resets()
    username_key = username.strip().lower()
    email_key = email.strip().lower()
    for token, record in list(tokens.items()):
        if (
            str(record.get("username", "")).strip().lower() == username_key
            and str(record.get("email", "")).strip().lower() == email_key
        ):
            tokens.pop(token, None)
    token = secrets.token_urlsafe(32)
    tokens[token] = {
        "username": username.strip(),
        "email": email.strip().lower(),
        "expires_at": int(time.time()) + RESET_TOKEN_TTL,
    }
    save_json(PASSWORD_RESETS_PATH, tokens)
    return token


def peek_password_reset_token(token: str) -> dict | None:
    if not token:
        return None
    tokens = load_password_resets()
    return tokens.get(token.strip())


def consume_password_reset_token(token: str) -> dict | None:
    if not token:
        return None
    tokens = load_password_resets()
    payload = tokens.pop(token.strip(), None)
    save_json(PASSWORD_RESETS_PATH, tokens)
    return payload


def create_session(username: str, role: str) -> str:
    sessions = load_json(SESSIONS_PATH, {})
    if not isinstance(sessions, dict):
        sessions = {}
    sessions = clean_sessions(sessions)
    token = secrets.token_urlsafe(32)
    sessions[token] = {"user": username, "role": role, "expires": time.time() + SESSION_TTL}
    save_json(SESSIONS_PATH, sessions)
    return token


def delete_session(token: str) -> None:
    sessions = load_json(SESSIONS_PATH, {})
    if not isinstance(sessions, dict):
        sessions = {}
    if token in sessions:
        sessions.pop(token, None)
        save_json(SESSIONS_PATH, sessions)


def get_session_user(cookie_header: str | None, cookie_name: str, role: str | None = None) -> str | None:
    if not cookie_header:
        return None
    cookies = {}
    for part in cookie_header.split(";"):
        if "=" in part:
            key, value = part.split("=", 1)
            cookies[key.strip()] = value.strip()
    token = cookies.get(cookie_name)
    if not token:
        return None
    raw_sessions = load_json(SESSIONS_PATH, {})
    if not isinstance(raw_sessions, dict):
        raw_sessions = {}
    sessions = clean_sessions(raw_sessions)
    if sessions != raw_sessions:
        save_json(SESSIONS_PATH, sessions)
    data = sessions.get(token)
    if not data:
        return None
    if role and data.get("role") != role:
        return None
    return data.get("user")


def get_cookie_token(cookie_header: str | None, cookie_name: str) -> str | None:
    if not cookie_header:
        return None
    for part in cookie_header.split(";"):
        if part.strip().startswith(f"{cookie_name}="):
            return part.strip().split("=", 1)[1]
    return None


def strip_fallback_blocks(content: str, key: str) -> str:
    start = f"<!-- FALLBACK_{key}_START -->"
    end = f"<!-- FALLBACK_{key}_END -->"
    while True:
        start_index = content.find(start)
        if start_index == -1:
            break
        end_index = content.find(end, start_index + len(start))
        if end_index == -1:
            break
        content = content[:start_index] + content[end_index + len(end):]
    return content


def render_template(path: Path, replacements: dict[str, str]) -> str:
    content = path.read_text(encoding="utf-8")
    for key, value in replacements.items():
        token = "{{" + key + "}}"
        content = content.replace(f"<!-- {token} -->", value)
        content = content.replace(f"<!--{token}-->", value)
        content = content.replace(token, value)
        content = strip_fallback_blocks(content, key)
    return content


def build_form_alert(query: dict[str, list[str]]) -> str:
    status = (query.get("status") or [""])[0]
    message = (query.get("message") or [""])[0]
    if not status:
        return ""
    if status == "ok":
        text = "Solicitud recibida. Revisa tu email para confirmar el acceso."
        level = "success"
    elif status == "smtp_disabled":
        text = "Solicitud guardada, pero el envío de correo está desactivado (AURA_SMTP_ENABLED)."
        level = "error"
    elif status == "smtp_incomplete":
        text = message or "Falta configurar variables SMTP en Render."
        level = "error"
    elif status == "smtp_error":
        text = "No se pudo enviar el correo (error SMTP). Revisa host, puerto, TLS/SSL y contraseña de aplicación."
        level = "error"
    else:
        text = message or "No se pudo enviar la solicitud."
        level = "error"
    return f'<div class="form-alert {level}">{html.escape(text)}</div>'


def build_admin_alert(query: dict[str, list[str]]) -> str:
    status = (query.get("admin_status") or query.get("status") or [""])[0]
    if not status:
        return ""
    if status == "error":
        return '<div class="form-alert error">No se pudo completar la operación.</div>'
    messages = {
        "event_added": "Evento guardado.",
        "event_updated": "Competición actualizada.",
        "event_deleted": "Evento eliminado.",
        "event_moved": "Orden de competiciones actualizado.",
        "app_approved": "Usuario aprobado.",
        "app_deleted": "Solicitud eliminada.",
        "video_added": "Vídeo guardado.",
        "video_updated": "Vídeo actualizado.",
        "video_deleted": "Vídeo eliminado.",
        "video_moved": "Orden de vídeos actualizado.",
        "plan_saved": "Plan de entrenamiento actualizado.",
        "comment_added": "Comentario enviado.",
        "submission_deleted": "Envío eliminado.",
        "content_saved": "Contenido web actualizado.",
        "client_added": "Alumno creado.",
        "client_duplicated": "Alumno duplicado.",
        "client_exists": "Ese usuario ya existe.",
        "smtp_test_ok": "Prueba SMTP enviada correctamente.",
        "smtp_test_disabled": "SMTP desactivado. Activa AURA_SMTP_ENABLED o define credenciales.",
        "smtp_test_incomplete": "SMTP incompleto. Faltan variables HOST/USER/PASS.",
        "smtp_test_failed": "La prueba SMTP falló. Revisa el detalle técnico en la tarjeta Estado SMTP.",
    }
    if status not in messages:
        return ""
    text = messages[status]
    return f'<div class="form-alert success">{html.escape(text)}</div>'


def build_access_alert(status: str, role: str) -> str:
    if not status or not status.startswith(f"{role}_"):
        return ""
    messages = {
        "user_ok": ("success", "Acceso correcto. Bienvenido."),
        "user_error": ("error", "Usuario o contraseña incorrectos."),
        "user_pending": ("error", "Tu cuenta aún no está activa."),
        "user_missing": ("error", "Completa usuario y contraseña."),
        "user_logout": ("success", "Sesión cerrada."),
        "user_submit_ok": ("success", "Vídeo enviado. Recibirás feedback."),
        "user_submit_error": ("error", "No se pudo enviar el vídeo."),
        "user_reset_missing": ("error", "Completa usuario y email para recuperar tu acceso."),
        "user_reset_sent": ("success", "Si los datos coinciden, te hemos enviado un enlace de restablecimiento."),
        "user_reset_smtp": ("error", "No se pudo enviar el email de recuperación. Revisa SMTP en Render."),
        "user_reset_smtp_disabled": (
            "error",
            "No se pudo enviar el email: el envío SMTP está desactivado (AURA_SMTP_ENABLED).",
        ),
        "user_reset_smtp_incomplete": (
            "error",
            "No se pudo enviar el email: faltan variables SMTP (HOST/USER/PASS) en Render.",
        ),
        "user_reset_smtp_failed": (
            "error",
            "No se pudo enviar el email de recuperación por error SMTP. Revisa host, puerto, TLS/SSL y contraseña.",
        ),
        "user_reset_invalid": ("error", "El enlace de recuperación no es válido o ha caducado."),
        "user_reset_mismatch": ("error", "Las contraseñas no coinciden o están vacías."),
        "user_reset_done": ("success", "Contraseña actualizada. Ya puedes iniciar sesión."),
        "admin_ok": ("success", "Sesión admin activa."),
        "admin_error": ("error", "Credenciales admin incorrectas."),
        "admin_logout": ("success", "Sesión cerrada."),
    }
    level, text = messages.get(status, ("success", "Acceso actualizado."))
    return f'<div class="form-alert {level}">{html.escape(text)}</div>'


def find_application(applications: list[dict], username: str) -> dict | None:
    target = username.strip().lower()
    for app in applications:
        if app.get("username", "").strip().lower() == target:
            return app
    return None


def render_application_list(applications: list[dict]) -> str:
    items = []
    for index, app in enumerate(applications):
        raw_id = str(app.get("id", ""))
        app_id = html.escape(raw_id)
        raw_username = str(app.get("username", ""))
        username = html.escape(raw_username)
        raw_email = str(app.get("email", ""))
        email = html.escape(raw_email)
        skill = html.escape(str(app.get("skill", "")))
        level = html.escape(str(app.get("level", "")))
        goal = html.escape(str(app.get("goal", "")))
        concerns = html.escape(str(app.get("concerns", "")))
        approved = bool(app.get("approved"))
        status = "Activo" if approved else "Pendiente"
        actions = []
        plan_href = (
            f"/admin?admin_section=portal&plan_user={urllib.parse.quote(raw_username)}#plan"
        )
        actions.append(f'<a class="btn glass primary small" href="{plan_href}">Ver alumno</a>')
        if not approved:
            actions.append(
                "\n".join(
                    [
                        "  <form class=\"admin-inline-form\" action=\"/admin/applications/approve\" method=\"post\">",
                        f"    <input type=\"hidden\" name=\"id\" value=\"{app_id}\">",
                        "    <button class=\"btn glass primary small\" type=\"submit\">Aprobar</button>",
                        "  </form>",
                    ]
                )
            )
        actions.append(
            "\n".join(
                [
                    "  <form class=\"admin-inline-form\" action=\"/admin/clients/duplicate\" method=\"post\">",
                    f"    <input type=\"hidden\" name=\"id\" value=\"{app_id}\">",
                    "    <button class=\"btn glass ghost small\" type=\"submit\">Duplicar</button>",
                    "  </form>",
                ]
            )
        )
        actions.append(
            "\n".join(
                [
                    "  <form class=\"admin-inline-form\" action=\"/admin/applications/delete\" method=\"post\">",
                    f"    <input type=\"hidden\" name=\"id\" value=\"{app_id}\">",
                    "    <button class=\"btn glass ghost small\" type=\"submit\">Eliminar</button>",
                    "  </form>",
                ]
            )
        )
        search_blob = " ".join([raw_username, raw_email, str(app.get("skill", "")), raw_id]).lower()
        meta = []
        if skill:
            meta.append(f"Skill: {skill}")
        if goal:
            meta.append(f"Objetivo: {goal}")
        if level:
            meta.append(f"Nivel: {level}")
        meta.append(f"Estado: {status}")
        summary = " · ".join(meta) if meta else status
        detail_lines = [
            f"      <span>ID {app_id}</span>",
            f"      <span>Email: {email}</span>",
            f"      <span>Estado: {status}</span>",
        ]
        if skill:
            detail_lines.append(f"      <span>Skill: {skill}</span>")
        if goal:
            detail_lines.append(f"      <span>Objetivo: {goal}</span>")
        if level:
            detail_lines.append(f"      <span>Nivel: {level}</span>")
        if concerns:
            detail_lines.append(f"      <span>Inquietudes: {concerns}</span>")
        open_attr = " open" if index == 0 else ""
        items.append(
            "\n".join(
                [
                    f'<li class="admin-item admin-edit-item admin-collapsible-item student-item" data-search="{html.escape(search_blob)}">',
                    f'  <details class="admin-collapsible"{open_attr}>',
                    '    <summary class="admin-collapsible-summary">',
                    '      <div class="admin-collapsible-main">',
                    f"        <strong>{username}</strong>",
                    f"        <span>{summary}</span>",
                    "      </div>",
                    f'      <span class="admin-collapsible-tag">{status}</span>',
                    "    </summary>",
                    '    <div class="admin-collapsible-content">',
                    "      <div>",
                    "\n".join(detail_lines),
                    "      </div>",
                    f"      <div class=\"admin-actions\">{''.join(actions)}</div>",
                    "    </div>",
                    "  </details>",
                    "</li>",
                ]
            )
        )
    return "\n".join(items) if items else "<li class=\"admin-item\">Sin solicitudes.</li>"


def format_date(value: int | float | str) -> str:
    try:
        timestamp = int(value)
    except (TypeError, ValueError):
        return ""
    return time.strftime("%d-%m-%Y", time.localtime(timestamp))


def format_datetime(value: int | float | str) -> str:
    try:
        timestamp = int(value)
    except (TypeError, ValueError):
        return ""
    return time.strftime("%d-%m %H:%M", time.localtime(timestamp))


def compute_day_progress(day: dict) -> dict:
    items = day.get("items") if isinstance(day, dict) else []
    if not isinstance(items, list):
        items = []
    total = len([item for item in items if isinstance(item, dict) and str(item.get("exercise", "")).strip()])
    done = 0
    missed = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status", "")).strip()
        if status == "done":
            done += 1
        elif status == "missed":
            missed += 1
    pending = max(total - done - missed, 0)
    done_pct = int(round((done / total) * 100)) if total else 0
    missed_pct = int(round((missed / total) * 100)) if total else 0
    pending_pct = max(0, 100 - done_pct - missed_pct) if total else 0
    return {
        "total": total,
        "done": done,
        "missed": missed,
        "pending": pending,
        "done_pct": done_pct,
        "missed_pct": missed_pct,
        "pending_pct": pending_pct,
    }


def compute_week_progress(week: dict) -> dict:
    days = week.get("days") if isinstance(week, dict) else []
    if not isinstance(days, list):
        days = []
    done = 0
    missed = 0
    pending = 0
    total = 0
    for day in days:
        day_stats = compute_day_progress(day)
        total += day_stats["total"]
        done += day_stats["done"]
        missed += day_stats["missed"]
        pending += day_stats["pending"]
    done_pct = int(round((done / total) * 100)) if total else 0
    missed_pct = int(round((missed / total) * 100)) if total else 0
    pending_pct = max(0, 100 - done_pct - missed_pct) if total else 0
    return {
        "total": total,
        "done": done,
        "missed": missed,
        "pending": pending,
        "done_pct": done_pct,
        "missed_pct": missed_pct,
        "pending_pct": pending_pct,
    }


def build_progress_payload(plan: dict) -> dict:
    normalized = normalize_plan(plan)
    week_payload = []
    for index, week in enumerate(normalized.get("weeks", []), start=1):
        stats = compute_week_progress(week)
        week_payload.append(
            {
                "week": index,
                "title": week.get("title", f"Semana {index}"),
                **stats,
            }
        )
    return {"weeks": week_payload}


def load_chat_messages(username: str) -> list[dict]:
    records = load_json(CHATS_PATH, [])
    if not isinstance(records, list):
        return []
    target = username.strip().lower()
    filtered = []
    for item in records:
        if not isinstance(item, dict):
            continue
        if str(item.get("username", "")).strip().lower() != target:
            continue
        try:
            created_at = int(item.get("created_at", 0) or 0)
        except (TypeError, ValueError):
            created_at = 0
        filtered.append(
            {
                "id": str(item.get("id", "")),
                "username": str(item.get("username", "")),
                "author": str(item.get("author", "")),
                "text": str(item.get("text", "")),
                "created_at": created_at,
            }
        )
    filtered.sort(key=lambda entry: entry.get("created_at", 0))
    return filtered


def render_chat_panel(username: str, role: str) -> str:
    messages = load_chat_messages(username)
    items = []
    for msg in messages[-200:]:
        author = msg.get("author", "")
        own = "is-own" if (role == "user" and author == "user") or (role == "admin" and author == "coach") else ""
        author_label = "Alumno" if author == "user" else "Profesor"
        created_at = format_datetime(msg.get("created_at", 0))
        text = html.escape(msg.get("text", ""))
        items.append(
            "\n".join(
                [
                    f'<li class="chat-message {own}">',
                    f'  <span class="chat-author">{author_label}</span>',
                    f"  <p>{text}</p>",
                    f'  <span class="chat-time">{created_at}</span>',
                    "</li>",
                ]
            )
        )
    list_html = "\n".join(items) if items else '<li class="chat-empty">Sin mensajes todavía.</li>'
    if role == "admin":
        return "\n".join(
            [
                '<div class="portal-card glass-card chat-panel">',
                f'  <h3 id="coach_chat_title">Comentarios con {html.escape(username)}</h3>',
                f'  <ul id="coach_chat_list" class="chat-list">{list_html}</ul>',
                '  <form class="admin-form chat-form" action="/admin/chat/send" method="post">',
                f'    <input id="coach_chat_username" type="hidden" name="username" value="{html.escape(username)}">',
                '    <div class="form-field">',
                '      <label for="coach_chat_text">Comentario para el alumno</label>',
                '      <textarea id="coach_chat_text" name="text" rows="3" placeholder="Escribe un mensaje..." required></textarea>',
                "    </div>",
                '    <button class="btn glass primary small" type="submit">Enviar</button>',
                "  </form>",
                "</div>",
            ]
        )
    else:
        form_html = "\n".join(
            [
                '<form class="admin-form chat-form" action="/portal/chat/send" method="post">',
                '  <div class="form-field">',
                '    <label for="user_chat_text">Comentarios con tu profesor</label>',
                '    <textarea id="user_chat_text" name="text" rows="3" placeholder="Escribe tu consulta o comentario..." required></textarea>',
                "  </div>",
                '  <button class="btn glass primary small" type="submit">Enviar</button>',
                "</form>",
            ]
        )
    return "\n".join(
        [
            '<div class="portal-card glass-card chat-panel">',
            "  <h3>Comentarios con tu profesor</h3>",
            f'  <ul class="chat-list">{list_html}</ul>',
            form_html,
            "</div>",
        ]
    )


def render_coach_dashboard(applications: list[dict], storage_status: dict) -> str:
    now = datetime.now()
    this_month = 0
    duplicate_rows = 0
    seen_pairs: set[tuple[str, str]] = set()
    duplicate_signatures: set[tuple[str, str]] = set()
    for app in applications:
        created_at = app.get("created_at", 0)
        try:
            created_dt = datetime.fromtimestamp(int(created_at))
        except (TypeError, ValueError, OSError):
            created_dt = None
        if created_dt and created_dt.year == now.year and created_dt.month == now.month:
            this_month += 1
        username = str(app.get("username", "")).strip().lower()
        email = str(app.get("email", "")).strip().lower()
        signature = (username, email)
        if signature in seen_pairs:
            duplicate_signatures.add(signature)
        seen_pairs.add(signature)
    for app in applications:
        signature = (
            str(app.get("username", "")).strip().lower(),
            str(app.get("email", "")).strip().lower(),
        )
        if signature in duplicate_signatures:
            duplicate_rows += 1

    total = len(applications)
    approved = sum(1 for app in applications if app.get("approved"))
    pending = total - approved
    storage_mode = storage_status.get("mode", "local")
    storage_class = "storage-local"
    if storage_mode == "db_ok":
        storage_class = "storage-ok"
    elif storage_mode == "db_error":
        storage_class = "storage-error"
    storage_title = html.escape(str(storage_status.get("title", "")))
    storage_detail = html.escape(str(storage_status.get("detail", "")))
    storage_debug = html.escape(str(storage_status.get("debug", "")))
    storage_lines = [
        f'  <div class="storage-pill {storage_class}">',
        '    <span class="storage-pill-label">Estado de guardado</span>',
        f"    <strong>{storage_title}</strong>",
        f"    <span>{storage_detail}</span>",
    ]
    if storage_mode == "db_error" and storage_debug:
        storage_lines.extend(
            [
                '    <details class="storage-pill-debug">',
                "      <summary>Ver detalle técnico</summary>",
                f"      <pre>{storage_debug}</pre>",
                "    </details>",
            ]
        )
    storage_lines.append("  </div>")
    storage_html = "\n".join(storage_lines)

    smtp_settings = load_smtp_settings()
    smtp_enabled = bool(smtp_settings.get("enabled"))
    smtp_missing = smtp_missing_fields(smtp_settings)
    smtp_error = SMTP_LAST_ERROR.strip()
    smtp_class = "storage-local"
    smtp_title = "SMTP desactivado"
    smtp_detail = "Define credenciales SMTP (host, usuario y contraseña) en Render para activar correos."
    if smtp_enabled and smtp_missing:
        smtp_class = "storage-error"
        smtp_title = "SMTP incompleto"
        smtp_detail = f"Faltan variables: {', '.join(smtp_missing)}."
    elif smtp_enabled and smtp_error:
        smtp_class = "storage-error"
        smtp_title = "SMTP con error"
        smtp_detail = "Hubo un error de envío. Abre el detalle técnico para ver la causa exacta."
    elif smtp_enabled:
        smtp_class = "storage-ok"
        smtp_title = "SMTP listo"
        smtp_detail = "Configuración cargada. Registro y recuperación deberían enviar correo."

    smtp_host = str(smtp_settings.get("host", "")).strip() or "(vacío)"
    smtp_user = str(smtp_settings.get("username", "")).strip() or "(vacío)"
    smtp_admin = str(smtp_settings.get("admin_email", "")).strip() or "(usa AURA_SMTP_USER)"
    smtp_host_source = str(smtp_settings.get("source_host", "")).strip() or "no detectado"
    smtp_user_source = str(smtp_settings.get("source_username", "")).strip() or "no detectado"
    smtp_pass_source = str(smtp_settings.get("source_password", "")).strip() or "no detectado"
    smtp_port = int(smtp_settings.get("port", 587))
    smtp_tls = bool(smtp_settings.get("use_tls", True))
    smtp_ssl = bool(smtp_settings.get("use_ssl", False))
    smtp_security = "SSL directo" if smtp_ssl else ("STARTTLS" if smtp_tls else "Sin STARTTLS")

    smtp_lines = [
        f'  <div class="storage-pill {smtp_class}">',
        '    <span class="storage-pill-label">Estado SMTP</span>',
        f"    <strong>{html.escape(smtp_title)}</strong>",
        f"    <span>{html.escape(smtp_detail)}</span>",
        (
            "    <span>"
            f"Host: {html.escape(smtp_host)} · Puerto: {smtp_port} · Seguridad: {html.escape(smtp_security)}"
            "</span>"
        ),
        f"    <span>Usuario SMTP: {html.escape(smtp_user)}</span>",
        f"    <span>Bandeja admin: {html.escape(smtp_admin)}</span>",
        (
            "    <span>"
            f"Origen variables: host={html.escape(smtp_host_source)} · "
            f"user={html.escape(smtp_user_source)} · pass={html.escape(smtp_pass_source)}"
            "</span>"
        ),
    ]
    if smtp_error:
        smtp_lines.extend(
            [
                '    <details class="storage-pill-debug">',
                "      <summary>Ver detalle técnico SMTP</summary>",
                f"      <pre>{html.escape(smtp_error)}</pre>",
                "    </details>",
            ]
        )
    smtp_lines.append("  </div>")
    smtp_html = "\n".join(smtp_lines)
    return "\n".join(
        [
            '<div class="admin-card glass-card admin-wide">',
            '  <details class="admin-collapsible admin-main-collapsible" open>',
            '    <summary class="admin-collapsible-summary admin-main-summary">',
            '      <div class="admin-collapsible-main">',
            "        <strong>Gestión de alumnos</strong>",
            "        <span>Estado de guardado, métricas y filtro</span>",
            "      </div>",
            '      <span class="admin-collapsible-tag">Dashboard</span>',
            "    </summary>",
            '    <div class="admin-collapsible-content coach-dashboard">',
            "      <div class=\"coach-dashboard-head\">",
            '        <a class="btn glass ghost small" href="/admin/export/json">⬇ Descargar todos los JSON en ZIP</a>',
            '        <form class="admin-inline-form" action="/admin/smtp/test" method="post">',
            '          <button class="btn glass ghost small" type="submit">Probar SMTP</button>',
            "        </form>",
            "      </div>",
            storage_html,
            smtp_html,
            "      <div class=\"coach-stats\">",
            f"        <span>Total de alumnos: <strong>{total}</strong></span>",
            f"        <span>Activos: <strong>{approved}</strong></span>",
            f"        <span>Pendientes: <strong>{pending}</strong></span>",
            f"        <span>Altas este mes: <strong>{this_month}</strong></span>",
            f"        <span>Posibles duplicados: <strong>{duplicate_rows}</strong></span>",
            "      </div>",
            '      <div class="form-field">',
            '        <label for="student_search">Buscar alumno (usuario, email o ID)</label>',
            '        <input id="student_search" type="text" placeholder="Escribe para filtrar...">',
            "      </div>",
            "    </div>",
            "  </details>",
            "</div>",
        ]
    )


def plan_day_to_text(day: dict) -> str:
    items = day.get("items") if isinstance(day, dict) else []
    if not isinstance(items, list):
        return ""
    lines = []
    for item in items:
        if not isinstance(item, dict):
            continue
        parts = [
            str(item.get("exercise", "")).strip(),
            str(item.get("sets", "")).strip(),
            str(item.get("reps", "")).strip(),
            str(item.get("weight", "")).strip(),
            str(item.get("rest", "")).strip(),
            str(item.get("notes", "")).strip(),
        ]
        while parts and not parts[-1]:
            parts.pop()
        if parts:
            lines.append(" | ".join(parts))
    return "\n".join(lines)


def plan_week_to_texts(week: dict) -> list[str]:
    days = week.get("days")
    if not isinstance(days, list):
        return ["" for _ in range(7)]
    texts = [plan_day_to_text(day) for day in days]
    if len(texts) < 7:
        texts.extend(["" for _ in range(7 - len(texts))])
    return texts[:7]


def render_training_plan(plan: dict, active_week: int | None = None) -> str:
    normalized = normalize_plan(plan)
    if active_week not in {1, 2, 3, 4}:
        active_week = None
    parts = [
        '<div class="training-board glass-card" data-stagger>',
        f'  <div class="training-head"><h3>{html.escape(normalized.get("title", "Plan de entrenamiento"))}</h3></div>',
        '  <div class="training-filter">',
        '    <label for="portal_week_select">Semana</label>',
        '    <select id="portal_week_select">',
        '      <option value="all">Todas</option>',
        '      <option value="1">Semana 1</option>',
        '      <option value="2">Semana 2</option>',
        '      <option value="3">Semana 3</option>',
        '      <option value="4">Semana 4</option>',
        "    </select>",
        "  </div>",
        '  <div class="training-grid">',
    ]
    for week_index, week in enumerate(normalized.get("weeks", []), start=1):
        week_title = html.escape(week.get("title", f"Semana {week_index}"))
        week_summary = html.escape(week.get("summary", ""))
        week_stats = compute_week_progress(week)
        hidden_class = ""
        if active_week and active_week != week_index:
            hidden_class = " is-hidden-week"
        donut_done = week_stats["done_pct"]
        donut_missed = week_stats["missed_pct"]
        donut_pending = max(0, 100 - donut_done - donut_missed)
        donut_style = (
            "style=\"--done:"
            f"{donut_done};--missed:{donut_missed};--pending:{donut_pending};\""
        )
        open_attr = ""
        if active_week is None or active_week == week_index:
            open_attr = " open"
        parts.append(
            f'    <details class="training-week stagger-item{hidden_class}" id="week{week_index}" data-week="{week_index}"{open_attr}>'
        )
        parts.append('      <summary class="training-week-summary">')
        parts.append('        <div class="training-week-top">')
        parts.append(f'          <div class="training-week-title">{week_title}</div>')
        parts.append(
            f'          <div class="week-kpi"><span>✓ {week_stats["done"]} ({week_stats["done_pct"]}%)</span><span>✕ {week_stats["missed"]} ({week_stats["missed_pct"]}%)</span><span>⏳ {week_stats["pending"]} ({week_stats["pending_pct"]}%)</span></div>'
        )
        parts.append("        </div>")
        parts.append(
            '        <span class="training-week-toggle" data-open-label="Minimizar" data-closed-label="Maximizar" aria-hidden="true">Minimizar</span>'
        )
        parts.append("      </summary>")
        parts.append('      <div class="training-week-body">')
        parts.append('      <div class="week-chart-row">')
        parts.append(
            f'        <div class="week-donut" {donut_style}><span>{week_stats["done_pct"]}%</span></div>'
        )
        parts.append(
            f'        <div class="week-bar"><span style="--done:{donut_done};--missed:{donut_missed};--pending:{donut_pending};"></span></div>'
        )
        parts.append("      </div>")
        parts.append('      <div class="day-grid">')
        days = week.get("days") or []
        for day_index, day_text in enumerate(days, start=1):
            day_title = html.escape(day_text.get("title", "")) if isinstance(day_text, dict) else ""
            rest_flag = bool(day_text.get("rest")) if isinstance(day_text, dict) else False
            day_label = day_title or DAY_LABELS[(day_index - 1) % len(DAY_LABELS)]
            day_stats = compute_day_progress(day_text if isinstance(day_text, dict) else {})
            parts.append('        <div class="day-card">')
            parts.append('          <div class="day-card-head">')
            parts.append(f'            <span class="day-label">Día {day_index}</span>')
            parts.append(f'            <strong class="day-title">{html.escape(day_label)}</strong>')
            parts.append(
                f'            <span class="day-mini-stats">✓ {day_stats["done"]} · ✕ {day_stats["missed"]} · ⏳ {day_stats["pending"]}</span>'
            )
            parts.append("          </div>")
            items = day_text.get("items") if isinstance(day_text, dict) else []
            if rest_flag or not isinstance(items, list) or not items:
                parts.append('          <p class="plan-empty">Descanso o movilidad.</p>')
            if not rest_flag and isinstance(items, list) and items:
                if len(items) > 1:
                    parts.append('          <span class="portal-scroll-hint">Más de un ejercicio en este día.</span>')
                parts.append('          <div class="plan-items portal-items-row">')
                for item_index, item in enumerate(items, start=1):
                    if not isinstance(item, dict):
                        continue
                    exercise = html.escape(item.get("exercise", ""))
                    sets = html.escape(item.get("sets", ""))
                    reps = html.escape(item.get("reps", ""))
                    weight = html.escape(item.get("weight", ""))
                    rest = html.escape(item.get("rest", ""))
                    notes = html.escape(item.get("notes", ""))
                    status = str(item.get("status", "")).strip()
                    status_note = html.escape(item.get("status_note", ""))
                    student_note = html.escape(item.get("student_note", ""))
                    status_badge = "Pendiente"
                    status_class = "pending"
                    if status == "done":
                        status_badge = "Completado"
                        status_class = "done"
                    elif status == "missed":
                        status_badge = "Fallado"
                        status_class = "missed"
                    meta_parts = []
                    if sets:
                        meta_parts.append(f"<span>Series: {sets}</span>")
                    if reps:
                        meta_parts.append(f"<span>Reps: {reps}</span>")
                    if weight:
                        meta_parts.append(f"<span>Peso: {weight}</span>")
                    if rest:
                        meta_parts.append(f"<span>Descanso: {rest}</span>")
                    if notes:
                        meta_parts.append(f"<span>Notas: {notes}</span>")
                    meta_html = "".join(meta_parts) if meta_parts else "<span>Trabajo técnico.</span>"
                    parts.append(f'            <div class="plan-item portal-item {status_class}">')
                    parts.append('              <div class="portal-item-head">')
                    parts.append(f"                <h4>{exercise or 'Ejercicio'}</h4>")
                    parts.append(f'                <span class="item-status {status_class}">{status_badge}</span>')
                    parts.append("              </div>")
                    parts.append(f'              <div class="plan-meta">{meta_html}</div>')
                    if status_note:
                        parts.append(f'              <p class="item-status-note">{status_note}</p>')
                    parts.append('              <form class="item-status-form" action="/portal/item/update" method="post">')
                    parts.append(f'                <input type="hidden" name="week" value="{week_index}">')
                    parts.append(f'                <input type="hidden" name="day" value="{day_index}">')
                    parts.append(f'                <input type="hidden" name="item" value="{item_index}">')
                    parts.append('                <div class="status-buttons">')
                    parts.append(
                        f'                  <button class="status-button done{" is-active" if status == "done" else ""}" type="submit" name="status" value="done">Hecho</button>'
                    )
                    parts.append(
                        f'                  <button class="status-button missed{" is-active" if status == "missed" else ""}" type="submit" name="status" value="missed">Fallé</button>'
                    )
                    parts.append("                </div>")
                    parts.append(
                        f'                <input class="status-note" name="status_note" type="text" placeholder="Motivo (opcional)" value="{status_note}">'
                    )
                    parts.append(
                        f'                <textarea class="day-feedback" name="student_note" rows="2" placeholder="Pesos usados / sensaciones">{student_note}</textarea>'
                    )
                    parts.append(
                        '                <button class="btn glass ghost small" type="submit">Guardar</button>'
                    )
                    parts.append("              </form>")
                    parts.append("            </div>")
                parts.append("          </div>")
            parts.append('        </div>')
        parts.append("      </div>")
        parts.append('      <form class="week-summary" action="/portal/week/update" method="post">')
        parts.append(f'        <input type="hidden" name="week" value="{week_index}">')
        parts.append('        <label>Resumen semanal</label>')
        parts.append(
            f'        <textarea name="summary" rows="3" placeholder="Resumen de la semana">{week_summary}</textarea>'
        )
        parts.append('        <button class="btn glass ghost small" type="submit">Guardar resumen</button>')
        parts.append("      </form>")
        parts.append("      </div>")
        parts.append("    </details>")
    parts.append("  </div>")
    parts.append("</div>")
    parts.append(
        f'<input type="hidden" id="portal_week_current" value="{active_week if active_week else "all"}">'
    )
    return "\n".join(parts)


def render_submission_media(submission: dict) -> str:
    file_name = submission.get("file") or ""
    video_url = submission.get("video_url") or ""
    if file_name:
        ext = Path(file_name).suffix.lower()
        src = f"/uploads/{file_name}"
        if ext in ALLOWED_IMAGE_EXT:
            return (
                f'<img src="{html.escape(src)}" alt="{html.escape(submission.get("title", ""))}" '
                'loading="lazy" decoding="async">'
            )
        return (
            f'<video data-src="{html.escape(src)}" autoplay loop muted playsinline preload="none"></video>'
        )
    if video_url:
        return (
            f'<a class="btn glass ghost small" href="{html.escape(video_url)}" '
            f'target="_blank" rel="noopener">Ver vídeo</a>'
        )
    return PLACEHOLDER_SVG


def render_submission_comments(comments: list[dict]) -> str:
    if not comments:
        return '<p class="form-note">Sin comentarios todavía.</p>'
    items = []
    for comment in comments:
        text = html.escape(comment.get("text", ""))
        created = format_date(comment.get("created_at", 0))
        items.append(f'<li><span>{created}</span><p>{text}</p></li>')
    return f'<ul class="comment-list">{"".join(items)}</ul>'


def render_user_submissions(submissions: list[dict], username: str) -> str:
    cards = []
    for sub in submissions:
        if sub.get("username") != username:
            continue
        title = html.escape(sub.get("title", "Envío"))
        desc = html.escape(sub.get("description", ""))
        created = format_date(sub.get("created_at", 0))
        media = render_submission_media(sub)
        comments_html = render_submission_comments(sub.get("comments", []))
        cards.append(
            "\n".join(
                [
                    '<div class="submission-card glass-card stagger-item">',
                    f"  <div class=\"submission-head\"><h4>{title}</h4><span>{created}</span></div>",
                    f"  <p>{desc}</p>",
                    f"  <div class=\"submission-media\">{media}</div>",
                    f"  <div class=\"submission-comments\">{comments_html}</div>",
                    "</div>",
                ]
            )
        )
    return "\n".join(cards) if cards else "<p class=\"form-note\">Aún no tienes envíos.</p>"


def render_admin_submissions(submissions: list[dict]) -> str:
    cards = []
    for sub in submissions:
        raw_id = sub.get("id", "")
        sub_id = html.escape(raw_id)
        comment_id = html.escape(f"comment_{raw_id}")
        username = html.escape(sub.get("username", ""))
        title = html.escape(sub.get("title", "Envío"))
        desc = html.escape(sub.get("description", ""))
        created = format_date(sub.get("created_at", 0))
        media = render_submission_media(sub)
        comments_html = render_submission_comments(sub.get("comments", []))
        cards.append(
            "\n".join(
                [
                    '<div class="submission-card glass-card stagger-item">',
                    f"  <div class=\"submission-head\"><h4>{title}</h4><span>{created}</span></div>",
                    f"  <p class=\"submission-user\">Alumno: {username}</p>",
                    f"  <p>{desc}</p>",
                    f"  <div class=\"submission-media\">{media}</div>",
                    f"  <div class=\"submission-comments\">{comments_html}</div>",
                    "  <form class=\"admin-form\" action=\"/admin/submissions/comment\" method=\"post\">",
                    f"    <input type=\"hidden\" name=\"id\" value=\"{sub_id}\">",
                    "    <div class=\"form-field\">",
                    f"      <label for=\"{comment_id}\">Comentario técnico</label>",
                    f"      <textarea id=\"{comment_id}\" name=\"comment\" rows=\"3\" required></textarea>",
                    "    </div>",
                    "    <button class=\"btn glass primary small\" type=\"submit\">Enviar comentario</button>",
                    "  </form>",
                    "  <form class=\"admin-form\" action=\"/admin/submissions/delete\" method=\"post\">",
                    f"    <input type=\"hidden\" name=\"id\" value=\"{sub_id}\">",
                    "    <button class=\"btn glass ghost small\" type=\"submit\">Eliminar envío</button>",
                    "  </form>",
                    "</div>",
                ]
            )
        )
    return "\n".join(cards) if cards else "<p class=\"form-note\">Sin envíos todavía.</p>"


def render_forgot_password_block(prefix: str) -> str:
    safe_prefix = re.sub(r"[^a-z0-9_-]", "", prefix.lower()) or "reset"
    user_id = f"{safe_prefix}_reset_user"
    email_id = f"{safe_prefix}_reset_email"
    return "\n".join(
        [
            '<details class="forgot-password-block">',
            "  <summary>¿Olvidaste tu contraseña?</summary>",
            '  <form class="admin-form" action="/password/forgot" method="post">',
            '    <div class="form-row">',
            '      <div class="form-field">',
            f'        <label for="{user_id}">Usuario</label>',
            f'        <input id="{user_id}" name="username" type="text" required>',
            "      </div>",
            '      <div class="form-field">',
            f'        <label for="{email_id}">Email</label>',
            f'        <input id="{email_id}" name="email" type="email" required>',
            "      </div>",
            "    </div>",
            '    <button class="btn glass ghost small" type="submit">Enviar enlace</button>',
            '    <p class="form-note">Usa el mismo usuario y correo con el que te registraste.</p>',
            "  </form>",
            "</details>",
        ]
    )


def render_password_reset_page(query: dict[str, list[str]]) -> str:
    token = (query.get("token") or [""])[0].strip()
    access_status = (query.get("access") or [""])[0]
    reset_data = peek_password_reset_token(token) if token else None

    if not access_status and token and not reset_data:
        access_status = "user_reset_invalid"
    alert = build_access_alert(access_status, "user")

    if reset_data:
        username = html.escape(str(reset_data.get("username", "")))
        card = "\n".join(
            [
                '<div class="admin-login glass-card">',
                "  <h2>Restablecer contraseña</h2>",
                f"  {alert}" if alert else "",
                f"  <p>Vas a actualizar la contraseña de <strong>{username}</strong>.</p>",
                '  <form class="admin-form" action="/password/reset" method="post">',
                f'    <input type="hidden" name="token" value="{html.escape(token)}">',
                '    <div class="form-field">',
                '      <label for="reset_password">Nueva contraseña</label>',
                '      <input id="reset_password" name="password" type="password" required>',
                "    </div>",
                '    <div class="form-field">',
                '      <label for="reset_password_confirm">Repite la contraseña</label>',
                '      <input id="reset_password_confirm" name="password_confirm" type="password" required>',
                "    </div>",
                '    <button class="btn glass primary" type="submit">Guardar contraseña</button>',
                "  </form>",
                '  <a class="btn glass ghost small" href="/portal">Volver al acceso</a>',
                "</div>",
            ]
        )
    else:
        fallback_alert = alert or build_access_alert("user_reset_invalid", "user")
        card = "\n".join(
            [
                '<div class="admin-login glass-card">',
                "  <h2>Restablecer contraseña</h2>",
                f"  {fallback_alert}" if fallback_alert else "",
                "  <p>Solicita un nuevo enlace desde el acceso a tu Área Privada.</p>",
                '  <a class="btn glass primary" href="/portal">Ir al portal</a>',
                "</div>",
            ]
        )

    return "\n".join(
        [
            "<!doctype html>",
            "<html lang=\"es\">",
            "  <head>",
            "    <meta charset=\"utf-8\">",
            "    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">",
            "    <title>Restablecer contraseña - AuraCalistenia</title>",
            "    <link rel=\"preconnect\" href=\"https://fonts.googleapis.com\">",
            "    <link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin>",
            "    <link href=\"https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Space+Grotesk:wght@300;400;500;600;700&display=swap\" rel=\"stylesheet\">",
            "    <link rel=\"stylesheet\" href=\"/styles.css?v=20260219-1\">",
            "  </head>",
            "  <body class=\"admin-body\">",
            "    <div class=\"noise\" aria-hidden=\"true\"></div>",
            "    <header class=\"nav\">",
            "      <div class=\"nav-inner\">",
            "        <nav class=\"nav-group nav-left\"></nav>",
            "        <a class=\"nav-brand\" href=\"/\" aria-label=\"AuraCalistenia\">",
            "          <span class=\"brand-mark\" aria-hidden=\"true\"></span>",
            "        </a>",
            "        <nav class=\"nav-group nav-right\">",
            "          <a href=\"/\">Inicio</a>",
            "          <a href=\"/portal\">Portal</a>",
            "        </nav>",
            "        <nav class=\"nav-group nav-compact\" aria-label=\"Navegación\">",
            "          <a href=\"/\">Inicio</a>",
            "          <a href=\"/portal\">Portal</a>",
            "        </nav>",
            "      </div>",
            "    </header>",
            "    <main class=\"section\">",
            f"      {card}",
            "    </main>",
            "  </body>",
            "</html>",
        ]
    )


def render_access_section(query: dict[str, list[str]], cookie_header: str | None) -> str:
    access_status = (query.get("access") or [""])[0]
    user_alert = build_access_alert(access_status, "user")
    admin_alert = build_access_alert(access_status, "admin")
    admin_user = get_session_user(cookie_header, ADMIN_SESSION_COOKIE, "admin")
    portal_user = get_session_user(cookie_header, USER_SESSION_COOKIE, "user")

    if admin_user:
        return "\n".join(
            [
                '<div class="access-grid" data-stagger>',
                '  <div class="portal-card glass-card stagger-item">',
                "    <h3>Panel admin activo</h3>",
                f"    {admin_alert}" if admin_alert else "",
                "    <p>Puedes editar la web, eventos y alumnos desde el panel.</p>",
                '    <div class="portal-actions">',
                '      <a class="btn glass primary" href="/admin">Ir al panel admin</a>',
                '      <form class="portal-actions" action="/admin/logout" method="post">',
                '        <button class="btn glass ghost" type="submit">Cerrar sesión</button>',
                "      </form>",
                "    </div>",
                "  </div>",
                "</div>",
            ]
        )

    if portal_user:
        return "\n".join(
            [
                '<div class="access-grid" data-stagger>',
                '  <div class="portal-card glass-card stagger-item">',
                "    <h3>Panel de alumno activo</h3>",
                f"    {user_alert}" if user_alert else "",
                f"    <p>Bienvenido, {html.escape(portal_user)}.</p>",
                '    <div class="portal-actions">',
                '      <a class="btn glass primary" href="/portal">Ver mi plan</a>',
                '      <form class="portal-actions" action="/logout" method="post">',
                '        <button class="btn glass ghost" type="submit">Cerrar sesión</button>',
                "      </form>",
                "    </div>",
                "  </div>",
                "</div>",
            ]
        )

    alert = user_alert or admin_alert
    forgot_block = render_forgot_password_block("home")
    login_card = "\n".join(
        [
            '<div class="portal-card glass-card stagger-item">',
            "  <h3>Acceso a tu Área Privada</h3>",
            "  <p>Usa tus credenciales de alumno o admin.</p>",
            f"  {alert}" if alert else "",
            "  <form class=\"admin-form\" action=\"/login\" method=\"post\">",
            "    <div class=\"form-field\">",
            "      <label for=\"portal_user\">Usuario</label>",
            "      <input id=\"portal_user\" name=\"username\" type=\"text\" required>",
            "    </div>",
            "    <div class=\"form-field\">",
            "      <label for=\"portal_pass\">Contraseña</label>",
            "      <input id=\"portal_pass\" name=\"password\" type=\"password\" required>",
            "    </div>",
            "    <button class=\"btn glass primary\" type=\"submit\">Entrar</button>",
            "  </form>",
            forgot_block,
            "</div>",
        ]
    )
    return f'<div class="access-grid" data-stagger>{login_card}</div>'


def render_events(events: list[dict]) -> str:
    parts = []
    for event in events:
        date_text = f"{event.get('date', '')} - {event.get('location', '')}".strip(" -")
        parts.append(
            "\n".join(
                [
                    '<article class="news-card glass-card stagger-item">',
                    f"  <span class=\"news-date\">{html.escape(date_text)}</span>",
                    f"  <h3>{html.escape(event.get('title', ''))}</h3>",
                    f"  <p>{html.escape(event.get('description', ''))}</p>",
                    f"  <span class=\"news-tag\">{html.escape(event.get('tag', ''))}</span>",
                    "</article>",
                ]
            )
        )
    return "\n".join(parts)


def render_video_media(video: dict) -> str:
    file_name = video.get("file") or ""
    video_url = video.get("video_url") or ""
    if file_name:
        ext = Path(file_name).suffix.lower()
        src = f"/uploads/{file_name}"
        if ext in ALLOWED_IMAGE_EXT:
            return (
                f'<img src="{html.escape(src)}" alt="{html.escape(video.get("title", ""))}" '
                'loading="lazy" decoding="async">'
            )
        return (
            f'<video data-src="{html.escape(src)}" autoplay loop muted playsinline preload="none"></video>'
        )
    if video_url:
        ext = Path(video_url).suffix.lower()
        src = html.escape(video_url)
        if ext in ALLOWED_IMAGE_EXT:
            return (
                f'<img src="{src}" alt="{html.escape(video.get("title", ""))}" '
                'loading="lazy" decoding="async">'
            )
        if ext in ALLOWED_VIDEO_EXT:
            return f'<video data-src="{src}" autoplay loop muted playsinline preload="none"></video>'
    return PLACEHOLDER_SVG


def render_video_cards(videos: list[dict]) -> str:
    parts = []
    for video in videos:
        layout = video.get("layout", "")
        layout_class = ""
        if layout in {"tall", "wide"}:
            layout_class = f" {layout}"
        media_html = render_video_media(video)
        video_url = video.get("video_url") or ""
        link_html = ""
        if video_url:
            link_html = (
                f'<a class="video-link glass-pill" href="{html.escape(video_url)}" '
                f'target="_blank" rel="noopener">Ver clip</a>'
            )
        parts.append(
            "\n".join(
                [
                    f'<div class="video-card{layout_class} stagger-item">',
                    '  <div class="video-thumb">',
                    f"    {media_html}",
                    f"    {link_html}",
                    "  </div>",
                    "  <div class=\"video-meta\">",
                    f"    <span class=\"tag glass-pill\">{html.escape(video.get('tag', ''))}</span>",
                    f"    <h3>{html.escape(video.get('title', ''))}</h3>",
                    f"    <p>{html.escape(video.get('description', ''))}</p>",
                    "  </div>",
                    "</div>",
                ]
            )
        )
    return "\n".join(parts)


def render_event_list(events: list[dict]) -> str:
    items = []
    total = len(events)
    for index, event in enumerate(events):
        event_id = str(event.get("id", ""))
        raw_title = str(event.get("title", "")).strip()
        raw_date = str(event.get("date", "")).strip()
        raw_location = str(event.get("location", "")).strip()
        raw_description = str(event.get("description", "")).strip()
        raw_tag = str(event.get("tag", "")).strip()
        title = html.escape(raw_title)
        date = html.escape(raw_date)
        location = html.escape(raw_location)
        description = html.escape(raw_description)
        tag = html.escape(raw_tag)
        summary_parts = [part for part in [raw_date, raw_location] if part]
        summary = html.escape(" · ".join(summary_parts)) if summary_parts else "Sin fecha ni lugar"
        title_display = title or "Competición sin título"
        tag_display = tag or "Sin etiqueta"
        open_attr = " open" if index == 0 else ""
        move_up_disabled = " disabled" if index == 0 else ""
        move_down_disabled = " disabled" if index == total - 1 else ""
        items.append(
            "\n".join(
                [
                    '<li class="admin-item admin-edit-item admin-collapsible-item">',
                    f'  <details class="admin-collapsible"{open_attr}>',
                    '    <summary class="admin-collapsible-summary">',
                    '      <div class="admin-collapsible-main">',
                    f"        <strong>{title_display}</strong>",
                    f"        <span>{summary}</span>",
                    "      </div>",
                    f"      <span class=\"admin-collapsible-tag\">{tag_display}</span>",
                    "    </summary>",
                    '    <div class="admin-collapsible-content">',
                    "      <form class=\"admin-form admin-inline-edit\" action=\"/admin/events/update\" method=\"post\">",
                    f"        <input type=\"hidden\" name=\"id\" value=\"{html.escape(event_id)}\">",
                    "        <div class=\"form-row\">",
                    "          <div class=\"form-field\">",
                    "            <label>Título</label>",
                    f"            <input name=\"title\" type=\"text\" value=\"{title}\" required>",
                    "          </div>",
                    "          <div class=\"form-field\">",
                    "            <label>Etiqueta</label>",
                    f"            <input name=\"tag\" type=\"text\" value=\"{tag}\" required>",
                    "          </div>",
                    "        </div>",
                    "        <div class=\"form-row\">",
                    "          <div class=\"form-field\">",
                    "            <label>Fecha</label>",
                    f"            <input name=\"date\" type=\"text\" value=\"{date}\" required>",
                    "          </div>",
                    "          <div class=\"form-field\">",
                    "            <label>Lugar</label>",
                    f"            <input name=\"location\" type=\"text\" value=\"{location}\" required>",
                    "          </div>",
                    "        </div>",
                    "        <div class=\"form-field\">",
                    "          <label>Descripción</label>",
                    f"          <input name=\"description\" type=\"text\" value=\"{description}\" required>",
                    "        </div>",
                    "        <div class=\"admin-actions\">",
                    "          <button class=\"btn glass primary small\" type=\"submit\">Guardar</button>",
                    "        </div>",
                    "      </form>",
                    "      <div class=\"admin-actions\">",
                    "        <form class=\"admin-inline-form\" action=\"/admin/events/move\" method=\"post\">",
                    f"          <input type=\"hidden\" name=\"id\" value=\"{html.escape(event_id)}\">",
                    "          <input type=\"hidden\" name=\"direction\" value=\"up\">",
                    f"          <button class=\"btn glass ghost small\" type=\"submit\"{move_up_disabled}>Subir</button>",
                    "        </form>",
                    "        <form class=\"admin-inline-form\" action=\"/admin/events/move\" method=\"post\">",
                    f"          <input type=\"hidden\" name=\"id\" value=\"{html.escape(event_id)}\">",
                    "          <input type=\"hidden\" name=\"direction\" value=\"down\">",
                    f"          <button class=\"btn glass ghost small\" type=\"submit\"{move_down_disabled}>Bajar</button>",
                    "        </form>",
                    "        <form class=\"admin-inline-form\" action=\"/admin/events/delete\" method=\"post\">",
                    f"          <input type=\"hidden\" name=\"id\" value=\"{html.escape(event_id)}\">",
                    "          <button class=\"btn glass ghost small\" type=\"submit\">Eliminar</button>",
                    "        </form>",
                    "      </div>",
                    "    </div>",
                    "  </details>",
                    "</li>",
                ]
            )
        )
    return "\n".join(items) if items else "<li class=\"admin-item\">Sin competiciones.</li>"


def render_video_list(videos: list[dict]) -> str:
    items = []
    total = len(videos)
    for index, video in enumerate(videos):
        video_id = str(video.get("id", ""))
        raw_title = str(video.get("title", "")).strip()
        raw_tag = str(video.get("tag", "")).strip()
        raw_description = str(video.get("description", "")).strip()
        raw_layout = str(video.get("layout", "")).strip()
        raw_video_url = str(video.get("video_url", "")).strip()
        raw_file = str(video.get("file", "")).strip()
        title = html.escape(raw_title)
        tag = html.escape(raw_tag)
        description = html.escape(raw_description)
        layout = html.escape(raw_layout or "normal")
        video_url = html.escape(raw_video_url)
        file_label = html.escape(raw_file or "-")
        title_display = title or "Vídeo sin título"
        tag_display = tag or "Sin etiqueta"
        layout_label = {"tall": "Tall", "wide": "Wide"}.get(raw_layout, "Normal")
        source_label = "Archivo subido" if raw_file else ("URL externa" if raw_video_url else "Sin fuente")
        meta_summary = html.escape(f"{raw_tag or 'Sin etiqueta'} · {layout_label} · {source_label}")
        search_blob = html.escape(
            " ".join([raw_title, raw_tag, raw_description, raw_video_url, raw_file]).lower()
        )
        open_attr = " open" if index == 0 else ""
        move_up_disabled = " disabled" if index == 0 else ""
        move_down_disabled = " disabled" if index == total - 1 else ""
        layout_options = "".join(
            [
                f'<option value=""{" selected" if raw_layout == "" else ""}>Normal</option>',
                f'<option value="tall"{" selected" if raw_layout == "tall" else ""}>Tall</option>',
                f'<option value="wide"{" selected" if raw_layout == "wide" else ""}>Wide</option>',
            ]
        )
        items.append(
            "\n".join(
                [
                    f'<li class="admin-item admin-edit-item admin-collapsible-item admin-media-item" data-search="{search_blob}">',
                    f'  <details class="admin-collapsible"{open_attr}>',
                    '    <summary class="admin-collapsible-summary">',
                    '      <div class="admin-collapsible-main">',
                    f"        <strong>{title_display}</strong>",
                    f"        <span>{meta_summary}</span>",
                    "      </div>",
                    f"      <span class=\"admin-collapsible-tag\">{layout}</span>",
                    "    </summary>",
                    '    <div class="admin-collapsible-content">',
                    "      <form class=\"admin-form admin-inline-edit\" action=\"/admin/videos/update\" method=\"post\" enctype=\"multipart/form-data\">",
                    f"        <input type=\"hidden\" name=\"id\" value=\"{html.escape(video_id)}\">",
                    "        <div class=\"form-row\">",
                    "          <div class=\"form-field\">",
                    "            <label>Título</label>",
                    f"            <input name=\"title\" type=\"text\" value=\"{title}\" required>",
                    "          </div>",
                    "          <div class=\"form-field\">",
                    "            <label>Etiqueta</label>",
                    f"            <input name=\"tag\" type=\"text\" value=\"{tag}\" required>",
                    "          </div>",
                    "        </div>",
                    "        <div class=\"form-row\">",
                    "          <div class=\"form-field\">",
                    "            <label>Descripción</label>",
                    f"            <input name=\"description\" type=\"text\" value=\"{description}\" required>",
                    "          </div>",
                    "          <div class=\"form-field\">",
                    "            <label>Diseño</label>",
                    f"            <select name=\"layout\">{layout_options}</select>",
                    "          </div>",
                    "        </div>",
                    "        <div class=\"form-row\">",
                    "          <div class=\"form-field\">",
                    "            <label>URL externa</label>",
                    f"            <input name=\"video_url\" type=\"text\" value=\"{video_url}\">",
                    "          </div>",
                    "          <div class=\"form-field\">",
                    "            <label>Archivo actual</label>",
                    f"            <input type=\"text\" value=\"{file_label}\" readonly>",
                    "          </div>",
                    "        </div>",
                    "        <div class=\"form-row\">",
                    "          <div class=\"form-field\">",
                    "            <label>Reemplazar archivo</label>",
                    "            <input name=\"video_file\" type=\"file\" accept=\"video/mp4,video/webm,video/ogg,image/png,image/jpeg,image/webp\">",
                    "          </div>",
                    "          <div class=\"form-field\">",
                    "            <label>Eliminar archivo actual</label>",
                    "            <label class=\"checkbox-field\"><input type=\"checkbox\" name=\"remove_file\"> Quitar archivo subido</label>",
                    "          </div>",
                    "        </div>",
                    "        <div class=\"admin-actions\">",
                    "          <button class=\"btn glass primary small\" type=\"submit\">Guardar</button>",
                    "        </div>",
                    "      </form>",
                    "      <div class=\"admin-actions\">",
                    "        <form class=\"admin-inline-form\" action=\"/admin/videos/move\" method=\"post\">",
                    f"          <input type=\"hidden\" name=\"id\" value=\"{html.escape(video_id)}\">",
                    "          <input type=\"hidden\" name=\"direction\" value=\"up\">",
                    f"          <button class=\"btn glass ghost small\" type=\"submit\"{move_up_disabled}>Subir</button>",
                    "        </form>",
                    "        <form class=\"admin-inline-form\" action=\"/admin/videos/move\" method=\"post\">",
                    f"          <input type=\"hidden\" name=\"id\" value=\"{html.escape(video_id)}\">",
                    "          <input type=\"hidden\" name=\"direction\" value=\"down\">",
                    f"          <button class=\"btn glass ghost small\" type=\"submit\"{move_down_disabled}>Bajar</button>",
                    "        </form>",
                    "        <form class=\"admin-inline-form\" action=\"/admin/videos/delete\" method=\"post\">",
                    f"          <input type=\"hidden\" name=\"id\" value=\"{html.escape(video_id)}\">",
                    "          <button class=\"btn glass ghost small\" type=\"submit\">Eliminar</button>",
                    "        </form>",
                    "      </div>",
                    "      <span class=\"admin-note\">Etiqueta actual: "
                    f"{tag_display} · Diseño: {layout}</span>",
                    "    </div>",
                    "  </details>",
                    "</li>",
                ]
            )
        )
    return "\n".join(items) if items else "<li class=\"admin-item\">Sin vídeos.</li>"


def render_stats(stats: list[dict]) -> str:
    items = []
    for stat in stats:
        value = html.escape(str(stat.get("value", "")))
        label = html.escape(str(stat.get("label", "")))
        if not value and not label:
            continue
        items.append(
            "\n".join(
                [
                    '<div class="stat glass-card stagger-item">',
                    f"  <span class=\"stat-number\">{value}</span>",
                    f"  <span class=\"stat-label\">{label}</span>",
                    "</div>",
                ]
            )
        )
    return "\n".join(items)


def render_paragraphs(paragraphs: list[str]) -> str:
    return "\n".join([f"<p>{html.escape(text)}</p>" for text in paragraphs if str(text).strip()])


def render_bullets(items: list[str]) -> str:
    return "\n".join([f"<li>{html.escape(text)}</li>" for text in items if str(text).strip()])


def render_sponsors(sponsors: list[dict]) -> str:
    cards = []
    for sponsor in sponsors:
        name = html.escape(str(sponsor.get("name", "")))
        logo = html.escape(str(sponsor.get("logo", "")))
        url = html.escape(str(sponsor.get("url", "")).strip())
        if not name or not logo:
            continue
        open_tag = '<div class="sponsor-tile glass-card stagger-item">'
        close_tag = "</div>"
        if url:
            open_tag = (
                f'<a class="sponsor-tile sponsor-link glass-card stagger-item" href="{url}" '
                'target="_blank" rel="noopener noreferrer">'
            )
            close_tag = "</a>"
        cards.append(
            "\n".join(
                [
                    open_tag,
                    f"  <img class=\"sponsor-logo\" src=\"{logo}\" alt=\"{name}\" loading=\"lazy\" decoding=\"async\">",
                    f"  <span class=\"sponsor-name\">{name}</span>",
                    "  <p class=\"sponsor-offer\">10% de descuento con el código <strong>FITA10</strong></p>",
                    close_tag,
                ]
            )
        )
    return "\n".join(cards)


def render_index(query: dict[str, list[str]], cookie_header: str | None) -> str:
    events = load_json(EVENTS_PATH, [])
    videos = load_json(VIDEOS_PATH, [])
    content = load_content()
    hero = content.get("hero", {})
    bio = content.get("bio", {})
    program = content.get("program", {})
    contact = content.get("contact", {})
    stats_html = render_stats(content.get("stats", []))
    bio_paragraphs = render_paragraphs(bio.get("paragraphs", []))
    program_bullets = render_bullets(program.get("bullets", []))
    sponsors_html = render_sponsors(content.get("sponsors", []))
    replacements = {
        "EVENTS": render_events(events),
        "VIDEOS": render_video_cards(videos),
        "FORM_ALERT": build_form_alert(query),
        "ACCESS_CONTENT": render_access_section(query, cookie_header),
        "HERO_EYEBROW": html.escape(hero.get("eyebrow", "")),
        "HERO_TITLE": html.escape(hero.get("title", "")),
        "HERO_SUBTITLE": html.escape(hero.get("subtitle", "")),
        "HERO_STATS": stats_html,
        "BIO_EYEBROW": html.escape(bio.get("eyebrow", "")),
        "BIO_NAME": html.escape(bio.get("name", "")),
        "BIO_PARAGRAPHS": bio_paragraphs,
        "BIO_SIGNATURE": html.escape(bio.get("signature", "")),
        "BIO_IMAGE": html.escape(bio.get("image", "")),
        "BIO_IMAGE_CAPTION": html.escape(bio.get("image_caption", "")),
        "PROGRAM_TITLE": html.escape(program.get("title", "")),
        "PROGRAM_LEAD": html.escape(program.get("lead", "")),
        "PROGRAM_HIGHLIGHT_TITLE": html.escape(program.get("highlight_title", "")),
        "PROGRAM_HIGHLIGHT_TEXT": html.escape(program.get("highlight_text", "")),
        "PROGRAM_BULLETS": program_bullets,
        "PROGRAM_IMAGE": html.escape(program.get("image", "")),
        "PROGRAM_IMAGE_CAPTION": html.escape(program.get("image_caption", "")),
        "SPONSORS": sponsors_html,
        "CONTACT_EMAIL": html.escape(contact.get("email", "")),
        "CONTACT_PHONE": html.escape(contact.get("phone", "")),
        "CONTACT_CITY": html.escape(contact.get("city", "")),
        "CONTACT_INSTAGRAM": html.escape(contact.get("instagram", "")),
    }
    return render_template(INDEX_TEMPLATE, replacements)


def render_plan_editor(applications: list[dict], selected_user: str, expanded: bool = False) -> str:
    if not applications:
        return (
            '<div class="admin-card glass-card admin-wide">'
            "<h3>Plan de entrenamiento</h3>"
            '<p class="admin-note">No hay alumnos registrados todavía.</p>'
            "</div>"
        )

    if not selected_user:
        selected_user = applications[0].get("username", "")
    selected_app = find_application(applications, selected_user) if selected_user else None
    if not selected_app and applications:
        selected_user = applications[0].get("username", "")
        selected_app = applications[0]
    plan = normalize_plan((selected_app or {}).get("plan"))

    selector_items = []
    for app in applications:
        username = app.get("username", "")
        label = html.escape(username)
        href = (
            f"/admin?admin_section=portal&plan_user={urllib.parse.quote(username)}#plan"
        )
        selector_items.append(f'<a class="glass-pill" href="{href}">{label}</a>')
    selector_html = (
        f'<div class="user-selector"><span>Selecciona alumno:</span>{"".join(selector_items)}</div>'
    )
    plan_data = {}
    progress_data = {}
    chat_data = {}
    for app in applications:
        username = app.get("username", "")
        if not username:
            continue
        progress_data[username] = build_progress_payload(app.get("plan", {}))
        chat_data[username] = load_chat_messages(username)
        cleaned_plan = normalize_plan(app.get("plan"))
        for week in cleaned_plan.get("weeks", []):
            week["summary"] = ""
            for day in week.get("days", []):
                day["status"] = ""
                day["status_note"] = ""
                day["feedback"] = ""
                for item in day.get("items", []):
                    if not isinstance(item, dict):
                        continue
                    item["status"] = ""
                    item["status_note"] = ""
                    item["student_note"] = ""
        plan_data[username] = cleaned_plan
    plan_json = json.dumps(plan_data, ensure_ascii=True).replace("</", "<\\/")
    progress_json = json.dumps(progress_data, ensure_ascii=True).replace("</", "<\\/")
    chat_json = json.dumps(chat_data, ensure_ascii=True).replace("</", "<\\/")

    week_blocks = []
    for week_index, week in enumerate(plan.get("weeks", []), start=1):
        week_title = html.escape(week.get("title", f"Semana {week_index}"))
        day_cards = []
        for day_index, day in enumerate(week.get("days", []), start=1):
            day_title = html.escape(day.get("title", ""))
            rest_flag = "checked" if day.get("rest") else ""
            card_class = "plan-day-card is-rest" if day.get("rest") else "plan-day-card"
            day_text = html.escape(plan_day_to_text(day))
            day_cards.append(
                "\n".join(
                    [
                        f'<div class="{card_class}" data-week="{week_index}" data-day="{day_index}">',
                        '  <div class="plan-day-head">',
                        f'    <span class="plan-day-label">Día {day_index}</span>',
                        f'    <input class="plan-day-title" data-field="day-title" name="week{week_index}_day{day_index}_title" placeholder="Título del día" value="{day_title}">',
                        '    <label class="plan-rest-toggle">',
                        f'      <input data-field="day-rest" type="checkbox" name="week{week_index}_day{day_index}_rest" {rest_flag}> Descanso',
                        "    </label>",
                        '    <div class="plan-day-actions">',
                        '      <button type="button" class="plan-day-move" data-action="left" aria-label="Mover día a la izquierda" title="Mover día a la izquierda">←</button>',
                        '      <button type="button" class="plan-day-move" data-action="right" aria-label="Mover día a la derecha" title="Mover día a la derecha">→</button>',
                        '      <button type="button" class="plan-day-clear" aria-label="Vaciar día" title="Vaciar día">🧹</button>',
                        "    </div>",
                        "  </div>",
                        '  <div class="plan-day-editor-wrap">',
                        '    <p class="plan-day-help">Una línea por ejercicio: Ejercicio | Series | Reps | Peso | Descanso | Notas</p>',
                        f'    <textarea class="plan-day-editor" data-field="day-text" name="week{week_index}_day{day_index}_text" rows="8" placeholder="Dominadas | 4 | 8 | 20kg | 90s | Técnica estricta">{day_text}</textarea>',
                        "  </div>",
                        '  <p class="plan-rest-note">Descanso / movilidad</p>',
                        "</div>",
                    ]
                )
            )
        week_blocks.append(
            "\n".join(
                [
                    f'<div class="plan-week-block" data-week="{week_index}">',
                    '  <div class="plan-week-head">',
                    f'    <div class="plan-week-title-field"><label for="week{week_index}_title">Semana {week_index} - título</label>',
                    f'    <input id="week{week_index}_title" name="week{week_index}_title" type="text" value="{week_title}"></div>',
                    '    <div class="plan-week-actions">',
                    '      <button type="button" class="btn glass ghost small plan-week-move" data-action="up" title="Subir semana">Subir semana</button>',
                    '      <button type="button" class="btn glass ghost small plan-week-move" data-action="down" title="Bajar semana">Bajar semana</button>',
                    '      <button type="button" class="btn glass ghost small plan-week-action" data-action="duplicate" title="Duplicar semana">Duplicar</button>',
                    '      <button type="button" class="btn glass ghost small plan-week-action" data-action="clear" title="Vaciar semana">Vaciar</button>',
                    "    </div>",
                    "  </div>",
                    '  <div class="plan-days-row">',
                    "\n".join(day_cards),
                    "  </div>",
                    "</div>",
                ]
            )
        )
    progress_card_html = "\n".join(
        [
            '<div class="coach-progress-card">',
            "  <h4>Progreso del alumno</h4>",
            '  <div class="coach-progress-tools">',
            '    <label for="coach_progress_week">Semana</label>',
            '    <select id="coach_progress_week">',
            '      <option value="1">Semana 1</option>',
            '      <option value="2">Semana 2</option>',
            '      <option value="3">Semana 3</option>',
            '      <option value="4">Semana 4</option>',
            "    </select>",
            "  </div>",
            '  <div class="coach-progress-content">',
            '    <div id="coach_progress_donut" class="coach-progress-donut"><span id="coach_progress_pct">0%</span></div>',
            '    <div class="coach-progress-kpis">',
            '      <span class="ok">✓ Completados: <strong id="coach_progress_done">0</strong></span>',
            '      <span class="bad">✕ Fallados: <strong id="coach_progress_missed">0</strong></span>',
            '      <span class="wait">⏳ Pendientes: <strong id="coach_progress_pending">0</strong></span>',
            "    </div>",
            "  </div>",
            "</div>",
        ]
    )
    chat_panel_html = render_chat_panel(selected_user, "admin") if selected_user else ""
    open_attr = " open" if expanded else ""

    return "\n".join(
        [
            '<div id="plan" class="admin-card glass-card admin-wide">',
            f'  <details class="admin-collapsible admin-main-collapsible"{open_attr}>',
            '    <summary class="admin-collapsible-summary admin-main-summary">',
            '      <div class="admin-collapsible-main">',
            "        <strong>Plan de entrenamiento por alumno</strong>",
            f"        <span>Alumno actual: {html.escape(selected_user)}</span>",
            "      </div>",
            '      <span class="admin-collapsible-tag">Plan</span>',
            "    </summary>",
            '    <div class="admin-collapsible-content">',
            '      <div class="plan-editor">',
            selector_html,
            progress_card_html,
            "  <div class=\"plan-tools\">",
            "    <div class=\"plan-tool-row\">",
            f"      <span class=\"plan-current-user\">Alumno actual: <strong>{html.escape(selected_user)}</strong></span>",
            "      <label for=\"plan_user_select\">Cambiar alumno:</label>",
            "      <select id=\"plan_user_select\">"
            + "".join(
                [
                    (
                        f'<option value="{html.escape(app.get("username",""))}"'
                        f'{" selected" if app.get("username","") == selected_user else ""}>'
                        f'{html.escape(app.get("username",""))}</option>'
                    )
                    for app in applications
                ]
            )
            + "</select>",
            '      <button type="button" class="btn glass ghost small" id="load_user_btn">Cargar</button>',
            "      <span class=\"plan-tool-note\">Guarda antes de cambiar para no perder cambios.</span>",
            "    </div>",
            '    <details class="plan-tools-advanced">',
            "      <summary>Herramientas avanzadas (copiar y mover)</summary>",
            "    <div class=\"plan-tool-row\">",
            "      <label>Copiar semana:</label>",
            "      <select id=\"copy_plan_user\">"
            + "".join([f'<option value="{html.escape(app.get("username",""))}">{html.escape(app.get("username",""))}</option>' for app in applications])
            + "</select>",
            "      <select id=\"copy_plan_week\">"
            + "".join([f'<option value="{i}">Semana {i}</option>' for i in range(1, 5)])
            + "</select>",
            "      <span>→</span>",
            "      <select id=\"copy_target_user\">"
            + "".join(
                [
                    (
                        f'<option value="{html.escape(app.get("username",""))}"'
                        f'{" selected" if app.get("username","") == selected_user else ""}>'
                        f'{html.escape(app.get("username",""))}</option>'
                    )
                    for app in applications
                ]
            )
            + "</select>",
            "      <select id=\"copy_target_week\">"
            + "".join([f'<option value="{i}">Semana {i}</option>' for i in range(1, 5)])
            + "</select>",
            '      <button type="button" class="btn glass ghost small" id="copy_week_btn">Copiar</button>',
            "    </div>",
            "    <div class=\"plan-tool-row\">",
            "      <label>Copiar día:</label>",
            "      <select id=\"copy_day_user\">"
            + "".join([f'<option value="{html.escape(app.get("username",""))}">{html.escape(app.get("username",""))}</option>' for app in applications])
            + "</select>",
            "      <select id=\"copy_day_week\">"
            + "".join([f'<option value="{i}">Semana {i}</option>' for i in range(1, 5)])
            + "</select>",
            "      <select id=\"copy_day_day\">"
            + "".join([f'<option value="{i}">Día {i}</option>' for i in range(1, 8)])
            + "</select>",
            "      <span>→</span>",
            "      <select id=\"copy_day_target_user\">"
            + "".join(
                [
                    (
                        f'<option value="{html.escape(app.get("username",""))}"'
                        f'{" selected" if app.get("username","") == selected_user else ""}>'
                        f'{html.escape(app.get("username",""))}</option>'
                    )
                    for app in applications
                ]
            )
            + "</select>",
            "      <select id=\"copy_day_target_week\">"
            + "".join([f'<option value="{i}">Semana {i}</option>' for i in range(1, 5)])
            + "</select>",
            "      <select id=\"copy_day_target_day\">"
            + "".join([f'<option value="{i}">Día {i}</option>' for i in range(1, 8)])
            + "</select>",
            '      <button type="button" class="btn glass ghost small" id="copy_day_btn">Copiar</button>',
            "    </div>",
            "    <div class=\"plan-tool-row\">",
            "      <label>Mover día:</label>",
            "      <select id=\"move_day_week_from\">"
            + "".join([f'<option value="{i}">Semana {i}</option>' for i in range(1, 5)])
            + "</select>",
            "      <select id=\"move_day_from\">"
            + "".join([f'<option value="{i}">Día {i}</option>' for i in range(1, 8)])
            + "</select>",
            "      <span>→</span>",
            "      <select id=\"move_day_week_to\">"
            + "".join([f'<option value="{i}">Semana {i}</option>' for i in range(1, 5)])
            + "</select>",
            "      <select id=\"move_day_to\">"
            + "".join([f'<option value="{i}">Día {i}</option>' for i in range(1, 8)])
            + "</select>",
            '      <button type="button" class="btn glass ghost small" id="move_day_btn">Mover</button>',
            '      <button type="button" class="btn glass ghost small" id="clear_day_btn">Vaciar destino</button>',
            "    </div>",
            "    </details>",
            "  </div>",
            "  <form class=\"admin-form\" action=\"/admin/plan/update\" method=\"post\">",
            f"    <input type=\"hidden\" name=\"username\" value=\"{html.escape(selected_user)}\">",
            '    <div class="form-field">',
            "      <label for=\"plan_title\">Título del plan</label>",
            f"      <input id=\"plan_title\" name=\"plan_title\" type=\"text\" value=\"{html.escape(plan.get('title', 'Plan de entrenamiento'))}\">",
            "    </div>",
            '    <div class="plan-weeks-row">',
            "\n".join(week_blocks),
            "    </div>",
            "    <button class=\"btn glass primary\" type=\"submit\">Guardar plan</button>",
            "  </form>",
            chat_panel_html,
            f'  <script type="application/json" id="plan-data">{plan_json}</script>',
            f'  <script type="application/json" id="plan-progress-data">{progress_json}</script>',
            f'  <script type="application/json" id="coach-chat-data">{chat_json}</script>',
            "      </div>",
            "    </div>",
            "  </details>",
            "</div>",
        ]
    )


def render_content_form(content: dict) -> str:
    hero = content.get("hero", {})
    bio = content.get("bio", {})
    program = content.get("program", {})
    contact = content.get("contact", {})
    stats_text = "\n".join(
        [f"{stat.get('value','')} | {stat.get('label','')}" for stat in content.get("stats", [])]
    )
    bio_paragraphs = "\n".join([str(p) for p in bio.get("paragraphs", [])])
    program_bullets = "\n".join([str(b) for b in program.get("bullets", [])])
    sponsors_text = "\n".join(
        [
            (
                f"{sponsor.get('name','')} | {sponsor.get('logo','')} | {sponsor.get('url','')}"
                if str(sponsor.get("url", "")).strip()
                else f"{sponsor.get('name','')} | {sponsor.get('logo','')}"
            )
            for sponsor in content.get("sponsors", [])
        ]
    )

    return "\n".join(
        [
            '<div class="admin-card glass-card admin-wide">',
            '  <details class="admin-collapsible admin-main-collapsible">',
            '    <summary class="admin-collapsible-summary admin-main-summary">',
            '      <div class="admin-collapsible-main">',
            "        <strong>Contenido de la web principal</strong>",
            "        <span>Hero, bio, programa, contacto y patrocinadores</span>",
            "      </div>",
            '      <span class="admin-collapsible-tag">Editar</span>',
            "    </summary>",
            '    <div class="admin-collapsible-content">',
            "      <form class=\"admin-form\" action=\"/admin/content\" method=\"post\" enctype=\"multipart/form-data\">",
            '    <div class="form-section">',
            "      <h4>Hero</h4>",
            '      <div class="form-row">',
            '        <div class="form-field">',
            "          <label for=\"hero_eyebrow\">Eyebrow</label>",
            f"          <input id=\"hero_eyebrow\" name=\"hero_eyebrow\" type=\"text\" value=\"{html.escape(hero.get('eyebrow',''))}\">",
            "        </div>",
            '        <div class="form-field">',
            "          <label for=\"hero_title\">Título</label>",
            f"          <input id=\"hero_title\" name=\"hero_title\" type=\"text\" value=\"{html.escape(hero.get('title',''))}\">",
            "        </div>",
            "      </div>",
            '      <div class="form-field">',
            "        <label for=\"hero_subtitle\">Subtítulo</label>",
            f"        <textarea id=\"hero_subtitle\" name=\"hero_subtitle\" rows=\"3\">{html.escape(hero.get('subtitle',''))}</textarea>",
            "      </div>",
            '      <div class="form-field">',
            "        <label for=\"hero_stats\">Stats (una línea por stat: valor | label)</label>",
            f"        <textarea id=\"hero_stats\" name=\"hero_stats\" rows=\"3\">{html.escape(stats_text)}</textarea>",
            "      </div>",
            "    </div>",
            '    <div class="form-section">',
            "      <h4>Bio</h4>",
            '      <div class="form-row">',
            '        <div class="form-field">',
            "          <label for=\"bio_eyebrow\">Eyebrow</label>",
            f"          <input id=\"bio_eyebrow\" name=\"bio_eyebrow\" type=\"text\" value=\"{html.escape(bio.get('eyebrow',''))}\">",
            "        </div>",
            '        <div class="form-field">',
            "          <label for=\"bio_name\">Nombre</label>",
            f"          <input id=\"bio_name\" name=\"bio_name\" type=\"text\" value=\"{html.escape(bio.get('name',''))}\">",
            "        </div>",
            "      </div>",
            '      <div class="form-field">',
            "        <label for=\"bio_paragraphs\">Párrafos (uno por línea)</label>",
            f"        <textarea id=\"bio_paragraphs\" name=\"bio_paragraphs\" rows=\"5\">{html.escape(bio_paragraphs)}</textarea>",
            "      </div>",
            '      <div class="form-row">',
            '        <div class="form-field">',
            "          <label for=\"bio_signature\">Firma</label>",
            f"          <input id=\"bio_signature\" name=\"bio_signature\" type=\"text\" value=\"{html.escape(bio.get('signature',''))}\">",
            "        </div>",
            '        <div class="form-field">',
            "          <label for=\"bio_image\">Imagen (ruta o URL)</label>",
            f"          <input id=\"bio_image\" name=\"bio_image\" type=\"text\" value=\"{html.escape(bio.get('image',''))}\">",
            "        </div>",
            "      </div>",
            '      <div class="form-field">',
            "        <label for=\"bio_image_file\">Subir imagen Bio (jpg/png/webp)</label>",
            "        <input id=\"bio_image_file\" name=\"bio_image_file\" type=\"file\" accept=\"image/png,image/jpeg,image/webp\">",
            "      </div>",
            '      <div class="form-field">',
            "        <label for=\"bio_image_caption\">Caption de la imagen</label>",
            f"        <input id=\"bio_image_caption\" name=\"bio_image_caption\" type=\"text\" value=\"{html.escape(bio.get('image_caption',''))}\">",
            "      </div>",
            "    </div>",
            '    <div class="form-section">',
            "      <h4>Programa</h4>",
            '      <div class="form-row">',
            '        <div class="form-field">',
            "          <label for=\"program_title\">Título</label>",
            f"          <input id=\"program_title\" name=\"program_title\" type=\"text\" value=\"{html.escape(program.get('title',''))}\">",
            "        </div>",
            '        <div class="form-field">',
            "          <label for=\"program_image\">Imagen (ruta o URL)</label>",
            f"          <input id=\"program_image\" name=\"program_image\" type=\"text\" value=\"{html.escape(program.get('image',''))}\">",
            "        </div>",
            "      </div>",
            '      <div class="form-field">',
            "        <label for=\"program_image_file\">Subir imagen Programa (jpg/png/webp)</label>",
            "        <input id=\"program_image_file\" name=\"program_image_file\" type=\"file\" accept=\"image/png,image/jpeg,image/webp\">",
            "      </div>",
            '      <div class="form-field">',
            "        <label for=\"program_lead\">Lead</label>",
            f"        <textarea id=\"program_lead\" name=\"program_lead\" rows=\"3\">{html.escape(program.get('lead',''))}</textarea>",
            "      </div>",
            '      <div class="form-row">',
            '        <div class="form-field">',
            "          <label for=\"program_highlight_title\">Título destacado</label>",
            f"          <input id=\"program_highlight_title\" name=\"program_highlight_title\" type=\"text\" value=\"{html.escape(program.get('highlight_title',''))}\">",
            "        </div>",
            '        <div class="form-field">',
            "          <label for=\"program_highlight_text\">Texto destacado</label>",
            f"          <input id=\"program_highlight_text\" name=\"program_highlight_text\" type=\"text\" value=\"{html.escape(program.get('highlight_text',''))}\">",
            "        </div>",
            "      </div>",
            '      <div class="form-row">',
            '        <div class="form-field">',
            "          <label for=\"program_bullets\">Bullets (uno por línea)</label>",
            f"          <textarea id=\"program_bullets\" name=\"program_bullets\" rows=\"4\">{html.escape(program_bullets)}</textarea>",
            "        </div>",
            '        <div class="form-field">',
            "          <label for=\"program_image_caption\">Caption de la imagen</label>",
            f"          <input id=\"program_image_caption\" name=\"program_image_caption\" type=\"text\" value=\"{html.escape(program.get('image_caption',''))}\">",
            "        </div>",
            "      </div>",
            "    </div>",
            '    <div class="form-section">',
            "      <h4>Contacto</h4>",
            '      <div class="form-row">',
            '        <div class="form-field">',
            "          <label for=\"contact_email\">Email</label>",
            f"          <input id=\"contact_email\" name=\"contact_email\" type=\"email\" value=\"{html.escape(contact.get('email',''))}\">",
            "        </div>",
            '        <div class="form-field">',
            "          <label for=\"contact_phone\">Teléfono</label>",
            f"          <input id=\"contact_phone\" name=\"contact_phone\" type=\"text\" value=\"{html.escape(contact.get('phone',''))}\">",
            "        </div>",
            "      </div>",
            '      <div class="form-row">',
            '        <div class="form-field">',
            "          <label for=\"contact_city\">Ciudad</label>",
            f"          <input id=\"contact_city\" name=\"contact_city\" type=\"text\" value=\"{html.escape(contact.get('city',''))}\">",
            "        </div>",
            '        <div class="form-field">',
            "          <label for=\"contact_instagram\">Instagram</label>",
            f"          <input id=\"contact_instagram\" name=\"contact_instagram\" type=\"text\" value=\"{html.escape(contact.get('instagram',''))}\">",
            "        </div>",
            "      </div>",
            "    </div>",
            '    <div class="form-section">',
            "      <h4>Patrocinadores</h4>",
            '      <div class="form-field">',
            "        <label for=\"sponsors\">Lista (nombre | ruta-logo | enlace-opcional)</label>",
            f"        <textarea id=\"sponsors\" name=\"sponsors\" rows=\"3\">{html.escape(sponsors_text)}</textarea>",
            "      </div>",
            "    </div>",
            "        <button class=\"btn glass primary\" type=\"submit\">Guardar contenido</button>",
            "      </form>",
            "    </div>",
            "  </details>",
            "</div>",
        ]
    )


def render_admin_page(query: dict[str, list[str]]) -> str:
    events = load_json(EVENTS_PATH, [])
    videos = load_json(VIDEOS_PATH, [])
    applications = load_applications()
    content = load_content()
    storage_status = get_storage_status()
    selected_user = (query.get("plan_user") or [""])[0]
    status = (query.get("status") or [""])[0]
    plan_expanded = bool(selected_user or status == "plan_saved")
    replacements = {
        "ADMIN_MESSAGE": build_admin_alert(query),
        "COACH_DASHBOARD": render_coach_dashboard(applications, storage_status),
        "PLAN_EDITOR": render_plan_editor(applications, selected_user, expanded=plan_expanded),
        "CONTENT_FORM": render_content_form(content),
        "EVENT_LIST": render_event_list(events),
        "VIDEO_LIST": render_video_list(videos),
        "APPLICATION_LIST": render_application_list(applications),
    }
    return render_template(ADMIN_TEMPLATE, replacements)


def render_login_page(error: str | None = None) -> str:
    message = ""
    if error:
        message = f'<div class="form-alert error">{html.escape(error)}</div>'
    return "\n".join(
        [
            "<!doctype html>",
            "<html lang=\"es\">",
            "  <head>",
            "    <meta charset=\"utf-8\">",
            "    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">",
            "    <title>Acceso admin - AuraCalistenia</title>",
            "    <link rel=\"preconnect\" href=\"https://fonts.googleapis.com\">",
            "    <link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin>",
            "    <link href=\"https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Space+Grotesk:wght@300;400;500;600;700&display=swap\" rel=\"stylesheet\">",
            "    <link rel=\"stylesheet\" href=\"/styles.css?v=20260219-1\">",
            "  </head>",
            "  <body class=\"admin-body\">",
            "    <div class=\"noise\" aria-hidden=\"true\"></div>",
            "    <header class=\"nav\">",
            "      <div class=\"nav-inner\">",
            "        <nav class=\"nav-group nav-left\"></nav>",
            "        <a class=\"nav-brand\" href=\"/\" aria-label=\"AuraCalistenia\">",
            "          <span class=\"brand-mark\" aria-hidden=\"true\"></span>",
            "        </a>",
            "        <nav class=\"nav-group nav-right\">",
            "          <a href=\"/\">Inicio</a>",
            "        </nav>",
            "        <nav class=\"nav-group nav-compact\" aria-label=\"Navegación\">",
            "          <a href=\"/\">Inicio</a>",
            "        </nav>",
            "      </div>",
            "    </header>",
            "    <main class=\"section\">",
            "      <div class=\"admin-login glass-card\">",
            "        <h2>Acceso admin</h2>",
            f"        {message}",
            "        <form class=\"admin-form\" action=\"/admin/login\" method=\"post\">",
            "          <div class=\"form-field\">",
            "            <label for=\"admin_user\">Usuario</label>",
            "            <input id=\"admin_user\" name=\"username\" type=\"text\" required>",
            "          </div>",
            "          <div class=\"form-field\">",
            "            <label for=\"admin_pass\">Contraseña</label>",
            "            <input id=\"admin_pass\" name=\"password\" type=\"password\" required>",
            "          </div>",
            "          <button class=\"btn glass primary\" type=\"submit\">Entrar</button>",
            "        </form>",
            "      </div>",
            "    </main>",
            "  </body>",
            "</html>",
        ]
    )


def render_portal_page(query: dict[str, list[str]], cookie_header: str | None) -> str:
    access_status = (query.get("access") or [""])[0]
    user_alert = build_access_alert(access_status, "user")
    portal_user = get_session_user(cookie_header, USER_SESSION_COOKIE, "user")
    applications = load_applications()

    if not portal_user:
        forgot_block = render_forgot_password_block("portal")
        login_card = "\n".join(
            [
                '<div class="portal-card glass-card stagger-item">',
                "  <h3>Acceso a tu Área Privada</h3>",
                "  <p>Introduce tu usuario y contraseña para ver tu plan.</p>",
                f"  {user_alert}" if user_alert else "",
                "  <form class=\"admin-form\" action=\"/login\" method=\"post\">",
                "    <div class=\"form-field\">",
                "      <label for=\"portal_user\">Usuario</label>",
                "      <input id=\"portal_user\" name=\"username\" type=\"text\" required>",
                "    </div>",
                "    <div class=\"form-field\">",
                "      <label for=\"portal_pass\">Contraseña</label>",
                "      <input id=\"portal_pass\" name=\"password\" type=\"password\" required>",
                "    </div>",
                "    <button class=\"btn glass primary\" type=\"submit\">Entrar</button>",
                "  </form>",
                forgot_block,
                "</div>",
            ]
        )
        return render_template(
            PORTAL_TEMPLATE,
            {"PORTAL_CONTENT": login_card, "PORTAL_NAV_ACTIONS": ""},
        )

    app = find_application(applications, portal_user) or {}
    week_param = (query.get("week") or [""])[0]
    try:
        active_week = int(week_param)
    except (TypeError, ValueError):
        active_week = None
    plan_html = render_training_plan(app.get("plan", {}), active_week=active_week)
    chat_html = render_chat_panel(portal_user, "user")
    skill = html.escape(app.get("skill", "Sin datos"))
    level = html.escape(app.get("level", ""))
    goal = html.escape(app.get("goal", ""))
    summary = "\n".join(
        [
            '<div class="portal-card glass-card stagger-item">',
            "  <h3>Plan activo</h3>",
            f"  {user_alert}" if user_alert else "",
            f"  <p>Bienvenido, {html.escape(portal_user)}.</p>",
            "  <div class=\"portal-meta\">",
            f"    <span>Skill: {skill}</span>",
            f"    <span>Objetivo: {goal or 'Sin datos'}</span>",
            f"    <span>Nivel: {level or 'Sin datos'}</span>",
            "  </div>",
            "</div>",
        ]
    )

    nav_actions = "\n".join(
        [
            '<form class="nav-logout-form" action="/logout" method="post">',
            '  <button class="btn glass ghost nav-logout-btn" type="submit">Cerrar sesión</button>',
            "</form>",
        ]
    )

    portal_content = "\n".join(
        [
            '<div class="access-grid" data-stagger>',
            summary,
            "</div>",
            '<details class="portal-collapsible" open>',
            "  <summary>Plan de entrenamiento</summary>",
            f"  {plan_html}",
            "</details>",
            '<details class="portal-collapsible">',
            "  <summary>Chat con tu profesor</summary>",
            f"  {chat_html}",
            "</details>",
        ]
    )
    return render_template(
        PORTAL_TEMPLATE,
        {"PORTAL_CONTENT": portal_content, "PORTAL_NAV_ACTIONS": nav_actions},
    )


def parse_post_data(handler: SimpleHTTPRequestHandler) -> tuple[dict[str, str], dict[str, UploadedFile]]:
    content_type = handler.headers.get("Content-Type", "")
    length = int(handler.headers.get("Content-Length", 0))
    if content_type.startswith("multipart/form-data"):
        raw_body = handler.rfile.read(length)
        header = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8")
        message = BytesParser(policy=default).parsebytes(header + raw_body)
        data: dict[str, str] = {}
        files: dict[str, UploadedFile] = {}
        for part in message.iter_parts():
            if part.get_content_disposition() != "form-data":
                continue
            name = part.get_param("name", header="content-disposition")
            if not name:
                continue
            filename = part.get_filename()
            payload = part.get_payload(decode=True) or b""
            if filename:
                files[name] = UploadedFile(filename=filename, file=BytesIO(payload))
            else:
                charset = part.get_content_charset() or "utf-8"
                data[name] = payload.decode(charset, errors="replace")
        return data, files

    body = handler.rfile.read(length).decode("utf-8")
    parsed = urllib.parse.parse_qs(body)
    data = {key: values[0] if values else "" for key, values in parsed.items()}
    return data, {}


def parse_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def parse_pair_lines(text: str) -> list[tuple[str, str]]:
    pairs = []
    for line in parse_lines(text):
        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 2:
            continue
        pairs.append((parts[0], parts[1]))
    return pairs


def parse_sponsor_lines(text: str) -> list[dict]:
    sponsors = []
    for line in parse_lines(text):
        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 2:
            continue
        name, logo = parts[0], parts[1]
        url = parts[2] if len(parts) > 2 else ""
        if not name or not logo:
            continue
        sponsor = {"name": name, "logo": logo}
        if url:
            sponsor["url"] = url
        sponsors.append(sponsor)
    return sponsors


def parse_day_items(text: str) -> list[dict]:
    items = []
    for line in parse_lines(text):
        parts = [part.strip() for part in line.split("|")]
        while len(parts) < 6:
            parts.append("")
        exercise, sets, reps, weight, rest, notes = parts[:6]
        if not exercise:
            continue
        items.append(
            {
                "exercise": exercise,
                "sets": sets,
                "reps": reps,
                "weight": weight,
                "rest": rest,
                "notes": notes,
            }
        )
    return items


def parse_plan_items_from_form(data: dict[str, str], week_index: int, day_index: int) -> list[dict]:
    pattern = re.compile(
        rf"week{week_index}_day{day_index}_item(\d+)_(exercise|sets|reps|weight|rest|notes)$"
    )
    items_by_index: dict[int, dict[str, str]] = {}
    for key, value in data.items():
        match = pattern.match(key)
        if not match:
            continue
        idx = int(match.group(1))
        field = match.group(2)
        items_by_index.setdefault(idx, {})[field] = str(value).strip()
    items = []
    for idx in sorted(items_by_index):
        item = items_by_index[idx]
        exercise = item.get("exercise", "").strip()
        if not exercise:
            continue
        items.append(
            {
                "exercise": exercise,
                "sets": item.get("sets", "").strip(),
                "reps": item.get("reps", "").strip(),
                "weight": item.get("weight", "").strip(),
                "rest": item.get("rest", "").strip(),
                "notes": item.get("notes", "").strip(),
            }
        )
    return items


def send_email(
    smtp_settings: dict,
    to_email: str,
    subject: str,
    body: str,
    html_body: str | None = None,
    reply_to: str | None = None,
) -> None:
    msg = EmailMessage()
    from_name = smtp_settings.get("from_name") or "AuraCalistenia"
    from_email = smtp_settings.get("username") or smtp_settings.get("admin_email") or ""
    msg["From"] = f"{from_name} <{from_email}>" if from_email else from_name
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")
    if reply_to:
        msg["Reply-To"] = reply_to

    host = smtp_settings.get("host")
    port = int(smtp_settings.get("port", 587))
    username = smtp_settings.get("username")
    password = smtp_settings.get("password")
    use_tls = smtp_settings.get("use_tls", True)
    use_ssl = smtp_settings.get("use_ssl", False)
    if port == 465 and not use_ssl:
        # Fallback automático para proveedores que usan SMTPS directo en 465.
        use_ssl = True
        use_tls = False

    if use_ssl:
        with smtplib.SMTP_SSL(host, port, timeout=10) as server:
            server.ehlo()
            if username and password:
                server.login(username, password)
            server.send_message(msg)
        return

    with smtplib.SMTP(host, port, timeout=10) as server:
        server.ehlo()
        if use_tls:
            server.starttls()
            server.ehlo()
        if username and password:
            server.login(username, password)
        server.send_message(msg)


def notify_application(application: dict, smtp_settings: dict) -> tuple[bool, str]:
    if not smtp_settings.get("enabled"):
        return False, "smtp_disabled"
    if smtp_missing_fields(smtp_settings):
        return False, "smtp_incomplete"

    admin_email = smtp_settings.get("admin_email") or smtp_settings.get("username")
    if not admin_email:
        return False, "smtp_incomplete"

    username = str(application.get("username", "")).strip()
    email_value = str(application.get("email", "")).strip()
    skill = str(application.get("skill", "")).strip()
    level = str(application.get("level", "")).strip()
    goal = str(application.get("goal", "")).strip()
    concerns = str(application.get("concerns", "")).strip()
    created_text = format_date(application.get("created_at", 0)) or "Sin fecha"

    admin_subject = f"solicitud de alta - {username}"
    admin_body = (
        "Nueva solicitud de alta registrada\n\n"
        f"Fecha: {created_text}\n"
        f"Nombre de usuario: {username}\n"
        f"Correo: {email_value}\n"
        f"Skill objetivo: {skill or 'No indicado'}\n"
        f"Nivel actual: {level or 'No indicado'}\n"
        f"Objetivo principal: {goal or 'No indicado'}\n"
        f"Inquietudes: {concerns or 'No indicó inquietudes'}\n\n"
        "Puedes responder directamente a este mensaje para contestar al alumno."
    )
    admin_html = "\n".join(
        [
            "<html><body style=\"font-family:Arial,sans-serif;background:#f5f7fb;color:#1e2330;\">",
            "<div style=\"max-width:680px;margin:24px auto;background:#ffffff;border:1px solid #e4e8f0;border-radius:14px;padding:24px;\">",
            "<h2 style=\"margin:0 0 14px 0;color:#b08b4a;\">Nueva solicitud de alta</h2>",
            "<p style=\"margin:0 0 16px 0;color:#5f677a;\">Se ha recibido una nueva solicitud desde la web.</p>",
            "<table style=\"width:100%;border-collapse:collapse;\">",
            f"<tr><td style=\"padding:10px;border-bottom:1px solid #edf1f7;\"><strong>Fecha</strong></td><td style=\"padding:10px;border-bottom:1px solid #edf1f7;\">{html.escape(created_text)}</td></tr>",
            f"<tr><td style=\"padding:10px;border-bottom:1px solid #edf1f7;\"><strong>Usuario</strong></td><td style=\"padding:10px;border-bottom:1px solid #edf1f7;\">{html.escape(username)}</td></tr>",
            f"<tr><td style=\"padding:10px;border-bottom:1px solid #edf1f7;\"><strong>Email</strong></td><td style=\"padding:10px;border-bottom:1px solid #edf1f7;\">{html.escape(email_value)}</td></tr>",
            f"<tr><td style=\"padding:10px;border-bottom:1px solid #edf1f7;\"><strong>Skill</strong></td><td style=\"padding:10px;border-bottom:1px solid #edf1f7;\">{html.escape(skill or 'No indicado')}</td></tr>",
            f"<tr><td style=\"padding:10px;border-bottom:1px solid #edf1f7;\"><strong>Nivel actual</strong></td><td style=\"padding:10px;border-bottom:1px solid #edf1f7;\">{html.escape(level or 'No indicado')}</td></tr>",
            f"<tr><td style=\"padding:10px;border-bottom:1px solid #edf1f7;\"><strong>Objetivo</strong></td><td style=\"padding:10px;border-bottom:1px solid #edf1f7;\">{html.escape(goal or 'No indicado')}</td></tr>",
            f"<tr><td style=\"padding:10px;vertical-align:top;\"><strong>Inquietudes</strong></td><td style=\"padding:10px;\">{html.escape(concerns or 'No indicó inquietudes')}</td></tr>",
            "</table>",
            "<p style=\"margin:16px 0 0 0;color:#5f677a;\">Puedes responder directamente a este correo para contestar al alumno.</p>",
            "</div></body></html>",
        ]
    )

    user_subject = "Solicitud recibida - AuraCalistenia"
    user_body = (
        "Hemos recibido tu solicitud correctamente.\n\n"
        f"Usuario: {username}\n"
        f"Skill objetivo: {skill or 'No indicado'}\n"
        f"Objetivo: {goal or 'No indicado'}\n\n"
        "En breve revisaremos tus datos y te responderemos por email."
    )
    user_html = "\n".join(
        [
            "<html><body style=\"font-family:Arial,sans-serif;background:#f5f7fb;color:#1e2330;\">",
            "<div style=\"max-width:640px;margin:24px auto;background:#ffffff;border:1px solid #e4e8f0;border-radius:14px;padding:24px;\">",
            "<h2 style=\"margin:0 0 12px 0;color:#b08b4a;\">Solicitud recibida</h2>",
            f"<p style=\"margin:0 0 8px 0;\">Hola <strong>{html.escape(username)}</strong>,</p>",
            "<p style=\"margin:0 0 14px 0;color:#5f677a;\">Hemos recibido tu solicitud en AuraCalistenia con estos datos:</p>",
            "<ul style=\"margin:0 0 14px 18px;padding:0;color:#2f3748;\">",
            f"<li>Skill objetivo: {html.escape(skill or 'No indicado')}</li>",
            f"<li>Nivel actual: {html.escape(level or 'No indicado')}</li>",
            f"<li>Objetivo: {html.escape(goal or 'No indicado')}</li>",
            "</ul>",
            "<p style=\"margin:0;color:#5f677a;\">Te responderemos a este correo cuando revisemos tu alta.</p>",
            "</div></body></html>",
        ]
    )

    try:
        send_email(
            smtp_settings,
            admin_email,
            admin_subject,
            admin_body,
            html_body=admin_html,
            reply_to=email_value,
        )
        if email_value:
            send_email(smtp_settings, email_value, user_subject, user_body, html_body=user_html)
        clear_smtp_error()
    except Exception as exc:
        remember_smtp_error(exc)
        return False, "smtp_failed"

    return True, "ok"


def notify_password_reset(username: str, email_value: str, reset_url: str, smtp_settings: dict) -> tuple[bool, str]:
    if not smtp_settings.get("enabled"):
        return False, "smtp_disabled"
    if smtp_missing_fields(smtp_settings):
        return False, "smtp_incomplete"

    subject = "Restablecer contraseña - AuraCalistenia"
    ttl_minutes = max(int(RESET_TOKEN_TTL / 60), 1)
    body = (
        "Has solicitado restablecer tu contraseña.\n\n"
        f"Usuario: {username}\n"
        f"Enlace de restablecimiento: {reset_url}\n\n"
        f"Este enlace caduca en {ttl_minutes} minutos."
    )
    html_body = "\n".join(
        [
            "<html><body style=\"font-family:Arial,sans-serif;background:#f5f7fb;color:#1e2330;\">",
            "<div style=\"max-width:640px;margin:24px auto;background:#ffffff;border:1px solid #e4e8f0;border-radius:14px;padding:24px;\">",
            "<h2 style=\"margin:0 0 12px 0;color:#b08b4a;\">Restablecer contraseña</h2>",
            f"<p style=\"margin:0 0 8px 0;\">Hola <strong>{html.escape(username)}</strong>,</p>",
            "<p style=\"margin:0 0 14px 0;color:#5f677a;\">Pulsa en el botón para crear una contraseña nueva.</p>",
            f"<p style=\"margin:0 0 14px 0;\"><a href=\"{html.escape(reset_url)}\" style=\"display:inline-block;padding:12px 18px;background:#0d7e57;color:#fff;text-decoration:none;border-radius:10px;\">Restablecer contraseña</a></p>",
            f"<p style=\"margin:0;color:#5f677a;\">Este enlace caduca en {ttl_minutes} minutos. Si no lo solicitaste, ignora este correo.</p>",
            "</div></body></html>",
        ]
    )
    try:
        send_email(smtp_settings, email_value, subject, body, html_body=html_body)
        clear_smtp_error()
    except Exception as exc:
        remember_smtp_error(exc)
        return False, "smtp_failed"
    return True, "ok"


def notify_smtp_test(smtp_settings: dict) -> tuple[bool, str]:
    if not smtp_settings.get("enabled"):
        return False, "smtp_disabled"
    if smtp_missing_fields(smtp_settings):
        return False, "smtp_incomplete"
    target_email = str(smtp_settings.get("admin_email") or smtp_settings.get("username") or "").strip()
    if not target_email:
        return False, "smtp_incomplete"
    subject = "Prueba SMTP - AuraCalistenia"
    body = (
        "Correo de prueba enviado desde el panel admin.\n\n"
        "Si recibes este email, la configuración SMTP funciona correctamente."
    )
    try:
        send_email(smtp_settings, target_email, subject, body)
        clear_smtp_error()
    except Exception as exc:
        remember_smtp_error(exc)
        return False, "smtp_failed"
    return True, "ok"


def handle_file_upload(field: UploadedFile) -> tuple[str, str] | None:
    if not field.filename:
        return None
    original = Path(field.filename).name
    ext = Path(original).suffix.lower()
    if ext not in ALLOWED_VIDEO_EXT and ext not in ALLOWED_IMAGE_EXT:
        return None
    safe_name = f"{int(time.time())}_{secrets.token_hex(4)}{ext}"
    dest = UPLOAD_DIR / safe_name

    with dest.open("wb") as handle:
        field.file.seek(0)
        shutil.copyfileobj(field.file, handle)

    if dest.stat().st_size > MAX_UPLOAD_BYTES:
        dest.unlink(missing_ok=True)
        return None
    return safe_name, ext


def move_item_by_id(items: list[dict], item_id: str, direction: str) -> tuple[list[dict], bool]:
    index = -1
    for idx, item in enumerate(items):
        if str(item.get("id", "")).strip() == item_id:
            index = idx
            break
    if index == -1:
        return items, False
    step = -1 if direction == "up" else 1
    target = index + step
    if target < 0 or target >= len(items):
        return items, False
    reordered = list(items)
    reordered[index], reordered[target] = reordered[target], reordered[index]
    return reordered, True


class AuraHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    def end_headers(self) -> None:
        path = urllib.parse.urlparse(self.path).path.lower()
        static_ext = (
            ".css",
            ".js",
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
            ".svg",
            ".gif",
            ".mp4",
            ".webm",
            ".ogg",
            ".mov",
            ".woff",
            ".woff2",
        )
        if path.startswith("/uploads/") or path.endswith(static_ext):
            self.send_header("Cache-Control", "public, max-age=604800, immutable")
        elif path in {"/", "/admin", "/admin/", "/portal", "/portal/", "/password/reset"} or path.endswith(".html"):
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_html(self, content: str, status: int = HTTPStatus.OK) -> None:
        encoded = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def send_bytes(self, payload: bytes, content_type: str, filename: str | None = None) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(payload)

    def redirect(self, location: str) -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", location)
        self.end_headers()

    def admin_redirect(self, status: str) -> None:
        referer = self.headers.get("Referer", "")
        if "/admin" in referer:
            self.redirect(f"/admin?status={status}")
        else:
            self.redirect(f"/?admin_status={status}#acceso")

    def redirect_user_access(self, status: str) -> None:
        referer = self.headers.get("Referer", "")
        target = "/portal" if "/portal" in referer else "/"
        suffix = f"?access={status}" + ("" if target == "/portal" else "#acceso")
        self.redirect(f"{target}{suffix}")

    def get_public_base_url(self) -> str:
        forwarded = self.headers.get("Forwarded", "")
        proto = self.headers.get("X-Forwarded-Proto", "").split(",", 1)[0].strip()
        host = self.headers.get("X-Forwarded-Host", "").split(",", 1)[0].strip()
        if not host:
            host = self.headers.get("Host", "").split(",", 1)[0].strip()
        if not host:
            host = "localhost:8000"
        if not proto and "proto=https" in forwarded.lower():
            proto = "https"
        if proto not in {"http", "https"}:
            host_lower = host.lower()
            if host_lower.startswith("localhost") or host_lower.startswith("127.0.0.1"):
                proto = "http"
            else:
                proto = "https"
        return f"{proto}://{host}"

    def handle_export_json(self) -> None:
        timestamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
        memory = BytesIO()
        files = [
            ("events.json", EVENTS_PATH),
            ("videos.json", VIDEOS_PATH),
            ("applications.json", APPLICATIONS_PATH),
            ("submissions.json", SUBMISSIONS_PATH),
            ("chats.json", CHATS_PATH),
            ("sessions.json", SESSIONS_PATH),
            ("settings.json", SETTINGS_PATH),
            ("content.json", CONTENT_PATH),
            ("password_resets.json", PASSWORD_RESETS_PATH),
        ]
        with ZipFile(memory, mode="w", compression=ZIP_DEFLATED) as bundle:
            defaults = {
                "events.json": [],
                "videos.json": [],
                "applications.json": [],
                "submissions.json": [],
                "chats.json": [],
                "sessions.json": {},
                "settings.json": {},
                "content.json": {},
                "password_resets.json": {},
            }
            for archive_name, source_path in files:
                payload = load_json(source_path, defaults.get(archive_name, {}))
                bundle.writestr(
                    archive_name,
                    json.dumps(payload, indent=2, ensure_ascii=True),
                )
        payload = memory.getvalue()
        self.send_bytes(payload, "application/zip", f"aura-backup-{timestamp}.zip")

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path in {"/", "/index.html"}:
            self.send_html(render_index(query, self.headers.get("Cookie")))
            return

        if path == "/admin" or path == "/admin/":
            user = get_session_user(self.headers.get("Cookie"), ADMIN_SESSION_COOKIE, "admin")
            if user:
                self.send_html(render_admin_page(query))
            else:
                access = (query.get("access") or [""])[0]
                error = "Credenciales admin incorrectas." if access == "admin_error" else None
                self.send_html(render_login_page(error))
            return

        if path == "/admin.html":
            self.redirect("/admin")
            return

        if path == "/portal.html":
            self.redirect("/portal")
            return

        if path == "/legal":
            self.redirect("/legal.html")
            return

        if path == "/portal" or path == "/portal/":
            self.send_html(render_portal_page(query, self.headers.get("Cookie")))
            return

        if path == "/password/reset":
            self.send_html(render_password_reset_page(query))
            return

        if path == "/admin/export/json":
            user = get_session_user(self.headers.get("Cookie"), ADMIN_SESSION_COOKIE, "admin")
            if not user:
                self.send_error(HTTPStatus.FORBIDDEN)
                return
            self.handle_export_json()
            return

        if path.startswith("/data/"):
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        super().do_GET()

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/apply":
            self.handle_apply()
            return

        if path == "/admin/login":
            self.handle_admin_login()
            return

        if path == "/admin/logout":
            self.handle_admin_logout()
            return

        if path == "/login":
            self.handle_login()
            return

        if path == "/logout":
            self.handle_user_logout()
            return

        if path == "/password/forgot":
            self.handle_password_forgot()
            return

        if path == "/password/reset":
            self.handle_password_reset()
            return

        if path == "/user/submissions/add":
            self.handle_submission_add()
            return

        if path == "/portal/day/update":
            self.handle_day_update()
            return

        if path == "/portal/item/update":
            self.handle_item_update()
            return

        if path == "/portal/week/update":
            self.handle_week_update()
            return

        if path == "/portal/chat/send":
            self.handle_portal_chat_send()
            return

        admin_user = get_session_user(self.headers.get("Cookie"), ADMIN_SESSION_COOKIE, "admin")
        if not admin_user:
            self.send_error(HTTPStatus.FORBIDDEN)
            return

        if path == "/admin/events/add":
            self.handle_event_add()
            return

        if path == "/admin/events/update":
            self.handle_event_update()
            return

        if path == "/admin/events/move":
            self.handle_event_move()
            return

        if path == "/admin/events/delete":
            self.handle_event_delete()
            return

        if path == "/admin/videos/add":
            self.handle_video_add()
            return

        if path == "/admin/videos/update":
            self.handle_video_update()
            return

        if path == "/admin/videos/move":
            self.handle_video_move()
            return

        if path == "/admin/videos/delete":
            self.handle_video_delete()
            return

        if path == "/admin/plan/update":
            self.handle_plan_update()
            return

        if path == "/admin/content":
            self.handle_content_update()
            return

        if path == "/admin/smtp/test":
            self.handle_smtp_test()
            return

        if path == "/admin/clients/add":
            self.handle_client_add()
            return

        if path == "/admin/clients/duplicate":
            self.handle_client_duplicate()
            return

        if path == "/admin/applications/approve":
            self.handle_application_approve()
            return

        if path == "/admin/applications/delete":
            self.handle_application_delete()
            return

        if path == "/admin/submissions/comment":
            self.handle_submission_comment()
            return

        if path == "/admin/submissions/delete":
            self.handle_submission_delete()
            return

        if path == "/admin/chat/send":
            self.handle_admin_chat_send()
            return

        self.send_error(HTTPStatus.NOT_FOUND)

    def handle_apply(self) -> None:
        data, _ = parse_post_data(self)
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()
        email = data.get("email", "").strip()
        skill = data.get("skill", "").strip()
        level = data.get("level", "").strip()
        goal = data.get("goal", "").strip()
        concerns = data.get("concerns", "").strip()

        if not all([username, password, email, skill, goal]):
            self.redirect("/?status=error&message=Faltan campos obligatorios")
            return

        applications = load_applications()
        for app in applications:
            if app.get("username", "").lower() == username.lower():
                self.redirect("/?status=error&message=Usuario ya registrado")
                return
            if app.get("email", "").lower() == email.lower():
                self.redirect("/?status=error&message=Email ya registrado")
                return

        salt, pw_hash = hash_password(password)
        application = {
            "id": secrets.token_hex(6),
            "username": username,
            "email": email,
            "skill": skill,
            "level": level,
            "goal": goal,
            "concerns": concerns,
            "salt": salt,
            "hash": pw_hash,
            "approved": False,
            "plan": copy_default_plan(),
            "created_at": int(time.time()),
        }
        applications.append(application)
        save_json(APPLICATIONS_PATH, applications)

        smtp_settings = load_smtp_settings()
        if not smtp_settings.get("enabled"):
            self.redirect("/?status=smtp_disabled")
            return
        missing = smtp_missing_fields(smtp_settings)
        if missing:
            detail = urllib.parse.quote(f"Faltan variables en Render: {', '.join(missing)}")
            self.redirect(f"/?status=smtp_incomplete&message={detail}")
            return
        ok, reason = notify_application(application, smtp_settings)
        if ok:
            self.redirect("/?status=ok")
            return
        if reason == "smtp_incomplete":
            detail = urllib.parse.quote("Faltan variables SMTP (HOST/USER/PASS).")
            self.redirect(f"/?status=smtp_incomplete&message={detail}")
            return
        if reason == "smtp_disabled":
            self.redirect("/?status=smtp_disabled")
            return
        self.redirect("/?status=smtp_error")

    def handle_admin_login(self) -> None:
        data, _ = parse_post_data(self)
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()
        settings = load_json(SETTINGS_PATH, {})
        admin = settings.get("admin", {})
        if username != admin.get("username"):
            self.redirect("/admin?access=admin_error")
            return
        if not verify_password(password, admin.get("salt", ""), admin.get("hash", "")):
            self.redirect("/admin?access=admin_error")
            return

        cookie_header = self.headers.get("Cookie")
        old_user_token = get_cookie_token(cookie_header, USER_SESSION_COOKIE)
        if old_user_token:
            delete_session(old_user_token)
        token = create_session(username, "admin")
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header(
            "Set-Cookie",
            f"{ADMIN_SESSION_COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax",
        )
        self.send_header("Set-Cookie", f"{USER_SESSION_COOKIE}=deleted; Path=/; Max-Age=0")
        self.send_header("Location", "/admin")
        self.end_headers()

    def handle_admin_logout(self) -> None:
        cookie_header = self.headers.get("Cookie")
        user = get_session_user(cookie_header, ADMIN_SESSION_COOKIE, "admin")
        token = get_cookie_token(cookie_header, ADMIN_SESSION_COOKIE)
        if user and token:
            delete_session(token)
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Set-Cookie", f"{ADMIN_SESSION_COOKIE}=deleted; Path=/; Max-Age=0")
        self.send_header("Location", "/portal")
        self.end_headers()

    def handle_login(self) -> None:
        data, _ = parse_post_data(self)
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()
        if not username or not password:
            referer = self.headers.get("Referer", "")
            target = "/portal" if "/portal" in referer else "/"
            suffix = "?access=user_missing" + ("" if target == "/portal" else "#acceso")
            self.redirect(f"{target}{suffix}")
            return

        settings = load_json(SETTINGS_PATH, {})
        admin = settings.get("admin", {})
        if username == admin.get("username"):
            if verify_password(password, admin.get("salt", ""), admin.get("hash", "")):
                cookie_header = self.headers.get("Cookie")
                old_user_token = get_cookie_token(cookie_header, USER_SESSION_COOKIE)
                if old_user_token:
                    delete_session(old_user_token)
                token = create_session(username, "admin")
                self.send_response(HTTPStatus.SEE_OTHER)
                self.send_header(
                    "Set-Cookie",
                    f"{ADMIN_SESSION_COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax",
                )
                self.send_header("Set-Cookie", f"{USER_SESSION_COOKIE}=deleted; Path=/; Max-Age=0")
                self.send_header("Location", "/admin")
                self.end_headers()
                return
            self.redirect("/admin?access=admin_error")
            return

        applications = load_applications()
        app = find_application(applications, username)
        if not app:
            referer = self.headers.get("Referer", "")
            target = "/portal" if "/portal" in referer else "/"
            suffix = "?access=user_error" + ("" if target == "/portal" else "#acceso")
            self.redirect(f"{target}{suffix}")
            return
        if not verify_password(password, app.get("salt", ""), app.get("hash", "")):
            referer = self.headers.get("Referer", "")
            target = "/portal" if "/portal" in referer else "/"
            suffix = "?access=user_error" + ("" if target == "/portal" else "#acceso")
            self.redirect(f"{target}{suffix}")
            return
        if not app.get("approved"):
            referer = self.headers.get("Referer", "")
            target = "/portal" if "/portal" in referer else "/"
            suffix = "?access=user_pending" + ("" if target == "/portal" else "#acceso")
            self.redirect(f"{target}{suffix}")
            return

        cookie_header = self.headers.get("Cookie")
        old_admin_token = get_cookie_token(cookie_header, ADMIN_SESSION_COOKIE)
        if old_admin_token:
            delete_session(old_admin_token)
        token = create_session(username, "user")
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header(
            "Set-Cookie",
            f"{USER_SESSION_COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax",
        )
        self.send_header("Set-Cookie", f"{ADMIN_SESSION_COOKIE}=deleted; Path=/; Max-Age=0")
        self.send_header("Location", "/portal")
        self.end_headers()

    def handle_user_logout(self) -> None:
        cookie_header = self.headers.get("Cookie")
        user = get_session_user(cookie_header, USER_SESSION_COOKIE, "user")
        token = get_cookie_token(cookie_header, USER_SESSION_COOKIE)
        if user and token:
            delete_session(token)
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Set-Cookie", f"{USER_SESSION_COOKIE}=deleted; Path=/; Max-Age=0")
        referer = self.headers.get("Referer", "")
        target = "/portal" if "/portal" in referer else "/"
        suffix = "?access=user_logout" + ("" if target == "/portal" else "#acceso")
        self.send_header("Location", f"{target}{suffix}")
        self.end_headers()

    def handle_password_forgot(self) -> None:
        data, _ = parse_post_data(self)
        username = data.get("username", "").strip()
        email_value = data.get("email", "").strip().lower()
        if not username or not email_value:
            self.redirect_user_access("user_reset_missing")
            return

        applications = load_applications()
        app = find_application(applications, username)
        if not app:
            self.redirect_user_access("user_reset_sent")
            return
        app_email = str(app.get("email", "")).strip().lower()
        if app_email != email_value:
            self.redirect_user_access("user_reset_sent")
            return

        token = create_password_reset_token(str(app.get("username", username)).strip(), app_email)
        reset_url = f"{self.get_public_base_url()}/password/reset?token={urllib.parse.quote(token)}"
        smtp_settings = load_smtp_settings()
        ok, reason = notify_password_reset(str(app.get("username", username)).strip(), app_email, reset_url, smtp_settings)
        if not ok:
            consume_password_reset_token(token)
            if reason == "smtp_disabled":
                self.redirect_user_access("user_reset_smtp_disabled")
                return
            if reason == "smtp_incomplete":
                self.redirect_user_access("user_reset_smtp_incomplete")
                return
            if reason == "smtp_failed":
                self.redirect_user_access("user_reset_smtp_failed")
                return
            self.redirect_user_access("user_reset_invalid")
            return
        self.redirect_user_access("user_reset_sent")

    def handle_password_reset(self) -> None:
        data, _ = parse_post_data(self)
        token = data.get("token", "").strip()
        password = data.get("password", "").strip()
        password_confirm = data.get("password_confirm", "").strip()
        if not token:
            self.redirect("/password/reset?access=user_reset_invalid")
            return
        if not password or password != password_confirm:
            quoted = urllib.parse.quote(token)
            self.redirect(f"/password/reset?token={quoted}&access=user_reset_mismatch")
            return

        payload = consume_password_reset_token(token)
        if not payload:
            self.redirect("/password/reset?access=user_reset_invalid")
            return

        username = str(payload.get("username", "")).strip()
        email_value = str(payload.get("email", "")).strip().lower()
        applications = load_applications()
        app = find_application(applications, username)
        if not app:
            self.redirect("/password/reset?access=user_reset_invalid")
            return
        if str(app.get("email", "")).strip().lower() != email_value:
            self.redirect("/password/reset?access=user_reset_invalid")
            return

        salt, pw_hash = hash_password(password)
        app["salt"] = salt
        app["hash"] = pw_hash
        save_json(APPLICATIONS_PATH, applications)
        self.redirect("/portal?access=user_reset_done")

    def handle_event_add(self) -> None:
        data, _ = parse_post_data(self)
        title = data.get("title", "").strip()
        date = data.get("date", "").strip()
        location = data.get("location", "").strip()
        description = data.get("description", "").strip()
        tag = data.get("tag", "").strip()
        if not all([title, date, location, description, tag]):
            self.admin_redirect("error")
            return

        events = load_json(EVENTS_PATH, [])
        events.append(
            {
                "id": f"evt_{secrets.token_hex(4)}",
                "date": date,
                "location": location,
                "title": title,
                "description": description,
                "tag": tag,
            }
        )
        save_json(EVENTS_PATH, events)
        self.admin_redirect("event_added")

    def handle_event_update(self) -> None:
        data, _ = parse_post_data(self)
        event_id = data.get("id", "").strip()
        title = data.get("title", "").strip()
        date = data.get("date", "").strip()
        location = data.get("location", "").strip()
        description = data.get("description", "").strip()
        tag = data.get("tag", "").strip()
        if not all([event_id, title, date, location, description, tag]):
            self.admin_redirect("error")
            return
        events = load_json(EVENTS_PATH, [])
        updated = False
        for event in events:
            if str(event.get("id", "")).strip() != event_id:
                continue
            event["title"] = title
            event["date"] = date
            event["location"] = location
            event["description"] = description
            event["tag"] = tag
            updated = True
            break
        if not updated:
            self.admin_redirect("error")
            return
        save_json(EVENTS_PATH, events)
        self.admin_redirect("event_updated")

    def handle_event_move(self) -> None:
        data, _ = parse_post_data(self)
        event_id = data.get("id", "").strip()
        direction = data.get("direction", "").strip()
        if direction not in {"up", "down"} or not event_id:
            self.admin_redirect("error")
            return
        events = load_json(EVENTS_PATH, [])
        reordered, changed = move_item_by_id(events, event_id, direction)
        if not changed:
            self.admin_redirect("error")
            return
        save_json(EVENTS_PATH, reordered)
        self.admin_redirect("event_moved")

    def handle_event_delete(self) -> None:
        data, _ = parse_post_data(self)
        event_id = data.get("id", "").strip()
        events = load_json(EVENTS_PATH, [])
        events = [event for event in events if event.get("id") != event_id]
        save_json(EVENTS_PATH, events)
        self.admin_redirect("event_deleted")

    def handle_video_add(self) -> None:
        data, files = parse_post_data(self)
        title = data.get("title", "").strip()
        tag = data.get("tag", "").strip()
        description = data.get("description", "").strip()
        layout = data.get("layout", "").strip()
        video_url = data.get("video_url", "").strip()
        if not all([title, tag, description]):
            self.admin_redirect("error")
            return

        stored_file = ""
        if "video_file" in files:
            upload = handle_file_upload(files["video_file"])
            if upload:
                stored_file, _ = upload

        videos = load_json(VIDEOS_PATH, [])
        videos.append(
            {
                "id": f"vid_{secrets.token_hex(4)}",
                "tag": tag,
                "title": title,
                "description": description,
                "layout": layout if layout in {"tall", "wide"} else "",
                "video_url": video_url,
                "file": stored_file,
            }
        )
        save_json(VIDEOS_PATH, videos)
        self.admin_redirect("video_added")

    def handle_video_update(self) -> None:
        data, files = parse_post_data(self)
        video_id = data.get("id", "").strip()
        title = data.get("title", "").strip()
        tag = data.get("tag", "").strip()
        description = data.get("description", "").strip()
        layout = data.get("layout", "").strip()
        video_url = data.get("video_url", "").strip()
        remove_file = "remove_file" in data
        if not all([video_id, title, tag, description]):
            self.admin_redirect("error")
            return

        videos = load_json(VIDEOS_PATH, [])
        updated = False
        for video in videos:
            if str(video.get("id", "")).strip() != video_id:
                continue
            video["title"] = title
            video["tag"] = tag
            video["description"] = description
            video["layout"] = layout if layout in {"tall", "wide"} else ""
            video["video_url"] = video_url
            current_file = str(video.get("file", "")).strip()
            if remove_file and current_file:
                current_path = UPLOAD_DIR / current_file
                if current_path.exists():
                    current_path.unlink(missing_ok=True)
                video["file"] = ""
                current_file = ""
            if "video_file" in files:
                upload = handle_file_upload(files["video_file"])
                if upload:
                    new_file, _ = upload
                    if current_file:
                        old_path = UPLOAD_DIR / current_file
                        if old_path.exists():
                            old_path.unlink(missing_ok=True)
                    video["file"] = new_file
            updated = True
            break
        if not updated:
            self.admin_redirect("error")
            return
        save_json(VIDEOS_PATH, videos)
        self.admin_redirect("video_updated")

    def handle_video_move(self) -> None:
        data, _ = parse_post_data(self)
        video_id = data.get("id", "").strip()
        direction = data.get("direction", "").strip()
        if direction not in {"up", "down"} or not video_id:
            self.admin_redirect("error")
            return
        videos = load_json(VIDEOS_PATH, [])
        reordered, changed = move_item_by_id(videos, video_id, direction)
        if not changed:
            self.admin_redirect("error")
            return
        save_json(VIDEOS_PATH, reordered)
        self.admin_redirect("video_moved")

    def handle_video_delete(self) -> None:
        data, _ = parse_post_data(self)
        video_id = data.get("id", "").strip()
        videos = load_json(VIDEOS_PATH, [])
        remaining = []
        for video in videos:
            if video.get("id") == video_id:
                file_name = video.get("file")
                if file_name:
                    file_path = UPLOAD_DIR / file_name
                    if file_path.exists():
                        file_path.unlink(missing_ok=True)
                continue
            remaining.append(video)
        save_json(VIDEOS_PATH, remaining)
        self.admin_redirect("video_deleted")

    def handle_content_update(self) -> None:
        data, files = parse_post_data(self)
        content = load_content()

        content["hero"]["eyebrow"] = data.get("hero_eyebrow", "").strip()
        content["hero"]["title"] = data.get("hero_title", "").strip()
        content["hero"]["subtitle"] = data.get("hero_subtitle", "").strip()
        stats_pairs = parse_pair_lines(data.get("hero_stats", ""))
        if stats_pairs:
            content["stats"] = [{"value": value, "label": label} for value, label in stats_pairs]

        content["bio"]["eyebrow"] = data.get("bio_eyebrow", "").strip()
        content["bio"]["name"] = data.get("bio_name", "").strip()
        paragraphs = parse_lines(data.get("bio_paragraphs", ""))
        if paragraphs:
            content["bio"]["paragraphs"] = paragraphs
        content["bio"]["signature"] = data.get("bio_signature", "").strip()
        content["bio"]["image"] = data.get("bio_image", "").strip()
        content["bio"]["image_caption"] = data.get("bio_image_caption", "").strip()
        if "bio_image_file" in files:
            upload = handle_file_upload(files["bio_image_file"])
            if upload:
                stored_file, ext = upload
                if ext in ALLOWED_IMAGE_EXT:
                    content["bio"]["image"] = f"/uploads/{stored_file}"

        content["program"]["title"] = data.get("program_title", "").strip()
        content["program"]["lead"] = data.get("program_lead", "").strip()
        content["program"]["highlight_title"] = data.get("program_highlight_title", "").strip()
        content["program"]["highlight_text"] = data.get("program_highlight_text", "").strip()
        bullets = parse_lines(data.get("program_bullets", ""))
        if bullets:
            content["program"]["bullets"] = bullets
        content["program"]["image"] = data.get("program_image", "").strip()
        content["program"]["image_caption"] = data.get("program_image_caption", "").strip()
        if "program_image_file" in files:
            upload = handle_file_upload(files["program_image_file"])
            if upload:
                stored_file, ext = upload
                if ext in ALLOWED_IMAGE_EXT:
                    content["program"]["image"] = f"/uploads/{stored_file}"

        content["contact"]["email"] = data.get("contact_email", "").strip()
        content["contact"]["phone"] = data.get("contact_phone", "").strip()
        content["contact"]["city"] = data.get("contact_city", "").strip()
        content["contact"]["instagram"] = data.get("contact_instagram", "").strip()

        sponsor_entries = parse_sponsor_lines(data.get("sponsors", ""))
        if sponsor_entries:
            content["sponsors"] = sponsor_entries

        save_json(CONTENT_PATH, content)
        self.admin_redirect("content_saved")

    def handle_smtp_test(self) -> None:
        smtp_settings = load_smtp_settings()
        ok, reason = notify_smtp_test(smtp_settings)
        if ok:
            self.redirect("/admin?admin_status=smtp_test_ok")
            return
        if reason == "smtp_disabled":
            self.redirect("/admin?admin_status=smtp_test_disabled")
            return
        if reason == "smtp_incomplete":
            self.redirect("/admin?admin_status=smtp_test_incomplete")
            return
        self.redirect("/admin?admin_status=smtp_test_failed")

    def handle_client_add(self) -> None:
        data, _ = parse_post_data(self)
        username = data.get("client_username", "").strip()
        password = data.get("client_password", "").strip()
        email = data.get("client_email", "").strip()
        skill = data.get("client_skill", "").strip()
        level = data.get("client_level", "").strip()
        goal = data.get("client_goal", "").strip()
        concerns = data.get("client_concerns", "").strip()
        approved = "client_approved" in data

        if not username or not password or not email:
            self.admin_redirect("error")
            return

        applications = load_applications()
        if find_application(applications, username):
            self.admin_redirect("client_exists")
            return

        salt, pw_hash = hash_password(password)
        application = {
            "id": f"app_{secrets.token_hex(4)}",
            "username": username,
            "email": email,
            "skill": skill,
            "level": level,
            "goal": goal,
            "concerns": concerns,
            "salt": salt,
            "hash": pw_hash,
            "approved": approved,
            "plan": copy_default_plan(),
            "created_at": int(time.time()),
        }
        applications.append(application)
        save_json(APPLICATIONS_PATH, applications)
        self.admin_redirect("client_added")

    def handle_client_duplicate(self) -> None:
        data, _ = parse_post_data(self)
        source_id = data.get("id", "").strip()
        if not source_id:
            self.admin_redirect("error")
            return
        applications = load_applications()
        source = None
        for app in applications:
            if str(app.get("id", "")).strip() == source_id:
                source = app
                break
        if not source:
            self.admin_redirect("error")
            return
        base_username = str(source.get("username", "")).strip()
        if not base_username:
            self.admin_redirect("error")
            return
        existing_usernames = {str(app.get("username", "")).strip().lower() for app in applications}
        duplicate_username = f"{base_username}_copy"
        suffix = 2
        while duplicate_username.lower() in existing_usernames:
            duplicate_username = f"{base_username}_copy{suffix}"
            suffix += 1
        existing_emails = {str(app.get("email", "")).strip().lower() for app in applications}
        duplicate_email = str(source.get("email", "")).strip()
        if duplicate_email:
            if "@" in duplicate_email:
                local, domain = duplicate_email.split("@", 1)
                counter = 1
                candidate = f"{local}+copy@{domain}"
                while candidate.lower() in existing_emails:
                    counter += 1
                    candidate = f"{local}+copy{counter}@{domain}"
                duplicate_email = candidate
            else:
                counter = 1
                candidate = f"{duplicate_email}.copy"
                while candidate.lower() in existing_emails:
                    counter += 1
                    candidate = f"{duplicate_email}.copy{counter}"
                duplicate_email = candidate
        duplicated = {
            "id": f"app_{secrets.token_hex(4)}",
            "username": duplicate_username,
            "email": duplicate_email,
            "skill": source.get("skill", ""),
            "level": source.get("level", ""),
            "goal": source.get("goal", ""),
            "concerns": source.get("concerns", ""),
            "salt": source.get("salt", ""),
            "hash": source.get("hash", ""),
            "approved": bool(source.get("approved")),
            "plan": normalize_plan(source.get("plan")),
            "created_at": int(time.time()),
        }
        applications.append(duplicated)
        save_json(APPLICATIONS_PATH, applications)
        self.admin_redirect("client_duplicated")

    def handle_plan_update(self) -> None:
        data, _ = parse_post_data(self)
        username = data.get("username", "").strip()
        if not username:
            self.admin_redirect("error")
            return
        applications = load_applications()
        app = find_application(applications, username)
        if not app:
            self.admin_redirect("error")
            return
        plan = normalize_plan(app.get("plan"))
        plan_title = data.get("plan_title", "").strip()
        if plan_title:
            plan["title"] = plan_title
        for week_index in range(4):
            week_title = data.get(f"week{week_index + 1}_title", "").strip()
            if week_title:
                plan["weeks"][week_index]["title"] = week_title
            for day_index in range(7):
                day_key = f"week{week_index + 1}_day{day_index + 1}"
                day_title = data.get(f"{day_key}_title", "").strip()
                rest_flag = f"{day_key}_rest" in data
                day = plan["weeks"][week_index]["days"][day_index]
                old_items = day.get("items", []) if isinstance(day.get("items"), list) else []
                day_text_key = f"{day_key}_text"
                if day_text_key in data:
                    items = parse_day_items(data.get(day_text_key, ""))
                else:
                    items = parse_plan_items_from_form(data, week_index + 1, day_index + 1)
                for item_pos, parsed_item in enumerate(items):
                    if item_pos >= len(old_items):
                        continue
                    old_item = old_items[item_pos]
                    if not isinstance(old_item, dict):
                        continue
                    parsed_item["status"] = str(old_item.get("status", "")).strip()
                    parsed_item["status_note"] = str(old_item.get("status_note", "")).strip()
                    parsed_item["student_note"] = str(old_item.get("student_note", "")).strip()
                day["title"] = day_title
                day["rest"] = rest_flag
                day["items"] = [] if rest_flag else items
        app["plan"] = plan
        save_json(APPLICATIONS_PATH, applications)
        plan_param = urllib.parse.quote(username)
        self.redirect(
            f"/admin?admin_section=portal&status=plan_saved&plan_user={plan_param}#plan"
        )

    def handle_day_update(self) -> None:
        cookie_header = self.headers.get("Cookie")
        portal_user = get_session_user(cookie_header, USER_SESSION_COOKIE, "user")
        if not portal_user:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        data, _ = parse_post_data(self)
        try:
            week_index = int(data.get("week", "0")) - 1
            day_index = int(data.get("day", "0")) - 1
        except ValueError:
            self.redirect("/portal")
            return
        if week_index not in range(4) or day_index not in range(7):
            self.redirect("/portal")
            return
        status = data.get("status", "").strip()
        status_note = data.get("status_note", "").strip()
        feedback = data.get("feedback", "").strip()

        applications = load_applications()
        app = find_application(applications, portal_user)
        if not app:
            self.redirect("/portal")
            return
        plan = normalize_plan(app.get("plan"))
        day = plan["weeks"][week_index]["days"][day_index]
        if status in {"done", "partial", "missed"}:
            day["status"] = status
        if "status_note" in data:
            day["status_note"] = status_note
        if "feedback" in data:
            day["feedback"] = feedback
        app["plan"] = plan
        save_json(APPLICATIONS_PATH, applications)
        self.redirect(f"/portal?week={week_index + 1}#week{week_index + 1}")

    def handle_item_update(self) -> None:
        cookie_header = self.headers.get("Cookie")
        portal_user = get_session_user(cookie_header, USER_SESSION_COOKIE, "user")
        if not portal_user:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        data, _ = parse_post_data(self)
        try:
            week_index = int(data.get("week", "0")) - 1
            day_index = int(data.get("day", "0")) - 1
            item_index = int(data.get("item", "0")) - 1
        except ValueError:
            self.redirect("/portal")
            return
        if week_index not in range(4) or day_index not in range(7) or item_index < 0:
            self.redirect("/portal")
            return
        status = data.get("status", "").strip()
        status_note = data.get("status_note", "").strip()
        student_note = data.get("student_note", "").strip()

        applications = load_applications()
        app = find_application(applications, portal_user)
        if not app:
            self.redirect("/portal")
            return
        plan = normalize_plan(app.get("plan"))
        day = plan["weeks"][week_index]["days"][day_index]
        items = day.get("items", [])
        if item_index >= len(items):
            self.redirect(f"/portal?week={week_index + 1}#week{week_index + 1}")
            return
        item = items[item_index]
        if not isinstance(item, dict):
            self.redirect(f"/portal?week={week_index + 1}#week{week_index + 1}")
            return
        if status in {"done", "missed"}:
            item["status"] = status
        item["status_note"] = status_note
        item["student_note"] = student_note
        app["plan"] = plan
        save_json(APPLICATIONS_PATH, applications)
        self.redirect(f"/portal?week={week_index + 1}#week{week_index + 1}")

    def handle_week_update(self) -> None:
        cookie_header = self.headers.get("Cookie")
        portal_user = get_session_user(cookie_header, USER_SESSION_COOKIE, "user")
        if not portal_user:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        data, _ = parse_post_data(self)
        try:
            week_index = int(data.get("week", "0")) - 1
        except ValueError:
            self.redirect("/portal")
            return
        if week_index not in range(4):
            self.redirect("/portal")
            return
        summary = data.get("summary", "").strip()
        applications = load_applications()
        app = find_application(applications, portal_user)
        if not app:
            self.redirect("/portal")
            return
        plan = normalize_plan(app.get("plan"))
        plan["weeks"][week_index]["summary"] = summary
        app["plan"] = plan
        save_json(APPLICATIONS_PATH, applications)
        self.redirect(f"/portal?week={week_index + 1}#week{week_index + 1}")

    def handle_portal_chat_send(self) -> None:
        cookie_header = self.headers.get("Cookie")
        portal_user = get_session_user(cookie_header, USER_SESSION_COOKIE, "user")
        if not portal_user:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        data, _ = parse_post_data(self)
        text = data.get("text", "").strip()
        if not text:
            self.redirect("/portal")
            return
        chats = load_json(CHATS_PATH, [])
        if not isinstance(chats, list):
            chats = []
        chats.append(
            {
                "id": f"chat_{secrets.token_hex(4)}",
                "username": portal_user,
                "author": "user",
                "text": text,
                "created_at": int(time.time()),
            }
        )
        save_json(CHATS_PATH, chats)
        self.redirect("/portal")

    def handle_admin_chat_send(self) -> None:
        data, _ = parse_post_data(self)
        username = data.get("username", "").strip()
        text = data.get("text", "").strip()
        if not username or not text:
            self.admin_redirect("error")
            return
        applications = load_applications()
        app = find_application(applications, username)
        if not app:
            self.admin_redirect("error")
            return
        chats = load_json(CHATS_PATH, [])
        if not isinstance(chats, list):
            chats = []
        chats.append(
            {
                "id": f"chat_{secrets.token_hex(4)}",
                "username": app.get("username", username),
                "author": "coach",
                "text": text,
                "created_at": int(time.time()),
            }
        )
        save_json(CHATS_PATH, chats)
        plan_param = urllib.parse.quote(app.get("username", username))
        self.redirect(f"/admin?admin_section=portal&plan_user={plan_param}#plan")

    def handle_submission_add(self) -> None:
        cookie_header = self.headers.get("Cookie")
        portal_user = get_session_user(cookie_header, USER_SESSION_COOKIE, "user")
        if not portal_user:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        data, files = parse_post_data(self)
        title = data.get("title", "").strip()
        description = data.get("description", "").strip()
        video_url = data.get("video_url", "").strip()
        stored_file = ""
        if "video_file" in files:
            upload = handle_file_upload(files["video_file"])
            if upload:
                stored_file, _ = upload

        if not title or not description or (not stored_file and not video_url):
            self.redirect("/?access=user_submit_error#acceso")
            return

        submissions = load_submissions()
        submissions.append(
            {
                "id": f"sub_{secrets.token_hex(4)}",
                "username": portal_user,
                "title": title,
                "description": description,
                "video_url": video_url,
                "file": stored_file,
                "created_at": int(time.time()),
                "comments": [],
            }
        )
        save_json(SUBMISSIONS_PATH, submissions)
        self.redirect("/?access=user_submit_ok#acceso")

    def handle_submission_comment(self) -> None:
        data, _ = parse_post_data(self)
        sub_id = data.get("id", "").strip()
        comment = data.get("comment", "").strip()
        if not sub_id or not comment:
            self.admin_redirect("error")
            return
        submissions = load_submissions()
        updated = False
        for sub in submissions:
            if sub.get("id") == sub_id:
                sub.setdefault("comments", []).append(
                    {"text": comment, "created_at": int(time.time())}
                )
                updated = True
                break
        if updated:
            save_json(SUBMISSIONS_PATH, submissions)
            self.admin_redirect("comment_added")
        else:
            self.admin_redirect("error")

    def handle_submission_delete(self) -> None:
        data, _ = parse_post_data(self)
        sub_id = data.get("id", "").strip()
        submissions = load_submissions()
        remaining = []
        for sub in submissions:
            if sub.get("id") == sub_id:
                file_name = sub.get("file")
                if file_name:
                    file_path = UPLOAD_DIR / file_name
                    if file_path.exists():
                        file_path.unlink(missing_ok=True)
                continue
            remaining.append(sub)
        save_json(SUBMISSIONS_PATH, remaining)
        self.admin_redirect("submission_deleted")

    def handle_application_approve(self) -> None:
        data, _ = parse_post_data(self)
        app_id = data.get("id", "").strip()
        applications = load_applications()
        updated = False
        for app in applications:
            if app.get("id") == app_id:
                app["approved"] = True
                updated = True
                break
        if updated:
            save_json(APPLICATIONS_PATH, applications)
            self.admin_redirect("app_approved")
        else:
            self.admin_redirect("error")

    def handle_application_delete(self) -> None:
        data, _ = parse_post_data(self)
        app_id = data.get("id", "").strip()
        applications = load_applications()
        applications = [app for app in applications if app.get("id") != app_id]
        save_json(APPLICATIONS_PATH, applications)
        self.admin_redirect("app_deleted")


def run_server(port: int | None = None, host: str | None = None) -> None:
    ensure_data_files()
    if port is None:
        port = int(os.environ.get("PORT", "8000"))
    if host is None:
        host = os.environ.get("HOST", "0.0.0.0")
    server_address = (host, port)
    httpd = ThreadingHTTPServer(server_address, AuraHandler)
    if db_enabled():
        print(
            "Database URL detectada en "
            f"{DATABASE_URL_SOURCE or 'DATABASE_URL'} | driver="
            f"{'psycopg' if psycopg is not None else ('psycopg2' if psycopg2 is not None else 'none')}"
        )
        if DB_LAST_ERROR:
            print(f"Advertencia DB: {DB_LAST_ERROR}")
    else:
        print("Database URL no detectada. Modo JSON local temporal.")
    print(f"Serving on http://{host}:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run_server()
