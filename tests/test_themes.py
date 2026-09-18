import pytest

import settings_store as store
from themes import (
    DEFAULT_THEMES,
    compiled_relevance,
    list_themes,
    replace_themes,
    save_themes,
)


@pytest.fixture
def themes_db(tmp_path, monkeypatch):
    db = tmp_path / "themes.db"
    monkeypatch.setattr(store, "DB_PATH", db)
    monkeypatch.setattr(store, "SOURCES_FILE", tmp_path / "sources.json")
    monkeypatch.setattr(store, "ENV_FILE", tmp_path / ".env")
    store.init_db()
    return db


def test_list_themes_seeds_defaults_in_catalog_order(themes_db):
    rows = list_themes()
    assert len(rows) == len(DEFAULT_THEMES)
    assert [r["id"] for r in rows] == [t["id"] for t in DEFAULT_THEMES]
    assert all(r["enabled"] for r in rows)
    assert [r["rank"] for r in rows] == list(range(1, len(DEFAULT_THEMES) + 1))


def test_list_themes_sorted_by_rank(themes_db):
    list_themes()
    save_themes(
        [
            {
                "id": "economia",
                "label_en": "Economy",
                "label_pt": "economia",
                "rank": 1,
                "enabled": True,
            },
            {
                "id": "política",
                "label_en": "Politics",
                "label_pt": "política",
                "rank": 2,
                "enabled": True,
            },
        ]
    )
    rows = list_themes()
    assert rows[0]["id"] == "economia"
    assert rows[1]["id"] == "política"
    assert [r["rank"] for r in rows] == sorted(r["rank"] for r in rows)


def test_list_themes_persists_enabled_flag(themes_db):
    list_themes()
    save_themes(
        [
            {
                "id": "tecnologia",
                "label_en": "Technology",
                "label_pt": "tecnologia",
                "rank": 4,
                "enabled": False,
            },
        ]
    )
    tech = next(r for r in list_themes() if r["id"] == "tecnologia")
    assert tech["enabled"] is False


def test_save_themes_upserts_by_id(themes_db):
    list_themes()
    rows = save_themes(
        [
            {
                "id": "política",
                "label_en": "Politics revised",
                "label_pt": "política revisada",
                "rank": 42,
                "enabled": True,
            },
        ]
    )
    pol = next(r for r in rows if r["id"] == "política")
    assert pol["label_en"] == "Politics revised"
    assert pol["label_pt"] == "política revisada"
    assert pol["rank"] == 42
    assert len(rows) == len(DEFAULT_THEMES)


def test_compiled_relevance_prefers_high_rank_theme():
    ranked = ["economia", "esportes"]
    high_econ = compiled_relevance({"economia": 1.0, "esportes": 0.0}, ranked)
    high_sport = compiled_relevance({"economia": 0.0, "esportes": 1.0}, ranked)
    assert high_econ > high_sport
    assert 0 <= high_econ <= 100


def test_compiled_relevance_missing_theme_is_zero():
    assert compiled_relevance({}, ["economia"]) == 0


def test_replace_themes_drops_omitted_ids(themes_db):
    list_themes()
    rows = replace_themes(
        [
            {
                "id": "economia",
                "label_en": "Economy",
                "label_pt": "economia",
                "rank": 99,
                "enabled": True,
            },
            {
                "id": "mundo",
                "label_en": "World",
                "label_pt": "mundo",
                "rank": 1,
                "enabled": True,
            },
        ]
    )
    assert len(rows) == 2
    assert rows[0]["id"] == "mundo"
    assert rows[0]["rank"] == 1
    assert rows[1]["id"] == "economia"
    assert rows[1]["rank"] == 2


def test_replace_themes_slug_new_id_from_label(themes_db):
    list_themes()
    rows = replace_themes(
        [
            {
                "label_en": "Space News",
                "label_pt": "espaço",
                "rank": 1,
                "enabled": True,
            },
        ]
    )
    assert len(rows) == 1
    assert rows[0]["id"] == "space-news"
    assert rows[0]["label_en"] == "Space News"


def test_default_theme_ids_match_legacy_temas():
    from tags import TEMAS

    assert {t["id"] for t in DEFAULT_THEMES} == set(TEMAS)
