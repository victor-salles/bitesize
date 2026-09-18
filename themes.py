"""Jev theme catalog (ranked interests) and compiled relevance."""

from __future__ import annotations

from typing import Any

from settings_store import _get_connection, init_db

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


def compiled_relevance(
    tema_scores: dict[str, float],
    ranked_ids: list[str] | None = None,
) -> int:
    ids = list(ranked_ids or [])
    if not ids:
        return 0
    n = len(ids)
    total_w = 0.0
    acc = 0.0
    for i, tid in enumerate(ids):
        w = n - i
        total_w += w
        acc += float(tema_scores.get(tid) or 0) * w
    return max(0, min(100, int(round(100 * acc / total_w))))
