#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

try:
    import psycopg2
except Exception as exc:  # pragma: no cover - local dependency guard
    print(f"Missing psycopg2: {exc}", file=sys.stderr)
    sys.exit(2)


DEFAULT_KEYS = ("applications.json", "chats.json", "submissions.json")
TABLE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Audit and recover AuraCalistenia JSON state between two Neon branches. "
            "Dry-run by default; writes to target only with --restore."
        )
    )
    parser.add_argument(
        "--source-url",
        default=os.environ.get("SOURCE_DATABASE_URL", ""),
        help="Neon connection URL for the branch that still has the data.",
    )
    parser.add_argument(
        "--target-url",
        default=os.environ.get("TARGET_DATABASE_URL") or os.environ.get("DATABASE_URL", ""),
        help="Neon connection URL used by production/Render.",
    )
    parser.add_argument(
        "--table",
        default=os.environ.get("AURA_DB_TABLE", "aura_state"),
        help="State table name. Default: aura_state.",
    )
    parser.add_argument(
        "--keys",
        nargs="+",
        default=list(DEFAULT_KEYS),
        help="State keys to compare/restore.",
    )
    parser.add_argument(
        "--restore",
        action="store_true",
        help="Actually write recovered state to the target branch.",
    )
    parser.add_argument(
        "--mode",
        choices=("add-missing", "replace-matching", "replace-all"),
        default="add-missing",
        help=(
            "Restore strategy for list values. add-missing preserves target records; "
            "replace-matching updates records with same id/username; replace-all copies source exactly."
        ),
    )
    parser.add_argument(
        "--allow-empty-source",
        action="store_true",
        help="Allow restoring even if source applications.json is empty.",
    )
    parser.add_argument(
        "--show-users",
        action="store_true",
        help="Print usernames found in applications.json.",
    )
    return parser.parse_args()


def connect(url: str):
    conn = psycopg2.connect(url, connect_timeout=10)
    conn.autocommit = True
    return conn


def load_key(conn, table: str, key: str):
    with conn.cursor() as cur:
        cur.execute(f"SELECT value, updated_at FROM {table} WHERE key = %s LIMIT 1", (key,))
        row = cur.fetchone()
    if not row:
        return None, None
    value, updated_at = row
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            pass
    return value, updated_at


def save_key(conn, table: str, key: str, value) -> None:
    payload = json.dumps(value, ensure_ascii=True)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO {table} (key, value, updated_at)
            VALUES (%s, %s::jsonb, NOW())
            ON CONFLICT (key)
            DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
            """,
            (key, payload),
        )


def count_value(value) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict):
        return len(value)
    if value is None:
        return 0
    return 1


def record_identity(record: dict) -> tuple[str, str] | None:
    username = str(record.get("username", "")).strip().lower()
    if username:
        return ("username", username)
    record_id = str(record.get("id", "")).strip()
    if record_id:
        return ("id", record_id)
    return None


def merge_lists(source: list, target: list, mode: str) -> list:
    if mode == "replace-all":
        return source
    if not isinstance(target, list):
        target = []
    merged = list(target)
    target_positions = {}
    for index, item in enumerate(merged):
        if isinstance(item, dict):
            identity = record_identity(item)
            if identity:
                target_positions[identity] = index
    for item in source:
        if not isinstance(item, dict):
            if item not in merged:
                merged.append(item)
            continue
        identity = record_identity(item)
        if identity and identity in target_positions:
            if mode == "replace-matching":
                merged[target_positions[identity]] = item
            continue
        merged.append(item)
        if identity:
            target_positions[identity] = len(merged) - 1
    return merged


def merge_values(source, target, mode: str):
    if mode == "replace-all":
        return source
    if isinstance(source, list):
        return merge_lists(source, target if isinstance(target, list) else [], mode)
    if isinstance(source, dict):
        if not isinstance(target, dict) or mode == "replace-matching":
            return source
        merged = dict(target)
        for key, value in source.items():
            merged.setdefault(key, value)
        return merged
    return source if target in (None, "", [], {}) else target


def summarize_key(label: str, key: str, value, updated_at, show_users: bool) -> None:
    updated = updated_at.isoformat() if hasattr(updated_at, "isoformat") else str(updated_at or "-")
    print(f"{label} {key}: count={count_value(value)} updated_at={updated}")
    if key == "applications.json" and isinstance(value, list):
        approved = sum(1 for item in value if isinstance(item, dict) and item.get("approved"))
        print(f"{label} {key}: approved={approved}")
        if show_users:
            users = [
                str(item.get("username", "")).strip()
                for item in value
                if isinstance(item, dict) and str(item.get("username", "")).strip()
            ]
            print(f"{label} {key}: users={users}")


def write_backup(root: Path, side: str, key: str, value, updated_at) -> None:
    safe_key = key.replace("/", "_")
    payload = {
        "key": key,
        "side": side,
        "updated_at": updated_at.isoformat() if hasattr(updated_at, "isoformat") else str(updated_at or ""),
        "value": value,
    }
    (root / f"{side}-{safe_key}").write_text(
        json.dumps(payload, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    if not args.source_url or not args.target_url:
        print(
            "Set SOURCE_DATABASE_URL and TARGET_DATABASE_URL, or pass --source-url and --target-url.",
            file=sys.stderr,
        )
        return 2
    if not TABLE_RE.fullmatch(args.table):
        print(f"Invalid table name: {args.table}", file=sys.stderr)
        return 2

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root = Path("recovery_backups") / stamp
    backup_root.mkdir(parents=True, exist_ok=True)

    with connect(args.source_url) as source_conn, connect(args.target_url) as target_conn:
        source_rows = {}
        target_rows = {}
        for key in args.keys:
            source_value, source_updated = load_key(source_conn, args.table, key)
            target_value, target_updated = load_key(target_conn, args.table, key)
            source_rows[key] = (source_value, source_updated)
            target_rows[key] = (target_value, target_updated)
            summarize_key("SOURCE", key, source_value, source_updated, args.show_users)
            summarize_key("TARGET", key, target_value, target_updated, args.show_users)
            write_backup(backup_root, "source", key, source_value, source_updated)
            write_backup(backup_root, "target", key, target_value, target_updated)

        source_apps = source_rows.get("applications.json", (None, None))[0]
        if args.restore and not args.allow_empty_source:
            if not isinstance(source_apps, list) or not source_apps:
                print("Refusing restore: source applications.json is empty.", file=sys.stderr)
                return 3

        if not args.restore:
            print(f"Dry-run complete. Backups written to {backup_root}")
            print("Add --restore only after confirming SOURCE is the correct branch.")
            return 0

        for key in args.keys:
            source_value, _ = source_rows[key]
            target_value, _ = target_rows[key]
            if source_value is None:
                print(f"Skipping {key}: missing in source.")
                continue
            next_value = merge_values(source_value, target_value, args.mode)
            save_key(target_conn, args.table, key, next_value)
            print(f"Restored {key}: mode={args.mode} count={count_value(next_value)}")

    print(f"Restore complete. Pre-restore backups written to {backup_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
