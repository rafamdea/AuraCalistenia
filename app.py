from __future__ import annotations

import base64
import hashlib
import html
import json
import os
import secrets
import shutil
import smtplib
import threading
import time
import urllib.parse
from dataclasses import dataclass
from email.message import EmailMessage
from email.parser import BytesParser
from email.policy import default
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("AURA_DATA_DIR", str(BASE_DIR / "data")))
UPLOAD_DIR = Path(os.environ.get("AURA_UPLOAD_DIR", str(BASE_DIR / "uploads")))
INDEX_TEMPLATE = BASE_DIR / "index.html"
ADMIN_TEMPLATE = BASE_DIR / "admin.html"

EVENTS_PATH = DATA_DIR / "events.json"
VIDEOS_PATH = DATA_DIR / "videos.json"
APPLICATIONS_PATH = DATA_DIR / "applications.json"
SUBMISSIONS_PATH = DATA_DIR / "submissions.json"
SESSIONS_PATH = DATA_DIR / "sessions.json"
SETTINGS_PATH = DATA_DIR / "settings.json"

DATA_LOCK = threading.Lock()
ADMIN_SESSION_COOKIE = "aura_admin_session"
USER_SESSION_COOKIE = "aura_user_session"
SESSION_TTL = 12 * 60 * 60
MAX_UPLOAD_BYTES = 50 * 1024 * 1024

ALLOWED_VIDEO_EXT = {".mp4", ".webm", ".ogg", ".mov"}
ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}


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
        "video_url": "FOTOS/VIDEO DOMINADAS.MOV",
        "file": "",
    },
    {
        "id": "vid_2",
        "tag": "Muscle up",
        "title": "Transición precisa",
        "description": "Explosivo y controlado.",
        "layout": "wide",
        "video_url": "FOTOS/VIDEO MUSCLE UP.MOV",
        "file": "",
    },
    {
        "id": "vid_3",
        "tag": "Pino",
        "title": "Línea en silencio",
        "description": "Balance y respiración.",
        "layout": "",
        "video_url": "FOTOS/VIDEO PINO.mov",
        "file": "",
    },
    {
        "id": "vid_4",
        "tag": "Front lever",
        "title": "Horizonte quieto",
        "description": "Control total en estáticos.",
        "layout": "tall",
        "video_url": "FOTOS/video front LEVER.MOV",
        "file": "",
    },
    {
        "id": "vid_5",
        "tag": "Fondos",
        "title": "Fondo profundo",
        "description": "Ritmo de resistencia brutal.",
        "layout": "wide",
        "video_url": "FOTOS/VIDEO FONDOS.mov",
        "file": "",
    },
    {
        "id": "vid_6",
        "tag": "Back lever",
        "title": "Reversa total",
        "description": "Control posterior con aura.",
        "layout": "",
        "video_url": "FOTOS/VIDEO BACK LEVER.MOV",
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


def load_json(path: Path, default):
    if not path.exists():
        return default
    with DATA_LOCK:
        try:
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except json.JSONDecodeError:
            return default


def save_json(path: Path, data) -> None:
    with DATA_LOCK:
        with path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=True)


def ensure_data_files() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    UPLOAD_DIR.mkdir(exist_ok=True)

    if not EVENTS_PATH.exists():
        save_json(EVENTS_PATH, DEFAULT_EVENTS)

    if not VIDEOS_PATH.exists():
        save_json(VIDEOS_PATH, DEFAULT_VIDEOS)

    if not APPLICATIONS_PATH.exists():
        save_json(APPLICATIONS_PATH, [])

    if not SUBMISSIONS_PATH.exists():
        save_json(SUBMISSIONS_PATH, [])

    if not SESSIONS_PATH.exists():
        save_json(SESSIONS_PATH, {})

    if not SETTINGS_PATH.exists():
        salt, pw_hash = hash_password("admin")
        settings = {
            "admin": {"username": "admin", "salt": salt, "hash": pw_hash},
            "smtp": {
                "enabled": False,
                "host": "",
                "port": 587,
                "username": "",
                "password": "",
                "from_name": "Aura Calistenia",
                "admin_email": "",
                "use_tls": True,
            },
        }
        save_json(SETTINGS_PATH, settings)


def copy_default_plan() -> dict:
    return json.loads(json.dumps(DEFAULT_TRAINING_PLAN))


