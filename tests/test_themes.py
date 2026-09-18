from themes import compiled_relevance, DEFAULT_THEMES


def test_compiled_relevance_prefers_high_rank_theme():
    ranked = ["economia", "esportes"]
    high_econ = compiled_relevance({"economia": 1.0, "esportes": 0.0}, ranked)
    high_sport = compiled_relevance({"economia": 0.0, "esportes": 1.0}, ranked)
    assert high_econ > high_sport
    assert 0 <= high_econ <= 100


def test_compiled_relevance_missing_theme_is_zero():
    assert compiled_relevance({}, ["economia"]) == 0


def test_default_theme_ids_match_legacy_temas():
    from tags import TEMAS

    assert {t["id"] for t in DEFAULT_THEMES} == set(TEMAS)
