import json

import jev_log


def test_write_run_stores_json_and_list_summaries(tmp_path, monkeypatch):
    monkeypatch.setattr(jev_log, "JEV_DIR", tmp_path)
    articles = [
        {
            "title": "Kept",
            "source": "G1",
            "category": "Brasil",
            "link": "https://g1.example/a",
            "skip": False,
            "skip_reason": None,
            "relevance": 80,
            "tipo": "artigo-completo",
            "temas": ["economia"],
            "jev": {
                "answers": {"ad": 0.02, "keep": 0.9, "temas": {"economia": 0.8}},
                "judgment": {"skip": False, "relevance": 80},
            },
        },
        {
            "title": "Ad",
            "source": "Shop",
            "skip": True,
            "skip_reason": "ad",
            "jev": {"answers": {"ad": 0.95}, "judgment": {"skip": True, "skip_reason": "ad"}},
        },
        {
            "title": "Broken",
            "source": "X",
            "skip": False,
            "jev_error": "timeout",
        },
    ]
    run = jev_log.write_run(articles, min_keep=0, workers=4)
    assert run["skipped"] == 1
    assert run["errors"] == 1
    assert run["kept"] == 2
    path = tmp_path / f"{run['id']}.json"
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["items"][0]["jev"]["answers"]["ad"] == 0.02
    assert data["items"][1]["skip_reason"] == "ad"
    assert data["items"][2]["error"] == "timeout"

    listed = jev_log.list_runs()
    assert listed[0]["id"] == run["id"]
    assert listed[0]["article_count"] == 3
    assert "items" not in listed[0]

    loaded = jev_log.load_run(run["id"])
    assert loaded["items"][0]["title"] == "Kept"


def test_load_run_rejects_unknown_and_unsafe_ids(tmp_path, monkeypatch):
    monkeypatch.setattr(jev_log, "JEV_DIR", tmp_path)
    assert jev_log.load_run("missing") is None
    assert jev_log.load_run("../etc/passwd") is None