def normalize_plan(plan: dict | None) -> dict:
    default = copy_default_plan()
    if not isinstance(plan, dict):
        return default
    weeks = plan.get("weeks")
    if not isinstance(weeks, list):
        weeks = []
    normalized = {
        "title": plan.get("title") or default.get("title", "Plan 4 semanas"),
        "weeks": [],
    }
    for index in range(4):
        source_week = weeks[index] if index < len(weeks) and isinstance(weeks[index], dict) else {}
        default_week = default["weeks"][index]
        title = source_week.get("title") or default_week.get("title", f"Semana {index + 1}")
        days = source_week.get("days")
        if not isinstance(days, list):
            days = []
        cleaned = []
        for day in days:
            text = str(day).strip()
            if text:
                cleaned.append(text)
        if len(cleaned) < 7:
            cleaned.extend(default_week["days"][len(cleaned):])
        if len(cleaned) > 7:
            cleaned = cleaned[:7]
        normalized["weeks"].append({"title": title, "days": cleaned})
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


def create_session(username: str, role: str) -> str:
    sessions = load_json(SESSIONS_PATH, {})
    sessions = clean_sessions(sessions)
    token = secrets.token_urlsafe(32)
    sessions[token] = {"user": username, "role": role, "expires": time.time() + SESSION_TTL}
    save_json(SESSIONS_PATH, sessions)
    return token


