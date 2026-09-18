"""Jev theme catalog (ranked interests) and compiled relevance."""

from __future__ import annotations

import re
from typing import Any

from settings_store import _get_connection, init_db

_THEME_ID_RE = re.compile(r"^[a-z0-9_-]+$")

DEFAULT_THEMES: list[dict[str, str]] = [
    {"id": "política", "label_en": "Politics", "label_pt": "política"},
    {"id": "saúde", "label_en": "Health", "label_pt": "saúde"},
    {"id": "economia", "label_en": "Economy", "label_pt": "economia"},
    {"id": "tecnologia", "label_en": "Technology", "label_pt": "tecnologia"},
    {"id": "mundo", "label_en": "World", "label_pt": "mundo"},
    {"id": "brasil", "label_en": "Brazil", "label_pt": "brasil"},
    {"id": "cultura", "label_en": "Culture", "label_pt": "cultura"},
    {"id": "esportes", "label_en": "Sports", "label_pt": "esportes"},
    {"id": "ciência", "label_en": "Science", "label_pt": "ciência"},
    {"id": "opinião", "label_en": "Opinion", "label_pt": "opinião"},
    {"id": "clima", "label_en": "Climate", "label_pt": "clima"},
]

_LEGACY_IDS = frozenset(t["id"] for t in DEFAULT_THEMES)


def _row_to_theme(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "label_en": row["label_en"],
        "label_pt": row["label_pt"],
        "rank": int(row["rank"]),
        "enabled": bool(row["enabled"]),
    }


def _seed_default_themes(conn: Any) -> None:
    for i, theme in enumerate(DEFAULT_THEMES, start=1):
        conn.execute(
            """
            INSERT INTO jev_themes (id, label_en, label_pt, rank, enabled)
            VALUES (?, ?, ?, ?, 1)
            """,
            (theme["id"], theme["label_en"], theme["label_pt"], i),
        )


def list_themes() -> list[dict[str, Any]]:
    init_db()
    with _get_connection() as conn:
        rows = conn.execute(
            "SELECT id, label_en, label_pt, rank, enabled FROM jev_themes ORDER BY rank"
        ).fetchall()
        if not rows:
            _seed_default_themes(conn)
            rows = conn.execute(
                "SELECT id, label_en, label_pt, rank, enabled FROM jev_themes ORDER BY rank"
            ).fetchall()
    return [_row_to_theme(r) for r in rows]


def save_themes(themes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    init_db()
    with _get_connection() as conn:
        for theme in themes:
            conn.execute(
                """
                INSERT INTO jev_themes (id, label_en, label_pt, rank, enabled)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    label_en = excluded.label_en,
                    label_pt = excluded.label_pt,
                    rank = excluded.rank,
                    enabled = excluded.enabled
                """,
                (
                    theme["id"],
                    theme["label_en"],
                    theme["label_pt"],
                    int(theme["rank"]),
                    1 if theme.get("enabled", True) else 0,
                ),
            )
    return list_themes()


def _slug_from_label_en(label_en: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", label_en.lower().strip())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "theme"


def _is_valid_theme_id(theme_id: str) -> bool:
    if theme_id in _LEGACY_IDS:
        return True
    return bool(_THEME_ID_RE.match(theme_id))


def replace_themes(themes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    init_db()
    ordered = sorted(themes, key=lambda t: int(t.get("rank") or 0))
    used_ids: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for i, theme in enumerate(ordered, start=1):
        raw_id = (theme.get("id") or "").strip()
        if raw_id:
            if not _is_valid_theme_id(raw_id):
                raise ValueError(f"invalid theme id: {raw_id}")
            tid = raw_id
        else:
            base = _slug_from_label_en(str(theme.get("label_en") or ""))
            tid = base
            n = 2
            while tid in used_ids:
                tid = f"{base}-{n}"
                n += 1
        used_ids.add(tid)
        normalized.append(
            {
                "id": tid,
                "label_en": str(theme.get("label_en") or "").strip(),
                "label_pt": str(theme.get("label_pt") or "").strip(),
                "rank": i,
                "enabled": bool(theme.get("enabled", True)),
            }
        )
    with _get_connection() as conn:
        if normalized:
            placeholders = ",".join("?" * len(normalized))
            conn.execute(
                f"DELETE FROM jev_themes WHERE id NOT IN ({placeholders})",
                [t["id"] for t in normalized],
            )
        else:
            conn.execute("DELETE FROM jev_themes")
        for theme in normalized:
            conn.execute(
                """
                INSERT INTO jev_themes (id, label_en, label_pt, rank, enabled)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    label_en = excluded.label_en,
                    label_pt = excluded.label_pt,
                    rank = excluded.rank,
                    enabled = excluded.enabled
                """,
                (
                    theme["id"],
                    theme["label_en"],
                    theme["label_pt"],
                    theme["rank"],
                    1 if theme["enabled"] else 0,
                ),
            )
    return list_themes()


def compiled_relevance(
    tema_scores: dict[str, float],
    ranked_ids: list[str] | None = None,
) -> int:
    ids = list(ranked_ids or [])
    if not ids:
        return 0
    n = len(ids)
    max_w = float(n)
    acc = 0.0
    for i, tid in enumerate(ids):
        w = n - i
        acc += float(tema_scores.get(tid) or 0) * w
    return max(0, min(100, int(round(100 * acc / max_w))))