def delete_session(token: str) -> None:
    sessions = load_json(SESSIONS_PATH, {})
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
    sessions = load_json(SESSIONS_PATH, {})
    sessions = clean_sessions(sessions)
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
    elif status == "smtp":
        text = "Solicitud recibida, pero SMTP no está configurado."
        level = "success"
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
        "event_deleted": "Evento eliminado.",
        "app_approved": "Usuario aprobado.",
        "app_deleted": "Solicitud eliminada.",
        "video_added": "Vídeo guardado.",
        "video_deleted": "Vídeo eliminado.",
        "plan_saved": "Plan de entrenamiento actualizado.",
        "comment_added": "Comentario enviado.",
        "submission_deleted": "Envío eliminado.",
        "smtp_saved": "Configuración SMTP actualizada.",
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
    for app in applications:
        app_id = html.escape(app.get("id", ""))
        username = html.escape(app.get("username", ""))
        email = html.escape(app.get("email", ""))
        skill = html.escape(app.get("skill", ""))
        level = html.escape(app.get("level", ""))
        goal = html.escape(app.get("goal", ""))
        concerns = html.escape(app.get("concerns", ""))
        approved = bool(app.get("approved"))
        status = "Activo" if approved else "Pendiente"
        actions = []
        if not approved:
            actions.append(
                "\n".join(
                    [
                        "  <form action=\"/admin/applications/approve\" method=\"post\">",
                        f"    <input type=\"hidden\" name=\"id\" value=\"{app_id}\">",
                        "    <button class=\"btn glass primary small\" type=\"submit\">Aprobar</button>",
                        "  </form>",
                    ]
                )
            )
        actions.append(
            "\n".join(
                [
                    "  <form action=\"/admin/applications/delete\" method=\"post\">",
                    f"    <input type=\"hidden\" name=\"id\" value=\"{app_id}\">",
                    "    <button class=\"btn glass ghost small\" type=\"submit\">Eliminar</button>",
                    "  </form>",
                ]
            )
        )
        detail_lines = [f"    <strong>{username}</strong>", f"    <span>{email}</span>"]
        if skill:
            detail_lines.append(f"    <span>Skill: {skill}</span>")
        if goal:
            detail_lines.append(f"    <span>Objetivo: {goal}</span>")
        if level:
            detail_lines.append(f"    <span>Nivel: {level}</span>")
        if concerns:
            detail_lines.append(f"    <span>Inquietudes: {concerns}</span>")
        detail_lines.append(f"    <span>Estado: {status}</span>")
        items.append(
            "\n".join(
                [
                    "<li class=\"admin-item\">",
                    "  <div>",
                    "\n".join(detail_lines),
                    "  </div>",
                    f"  <div class=\"admin-actions\">{''.join(actions)}</div>",
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


def plan_week_to_text(week: dict) -> str:
    days = week.get("days")
    if not isinstance(days, list):
        return ""
    return "\n".join([str(day) for day in days])


def render_training_plan(plan: dict) -> str:
    normalized = normalize_plan(plan)
    parts = [
        '<div class="training-board glass-card" data-stagger>',
        f'  <div class="training-head"><h3>{html.escape(normalized.get("title", "Plan de entrenamiento"))}</h3></div>',
        '  <div class="training-grid">',
    ]
    for week_index, week in enumerate(normalized.get("weeks", []), start=1):
        week_title = html.escape(week.get("title", f"Semana {week_index}"))
        parts.append('    <div class="training-week stagger-item">')
        parts.append(f'      <div class="training-week-title">{week_title}</div>')
        parts.append('      <div class="day-grid">')
        days = week.get("days") or []
        for day_index, day_text in enumerate(days, start=1):
            parts.append('        <div class="day-card">')
            parts.append(f'          <span class="day-label">Dia {day_index}</span>')
            parts.append(f'          <p>{html.escape(str(day_text))}</p>')
            parts.append('        </div>')
        parts.append("      </div>")
        parts.append("    </div>")
    parts.append("  </div>")
    parts.append("</div>")
    return "\n".join(parts)


def render_submission_media(submission: dict) -> str:
    file_name = submission.get("file") or ""
    video_url = submission.get("video_url") or ""
    if file_name:
        ext = Path(file_name).suffix.lower()
        src = f"/uploads/{file_name}"
        if ext in ALLOWED_IMAGE_EXT:
            return f'<img src="{html.escape(src)}" alt="{html.escape(submission.get("title", ""))}">'
        return (
            f'<video src="{html.escape(src)}" autoplay loop muted playsinline preload="metadata"></video>'
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


def render_access_section(query: dict[str, list[str]], cookie_header: str | None) -> str:
    access_status = (query.get("access") or [""])[0]
    user_alert = build_access_alert(access_status, "user")
    admin_alert = build_access_alert(access_status, "admin")
    admin_status_alert = build_admin_alert(query)

    admin_user = get_session_user(cookie_header, ADMIN_SESSION_COOKIE, "admin")
    portal_user = get_session_user(cookie_header, USER_SESSION_COOKIE, "user")
    applications = load_applications()
    submissions = load_submissions()

    if not admin_user and not portal_user:
        alert = user_alert or admin_alert
        login_card = "\n".join(
            [
                '<div class="portal-card glass-card stagger-item">',
                "  <h3>Acceso único</h3>",
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
                "</div>",
            ]
        )
        return f'<div class="access-grid" data-stagger>{login_card}</div>'

    if admin_user:
        selected_user = (query.get("plan_user") or [""])[0]
        if not selected_user and applications:
            selected_user = applications[0].get("username", "")
        selected_app = find_application(applications, selected_user) if selected_user else None
        plan = normalize_plan((selected_app or {}).get("plan"))
        plan_title = html.escape(plan.get("title", "Plan de entrenamiento"))

        selector_items = []
        for app in applications:
            username = app.get("username", "")
            label = html.escape(username)
            href = f"/?plan_user={urllib.parse.quote(username)}#acceso"
            selector_items.append(f'<a class="glass-pill" href="{href}">{label}</a>')
        selector_html = (
            f'<div class="user-selector"><span>Selecciona alumno:</span>{"".join(selector_items)}</div>'
            if selector_items
            else '<p class="form-note">No hay alumnos registrados.</p>'
        )

        plan_editor = "\n".join(
            [
                '<div class="admin-card glass-card stagger-item">',
                "  <h3>Plan de entrenamiento por alumno</h3>",
                selector_html,
                "  <form class=\"admin-form\" action=\"/admin/plan/update\" method=\"post\">",
                f"    <input type=\"hidden\" name=\"username\" value=\"{html.escape(selected_user)}\">",
                "    <div class=\"form-field\">",
                "      <label for=\"plan_title\">Título del plan</label>",
                f"      <input id=\"plan_title\" name=\"plan_title\" type=\"text\" value=\"{plan_title}\">",
                "    </div>",
                "    <div class=\"form-field\">",
                "      <label for=\"week1\">Semana 01</label>",
                f"      <textarea id=\"week1\" name=\"week1\" rows=\"7\">{html.escape(plan_week_to_text(plan['weeks'][0]))}</textarea>",
                "    </div>",
                "    <div class=\"form-field\">",
                "      <label for=\"week2\">Semana 02</label>",
                f"      <textarea id=\"week2\" name=\"week2\" rows=\"7\">{html.escape(plan_week_to_text(plan['weeks'][1]))}</textarea>",
                "    </div>",
                "    <div class=\"form-field\">",
                "      <label for=\"week3\">Semana 03</label>",
                f"      <textarea id=\"week3\" name=\"week3\" rows=\"7\">{html.escape(plan_week_to_text(plan['weeks'][2]))}</textarea>",
                "    </div>",
                "    <div class=\"form-field\">",
                "      <label for=\"week4\">Semana 04</label>",
                f"      <textarea id=\"week4\" name=\"week4\" rows=\"7\">{html.escape(plan_week_to_text(plan['weeks'][3]))}</textarea>",
                "    </div>",
                "    <button class=\"btn glass primary\" type=\"submit\">Guardar plan</button>",
                "  </form>",
                "</div>",
            ]
        )

        settings = load_json(SETTINGS_PATH, {})
        smtp = settings.get("smtp", {})
        smtp_host = html.escape(str(smtp.get("host", "")))
        smtp_port = html.escape(str(smtp.get("port", 587)))
        smtp_user = html.escape(str(smtp.get("username", "")))
        smtp_pass = html.escape(str(smtp.get("password", "")))
        smtp_from = html.escape(str(smtp.get("from_name", "Aura Calistenia")))
        smtp_admin = html.escape(str(smtp.get("admin_email", "")))
        smtp_enabled = "checked" if smtp.get("enabled") else ""
        smtp_tls = "checked" if smtp.get("use_tls", True) else ""

        admin_summary = "\n".join(
            [
                '<div class="portal-card glass-card stagger-item">',
                "  <h3>Panel activo</h3>",
                f"  {admin_alert}" if admin_alert else "",
                f"  {admin_status_alert}" if admin_status_alert else "",
                "  <p>Credenciales admin activas. Puedes editar toda la web.</p>",
                "  <form class=\"portal-actions\" action=\"/admin/logout\" method=\"post\">",
                "    <button class=\"btn glass ghost\" type=\"submit\">Cerrar sesión</button>",
                "  </form>",
                "</div>",
            ]
        )

        admin_embed = "\n".join(
            [
                '<div class="admin-embed" data-stagger>',
                '  <div class="admin-card glass-card stagger-item">',
                "    <h3>Solicitudes de alumnos</h3>",
                "    <ul class=\"admin-list\">",
                f"      {render_application_list(applications)}",
                "    </ul>",
                "  </div>",
                plan_editor,
                '  <div class="admin-card glass-card stagger-item">',
                "    <h3>Feedback de vídeos</h3>",
                f"    {render_admin_submissions(submissions)}",
                "  </div>",
                '  <div class="admin-card glass-card stagger-item">',
                "    <h3>Agregar evento</h3>",
                "    <form class=\"admin-form\" action=\"/admin/events/add\" method=\"post\">",
                "      <div class=\"form-field\">",
                "        <label for=\"event_title\">Título</label>",
                "        <input id=\"event_title\" name=\"title\" type=\"text\" required>",
                "      </div>",
                "      <div class=\"form-row\">",
                "        <div class=\"form-field\">",
                "          <label for=\"event_date\">Fecha</label>",
                "          <input id=\"event_date\" name=\"date\" type=\"text\" placeholder=\"Ej: 16-19 ABR 2026\" required>",
                "        </div>",
                "        <div class=\"form-field\">",
                "          <label for=\"event_location\">Lugar</label>",
                "          <input id=\"event_location\" name=\"location\" type=\"text\" placeholder=\"Ciudad, País\" required>",
                "        </div>",
                "      </div>",
                "      <div class=\"form-field\">",
                "        <label for=\"event_desc\">Descripción</label>",
                "        <input id=\"event_desc\" name=\"description\" type=\"text\" required>",
                "      </div>",
                "      <div class=\"form-field\">",
                "        <label for=\"event_tag\">Etiqueta</label>",
                "        <input id=\"event_tag\" name=\"tag\" type=\"text\" placeholder=\"Nacional o Europa\" required>",
                "      </div>",
                "      <button class=\"btn glass primary\" type=\"submit\">Guardar evento</button>",
                "    </form>",
                "  </div>",
                '  <div class="admin-card glass-card stagger-item">',
                "    <h3>Eventos actuales</h3>",
                "    <ul class=\"admin-list\">",
                f"      {render_event_list(load_json(EVENTS_PATH, []))}",
                "    </ul>",
                "  </div>",
                '  <div class="admin-card glass-card stagger-item">',
                "    <h3>Agregar vídeo</h3>",
                "    <form class=\"admin-form\" action=\"/admin/videos/add\" method=\"post\" enctype=\"multipart/form-data\">",
                "      <div class=\"form-field\">",
                "        <label for=\"video_title\">Título</label>",
                "        <input id=\"video_title\" name=\"title\" type=\"text\" required>",
                "      </div>",
                "      <div class=\"form-row\">",
                "        <div class=\"form-field\">",
                "          <label for=\"video_tag\">Etiqueta</label>",
                "          <input id=\"video_tag\" name=\"tag\" type=\"text\" required>",
                "        </div>",
                "        <div class=\"form-field\">",
                "          <label for=\"video_layout\">Diseño</label>",
                "          <select id=\"video_layout\" name=\"layout\">",
                "            <option value=\"\">Normal</option>",
                "            <option value=\"tall\">Tall</option>",
                "            <option value=\"wide\">Wide</option>",
                "          </select>",
                "        </div>",
                "      </div>",
                "      <div class=\"form-field\">",
                "        <label for=\"video_desc\">Descripción</label>",
                "        <input id=\"video_desc\" name=\"description\" type=\"text\" required>",
                "      </div>",
                "      <div class=\"form-field\">",
                "        <label for=\"video_url\">URL externa (opcional)</label>",
                "        <input id=\"video_url\" name=\"video_url\" type=\"url\" placeholder=\"https://\">",
                "      </div>",
                "      <div class=\"form-field\">",
                "        <label for=\"video_file\">Subir archivo (mp4, webm, jpg)</label>",
                "        <input id=\"video_file\" name=\"video_file\" type=\"file\" accept=\"video/mp4,video/webm,video/ogg,image/png,image/jpeg,image/webp\">",
                "      </div>",
                "      <button class=\"btn glass primary\" type=\"submit\">Guardar vídeo</button>",
                "    </form>",
                "    <p class=\"admin-note\">Si no subes archivo, se mostrará un placeholder con enlace.</p>",
                "  </div>",
                '  <div class="admin-card glass-card stagger-item">',
                "    <h3>Vídeos actuales</h3>",
                "    <ul class=\"admin-list\">",
                f"      {render_video_list(load_json(VIDEOS_PATH, []))}",
                "    </ul>",
                "  </div>",
                '  <div class="admin-card glass-card stagger-item">',
                "    <h3>Configuración SMTP</h3>",
                "    <form class=\"admin-form\" action=\"/admin/settings\" method=\"post\">",
                "      <div class=\"form-row\">",
                "        <div class=\"form-field\">",
                "          <label for=\"smtp_host\">Servidor SMTP</label>",
                f"          <input id=\"smtp_host\" name=\"smtp_host\" type=\"text\" value=\"{smtp_host}\" placeholder=\"smtp.tu-dominio.com\">",
                "        </div>",
                "        <div class=\"form-field\">",
                "          <label for=\"smtp_port\">Puerto</label>",
                f"          <input id=\"smtp_port\" name=\"smtp_port\" type=\"number\" value=\"{smtp_port}\">",
                "        </div>",
                "      </div>",
                "      <div class=\"form-row\">",
                "        <div class=\"form-field\">",
                "          <label for=\"smtp_user\">Usuario SMTP</label>",
                f"          <input id=\"smtp_user\" name=\"smtp_user\" type=\"text\" value=\"{smtp_user}\">",
                "        </div>",
                "        <div class=\"form-field\">",
                "          <label for=\"smtp_pass\">Contraseña de aplicación</label>",
                f"          <input id=\"smtp_pass\" name=\"smtp_pass\" type=\"password\" value=\"{smtp_pass}\">",
                "        </div>",
                "      </div>",
                "      <div class=\"form-row\">",
                "        <div class=\"form-field\">",
                "          <label for=\"smtp_from\">Nombre remitente</label>",
                f"          <input id=\"smtp_from\" name=\"smtp_from\" type=\"text\" value=\"{smtp_from}\">",
                "        </div>",
                "        <div class=\"form-field\">",
                "          <label for=\"smtp_admin\">Email admin</label>",
                f"          <input id=\"smtp_admin\" name=\"smtp_admin\" type=\"email\" value=\"{smtp_admin}\">",
                "        </div>",
                "      </div>",
                "      <div class=\"form-row\">",
                "        <label class=\"checkbox-field\">",
                f"          <input type=\"checkbox\" name=\"smtp_enabled\" {smtp_enabled}>",
                "          Activar envío SMTP",
                "        </label>",
                "        <label class=\"checkbox-field\">",
                f"          <input type=\"checkbox\" name=\"smtp_tls\" {smtp_tls}>",
                "          Usar STARTTLS",
                "        </label>",
                "      </div>",
                "      <button class=\"btn glass primary\" type=\"submit\">Guardar SMTP</button>",
                "    </form>",
                "  </div>",
                "</div>",
            ]
        )

        return "\n".join(
            [
                '<div class="access-grid" data-stagger>',
                admin_summary,
                "</div>",
                admin_embed,
            ]
        )

    app = find_application(applications, portal_user) or {}
    skill = html.escape(app.get("skill", "Sin datos"))
    level = html.escape(app.get("level", ""))
    goal = html.escape(app.get("goal", ""))
    plan_html = render_training_plan(app.get("plan", {}))
    submissions_html = render_user_submissions(submissions, portal_user)
    user_summary = "\n".join(
        [
            '<div class="portal-card glass-card stagger-item">',
            "  <h3>Panel activo</h3>",
            f"  {user_alert}" if user_alert else "",
            f"  <p>Bienvenido, {html.escape(portal_user)}.</p>",
            "  <div class=\"portal-meta\">",
            f"    <span>Skill: {skill}</span>",
            f"    <span>Objetivo: {goal or 'Sin datos'}</span>",
            f"    <span>Nivel: {level or 'Sin datos'}</span>",
            "    <span>Estado: Activo</span>",
            "  </div>",
            "  <form class=\"portal-actions\" action=\"/logout\" method=\"post\">",
            "    <button class=\"btn glass ghost\" type=\"submit\">Cerrar sesión</button>",
            "  </form>",
            "</div>",
        ]
    )

    submission_form = "\n".join(
        [
            '<div class="submission-block" data-stagger>',
            '  <div class="submission-card glass-card stagger-item">',
            "    <h3>Sube tu vídeo</h3>",
            "    <p>Envía tus progresos y recibirás feedback técnico.</p>",
            "    <form class=\"admin-form\" action=\"/user/submissions/add\" method=\"post\" enctype=\"multipart/form-data\">",
            "      <div class=\"form-field\">",
            "        <label for=\"submission_title\">Título</label>",
            "        <input id=\"submission_title\" name=\"title\" type=\"text\" required>",
            "      </div>",
            "      <div class=\"form-field\">",
            "        <label for=\"submission_desc\">Descripción</label>",
            "        <input id=\"submission_desc\" name=\"description\" type=\"text\" required>",
            "      </div>",
            "      <div class=\"form-field\">",
            "        <label for=\"submission_url\">URL externa (opcional)</label>",
            "        <input id=\"submission_url\" name=\"video_url\" type=\"url\" placeholder=\"https://\">",
            "      </div>",
            "      <div class=\"form-field\">",
            "        <label for=\"submission_file\">Subir archivo (mp4, webm, jpg)</label>",
            "        <input id=\"submission_file\" name=\"video_file\" type=\"file\" accept=\"video/mp4,video/webm,video/ogg,image/png,image/jpeg,image/webp\">",
            "      </div>",
            "      <button class=\"btn glass primary\" type=\"submit\">Enviar vídeo</button>",
            "    </form>",
            "  </div>",
            "</div>",
        ]
    )

    return "\n".join(
        [
            '<div class="access-grid" data-stagger>',
            user_summary,
            "</div>",
            plan_html,
            submission_form,
            f'<div class="submission-list" data-stagger>{submissions_html}</div>',
        ]
    )


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
            return f'<img src="{html.escape(src)}" alt="{html.escape(video.get("title", ""))}">'
        return (
            f'<video src="{html.escape(src)}" autoplay loop muted playsinline preload="metadata"></video>'
        )
    if video_url:
        ext = Path(video_url).suffix.lower()
        src = html.escape(video_url)
        if ext in ALLOWED_IMAGE_EXT:
            return f'<img src="{src}" alt="{html.escape(video.get("title", ""))}">'
        if ext in ALLOWED_VIDEO_EXT:
            return f'<video src="{src}" autoplay loop muted playsinline preload="metadata"></video>'
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
    for event in events:
        event_id = event.get("id", "")
        title = html.escape(event.get("title", ""))
        meta = html.escape(f"{event.get('date', '')} - {event.get('location', '')}".strip(" -"))
        items.append(
            "\n".join(
                [
                    '<li class="admin-item">',
                    f"  <div><strong>{title}</strong><span>{meta}</span></div>",
                    "  <form action=\"/admin/events/delete\" method=\"post\">",
                    f"    <input type=\"hidden\" name=\"id\" value=\"{html.escape(event_id)}\">",
                    "    <button class=\"btn glass ghost small\" type=\"submit\">Eliminar</button>",
                    "  </form>",
                    "</li>",
                ]
            )
        )
    return "\n".join(items) if items else "<li class=\"admin-item\">Sin eventos.</li>"


def render_video_list(videos: list[dict]) -> str:
    items = []
    for video in videos:
        video_id = video.get("id", "")
        title = html.escape(video.get("title", ""))
        tag = html.escape(video.get("tag", ""))
        layout = html.escape(video.get("layout", "") or "normal")
        items.append(
            "\n".join(
                [
                    '<li class="admin-item">',
                    f"  <div><strong>{title}</strong><span>{tag} - {layout}</span></div>",
                    "  <form action=\"/admin/videos/delete\" method=\"post\">",
                    f"    <input type=\"hidden\" name=\"id\" value=\"{html.escape(video_id)}\">",
                    "    <button class=\"btn glass ghost small\" type=\"submit\">Eliminar</button>",
                    "  </form>",
                    "</li>",
                ]
            )
        )
    return "\n".join(items) if items else "<li class=\"admin-item\">Sin vídeos.</li>"


def render_index(query: dict[str, list[str]], cookie_header: str | None) -> str:
    events = load_json(EVENTS_PATH, [])
    videos = load_json(VIDEOS_PATH, [])
    replacements = {
        "EVENTS": render_events(events),
        "VIDEOS": render_video_cards(videos),
        "FORM_ALERT": build_form_alert(query),
        "ACCESS_CONTENT": render_access_section(query, cookie_header),
    }
    return render_template(INDEX_TEMPLATE, replacements)


def render_admin_page(query: dict[str, list[str]]) -> str:
    events = load_json(EVENTS_PATH, [])
    videos = load_json(VIDEOS_PATH, [])
    settings = load_json(SETTINGS_PATH, {})
    smtp = settings.get("smtp", {})
    replacements = {
        "ADMIN_MESSAGE": build_admin_alert(query),
        "EVENT_LIST": render_event_list(events),
        "VIDEO_LIST": render_video_list(videos),
        "APPLICATION_LIST": render_application_list(load_applications()),
        "SMTP_HOST": html.escape(str(smtp.get("host", ""))),
        "SMTP_PORT": html.escape(str(smtp.get("port", ""))),
        "SMTP_USER": html.escape(str(smtp.get("username", ""))),
        "SMTP_PASS": html.escape(str(smtp.get("password", ""))),
        "SMTP_FROM": html.escape(str(smtp.get("from_name", ""))),
        "SMTP_ADMIN": html.escape(str(smtp.get("admin_email", ""))),
        "SMTP_ENABLED": "checked" if smtp.get("enabled") else "",
        "SMTP_TLS": "checked" if smtp.get("use_tls") else "",
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
            "    <title>Acceso admin - Aura Calistenia</title>",
            "    <link rel=\"preconnect\" href=\"https://fonts.googleapis.com\">",
            "    <link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin>",
            "    <link href=\"https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Space+Grotesk:wght@300;400;500;600;700&display=swap\" rel=\"stylesheet\">",
            "    <link rel=\"stylesheet\" href=\"styles.css\">",
            "  </head>",
            "  <body class=\"admin-body\">",
            "    <div class=\"noise\" aria-hidden=\"true\"></div>",
            "    <header class=\"nav\">",
            "      <div class=\"nav-inner\">",
            "        <nav class=\"nav-group nav-left\"></nav>",
            "        <a class=\"nav-brand\" href=\"/\">",
            "          <span class=\"brand-mark\" aria-hidden=\"true\"></span>",
            "          <span class=\"brand-text\">AURA CALISTENIA</span>",
            "        </a>",
            "        <nav class=\"nav-group nav-right\">",
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


def send_email(smtp_settings: dict, to_email: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    from_name = smtp_settings.get("from_name") or "Aura Calistenia"
    from_email = smtp_settings.get("username") or smtp_settings.get("admin_email") or ""
    msg["From"] = f"{from_name} <{from_email}>" if from_email else from_name
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    host = smtp_settings.get("host")
    port = int(smtp_settings.get("port", 587))
    username = smtp_settings.get("username")
    password = smtp_settings.get("password")
    use_tls = smtp_settings.get("use_tls", True)

    with smtplib.SMTP(host, port, timeout=10) as server:
        if use_tls:
            server.starttls()
        if username and password:
            server.login(username, password)
        server.send_message(msg)


def notify_application(application: dict, smtp_settings: dict) -> tuple[bool, str]:
    if not smtp_settings.get("enabled"):
        return False, "smtp_disabled"
    required = [smtp_settings.get("host"), smtp_settings.get("username"), smtp_settings.get("password")]
    if not all(required):
        return False, "smtp_incomplete"

    admin_email = smtp_settings.get("admin_email") or smtp_settings.get("username")
    if not admin_email:
        return False, "smtp_incomplete"

    admin_subject = "Nueva solicitud de entreno"
    admin_body = (
        "Nueva solicitud registrada:\n"
        f"Usuario: {application.get('username')}\n"
        f"Email: {application.get('email')}\n"
        f"Skill: {application.get('skill')}\n"
        f"Objetivo: {application.get('goal', '')}\n"
    )

    user_subject = "Solicitud recibida - Aura Calistenia"
    user_body = (
        "Tu solicitud fue recibida.\n\n"
        f"Skill: {application.get('skill')}\n"
        f"Objetivo: {application.get('goal', '')}\n"
        "Te contactaremos para confirmar tu acceso."
    )

    try:
        send_email(smtp_settings, admin_email, admin_subject, admin_body)
        send_email(smtp_settings, application.get("email", ""), user_subject, user_body)
    except Exception:
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


class AuraHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    def send_html(self, content: str, status: int = HTTPStatus.OK) -> None:
        encoded = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

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
                self.send_html(render_login_page())
            return

        if path == "/admin.html":
            self.redirect("/admin")
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

        if path == "/user/submissions/add":
            self.handle_submission_add()
            return

        admin_user = get_session_user(self.headers.get("Cookie"), ADMIN_SESSION_COOKIE, "admin")
        if not admin_user:
            self.send_error(HTTPStatus.FORBIDDEN)
            return

        if path == "/admin/events/add":
            self.handle_event_add()
            return

        if path == "/admin/events/delete":
            self.handle_event_delete()
            return

        if path == "/admin/videos/add":
            self.handle_video_add()
            return

        if path == "/admin/videos/delete":
            self.handle_video_delete()
            return

        if path == "/admin/settings":
            self.handle_settings_update()
            return

        if path == "/admin/plan/update":
            self.handle_plan_update()
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

        settings = load_json(SETTINGS_PATH, {})
        smtp_settings = settings.get("smtp", {})
        ok, reason = notify_application(application, smtp_settings)
        if ok:
            self.redirect("/?status=ok")
            return
        if reason in {"smtp_disabled", "smtp_incomplete"}:
            self.redirect("/?status=smtp")
            return
        self.redirect("/?status=error&message=Error enviando email")

    def handle_admin_login(self) -> None:
        data, _ = parse_post_data(self)
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()
        settings = load_json(SETTINGS_PATH, {})
        admin = settings.get("admin", {})
        if username != admin.get("username"):
            self.redirect("/?access=admin_error#acceso")
            return
        if not verify_password(password, admin.get("salt", ""), admin.get("hash", "")):
            self.redirect("/?access=admin_error#acceso")
            return

        token = create_session(username, "admin")
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header(
            "Set-Cookie",
            f"{ADMIN_SESSION_COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax",
        )
        self.send_header("Location", "/?access=admin_ok#acceso")
        self.end_headers()

    def handle_admin_logout(self) -> None:
        cookie_header = self.headers.get("Cookie")
        user = get_session_user(cookie_header, ADMIN_SESSION_COOKIE, "admin")
        token = get_cookie_token(cookie_header, ADMIN_SESSION_COOKIE)
        if user and token:
            delete_session(token)
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Set-Cookie", f"{ADMIN_SESSION_COOKIE}=deleted; Path=/; Max-Age=0")
        self.send_header("Location", "/?access=admin_logout#acceso")
        self.end_headers()

    def handle_login(self) -> None:
        data, _ = parse_post_data(self)
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()
        if not username or not password:
            self.redirect("/?access=user_missing#acceso")
            return

        settings = load_json(SETTINGS_PATH, {})
        admin = settings.get("admin", {})
        if username == admin.get("username"):
            if verify_password(password, admin.get("salt", ""), admin.get("hash", "")):
                token = create_session(username, "admin")
                self.send_response(HTTPStatus.SEE_OTHER)
                self.send_header(
                    "Set-Cookie",
                    f"{ADMIN_SESSION_COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax",
                )
                self.send_header("Location", "/?access=admin_ok#acceso")
                self.end_headers()
                return
            self.redirect("/?access=admin_error#acceso")
            return

        applications = load_applications()
        app = find_application(applications, username)
        if not app:
            self.redirect("/?access=user_error#acceso")
            return
        if not verify_password(password, app.get("salt", ""), app.get("hash", "")):
            self.redirect("/?access=user_error#acceso")
            return
        if not app.get("approved"):
            self.redirect("/?access=user_pending#acceso")
            return

        token = create_session(username, "user")
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header(
            "Set-Cookie",
            f"{USER_SESSION_COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax",
        )
        self.send_header("Location", "/?access=user_ok#acceso")
        self.end_headers()

    def handle_user_logout(self) -> None:
        cookie_header = self.headers.get("Cookie")
        user = get_session_user(cookie_header, USER_SESSION_COOKIE, "user")
        token = get_cookie_token(cookie_header, USER_SESSION_COOKIE)
        if user and token:
            delete_session(token)
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Set-Cookie", f"{USER_SESSION_COOKIE}=deleted; Path=/; Max-Age=0")
        self.send_header("Location", "/?access=user_logout#acceso")
        self.end_headers()

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

    def handle_settings_update(self) -> None:
        data, _ = parse_post_data(self)
        settings = load_json(SETTINGS_PATH, {})
        smtp = settings.get("smtp", {})
        try:
            port = int(data.get("smtp_port", 587) or 587)
        except ValueError:
            port = 587
        smtp.update(
            {
                "host": data.get("smtp_host", "").strip(),
                "port": port,
                "username": data.get("smtp_user", "").strip(),
                "password": data.get("smtp_pass", "").strip(),
                "from_name": data.get("smtp_from", "").strip() or "Aura Calistenia",
                "admin_email": data.get("smtp_admin", "").strip(),
                "enabled": "smtp_enabled" in data,
                "use_tls": "smtp_tls" in data,
            }
        )
        settings["smtp"] = smtp
        save_json(SETTINGS_PATH, settings)
        self.admin_redirect("smtp_saved")

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
        for index in range(4):
            raw = data.get(f"week{index + 1}", "")
            if not raw:
                continue
            lines = [line.strip() for line in raw.splitlines() if line.strip()]
            if len(lines) < 7:
                lines.extend(plan["weeks"][index]["days"][len(lines):])
            if len(lines) > 7:
                lines = lines[:7]
            plan["weeks"][index]["days"] = lines
        app["plan"] = plan
        save_json(APPLICATIONS_PATH, applications)
        plan_param = urllib.parse.quote(username)
        self.redirect(f"/?admin_status=plan_saved&plan_user={plan_param}#acceso")

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


def run_server(port: int | None = None) -> None:
    ensure_data_files()
    if port is None:
        port = int(os.environ.get("PORT", "8000"))
    server_address = ("", port)
    httpd = ThreadingHTTPServer(server_address, AuraHandler)
    print(f"Serving on http://localhost:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run_server()
