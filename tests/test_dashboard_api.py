import io
import time

import pytest

import dashboard
import settings_store as store


@pytest.fixture
def client(tmp_path, monkeypatch):
    db = tmp_path / "dash.db"
    token_file = tmp_path / "dashboard.token"
    monkeypatch.setattr(store, "DB_PATH", db)
    monkeypatch.setattr(store, "SOURCES_FILE", tmp_path / "sources.json")
    monkeypatch.setattr(store, "ENV_FILE", tmp_path / ".env")
    monkeypatch.setattr(dashboard, "TOKEN_FILE", token_file)
    monkeypatch.setattr(dashboard, "DASHBOARD_TOKEN", "test-token")
    store.init_db()
    dashboard.app.config["TESTING"] = True
    return dashboard.app.test_client()


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.get_json()["ok"] is True


def test_get_settings(client):
    r = client.get("/api/settings")
    assert r.status_code == 200
    data = r.get_json()
    assert "ai" in data
    assert data["ai"]["ai_backend"] in ("gemini", "ollama", "antigravity")
    assert data["ai"]["jev_triage_enabled"] is False


def test_put_settings(client):
    r = client.put(
        "/api/settings",
        json={"ai_backend": "ollama", "jev_triage_enabled": True, "jev_min_keep": 40},
        headers={"Authorization": "Bearer test-token"},
    )
    assert r.status_code == 200
    s = store.load_settings()
    assert s.ai_backend == "ollama"
    assert s.jev_triage_enabled is True
    assert s.jev_min_keep == 40


def test_sources_crud(client):
    auth = {"Authorization": "Bearer test-token"}
    r = client.post("/api/categories", json={"name": "Tech"}, headers=auth)
    assert r.status_code == 201
    cat_id = r.get_json()["id"]

    r = client.post(
        "/api/feeds",
        json={"category_id": cat_id, "name": "HN", "url": "https://hnrss.org/frontpage"},
        headers=auth,
    )
    assert r.status_code == 201
    feed_id = r.get_json()["id"]

    r = client.get("/api/sources")
    cats = r.get_json()["categories"]
    assert cats[0]["feeds"][0]["name"] == "HN"

    r = client.put("/api/feeds/" + str(feed_id), json={"enabled": False}, headers=auth)
    assert r.status_code == 200

    r = client.delete("/api/feeds/" + str(feed_id), headers=auth)
    assert r.status_code == 200


def test_kindle_test_missing_settings(client, monkeypatch):
    monkeypatch.setattr(
        dashboard,
        "send_test_email",
        lambda s: (False, "Missing settings: kindle_email"),
    )
    r = client.post("/api/kindle/test", headers={"Authorization": "Bearer test-token"})
    assert r.status_code == 400
    assert r.get_json()["ok"] is False


def test_get_settings_masks_smtp_password(client):
    store.set_setting("smtp_password", "super-secret")
    r = client.get("/api/settings")
    assert r.get_json()["kindle"]["smtp_password"] == ""
    assert r.get_json()["kindle"]["smtp_password_set"] is True


def test_put_settings_requires_token(client):
    r = client.put("/api/settings", json={"ai_backend": "ollama"})
    assert r.status_code == 401
    r = client.put(
        "/api/settings",
        json={"ai_backend": "gemini"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert r.status_code == 200


def test_jev_runs_api_lists_and_loads_json(client, tmp_path, monkeypatch):
    import jev_log

    monkeypatch.setattr(jev_log, "JEV_DIR", tmp_path / "jev")
    jev_log.write_run(
        [
            {
                "title": "Story",
                "source": "G1",
                "skip": False,
                "relevance": 70,
                "jev": {"answers": {"ad": 0.01, "keep": 0.8}},
            }
        ],
        min_keep=0,
        workers=2,
    )
    listed = client.get("/api/jev/runs")
    assert listed.status_code == 200
    runs = listed.get_json()["runs"]
    assert len(runs) == 1
    run_id = runs[0]["id"]
    detail = client.get("/api/jev/runs/" + run_id)
    assert detail.status_code == 200
    body = detail.get_json()
    assert body["items"][0]["title"] == "Story"
    assert body["items"][0]["jev"]["answers"]["keep"] == 0.8
    missing = client.get("/api/jev/runs/../secret")
    assert missing.status_code == 404


def test_jev_run_includes_theme_catalog(client, tmp_path, monkeypatch):
    import jev_log
    from themes import list_themes

    monkeypatch.setattr(jev_log, "JEV_DIR", tmp_path / "jev")
    jev_log.write_run(
        [{"title": "Story", "source": "G1", "skip": False, "relevance": 50}],
    )
    run_id = client.get("/api/jev/runs").get_json()["runs"][0]["id"]
    detail = client.get("/api/jev/runs/" + run_id)
    assert detail.status_code == 200
    body = detail.get_json()
    assert "themes" in body
    assert body["themes"] == list_themes()


def test_jev_label_save_and_export(client, tmp_path, monkeypatch):
    import jev_labels
    import jev_log

    monkeypatch.setattr(jev_log, "JEV_DIR", tmp_path / "jev")
    monkeypatch.setattr(jev_labels, "LABELS_PATH", tmp_path / "jev_labels.json")
    jev_log.write_run(
        [
            {
                "title": "Story",
                "source": "G1",
                "link": "https://ex.com/s",
                "skip": False,
                "relevance": 70,
                "tipo": "resumo",
                "temas": ["mundo"],
                "jev": {"answers": {"keep": 0.8, "ad": 0.01}},
            }
        ]
    )
    run_id = client.get("/api/jev/runs").get_json()["runs"][0]["id"]
    denied = client.post(
        "/api/jev/labels",
        json={"run_id": run_id, "index": 0, "ad": 0.15},
    )
    assert denied.status_code == 401
    saved = client.post(
        "/api/jev/labels",
        json={"run_id": run_id, "index": 0, "ad": 0.15, "relevance": 20},
        headers={"Authorization": "Bearer test-token"},
    )
    assert saved.status_code == 200
    assert saved.get_json()["human"]["ad"] == 0.15
    detail = client.get("/api/jev/runs/" + run_id)
    assert detail.get_json()["items"][0]["human"]["ad"] == 0.15
    assert "themes" in detail.get_json()
    export = client.get("/api/jev/labels/export")
    assert export.status_code == 200
    rows = export.get_json()["rows"]
    assert rows[0]["label"]["ad"] == 0.15
    assert rows[0]["predicted"]["ad"] == 0.01



def test_resolve_dashboard_token_from_file(tmp_path, monkeypatch):
    token_file = tmp_path / "dashboard.token"
    token_file.write_text("file-token\n", encoding="utf-8")
    monkeypatch.delenv("DASHBOARD_TOKEN", raising=False)
    monkeypatch.setattr(dashboard, "TOKEN_FILE", token_file)
    assert dashboard._resolve_dashboard_token() == "file-token"


def test_preview_returns_headlines(client, monkeypatch):
    auth = {"Authorization": "Bearer test-token"}
    r = client.post("/api/categories", json={"name": "Brazil"}, headers=auth)
    cat_id = r.get_json()["id"]
    client.post(
        "/api/feeds",
        json={
            "category_id": cat_id,
            "name": "Veja",
            "url": "https://veja.abril.com.br/feed/",
        },
        headers=auth,
    )

    def fake_preview(sources, fetch_fn=None, max_headlines=40):
        from preview import PREVIEW_FETCH_LIMIT
        assert max_headlines == PREVIEW_FETCH_LIMIT
        return {
            "categories": [
                {
                    "id": cat_id,
                    "name": "Brazil",
                    "feeds": [
                        {
                            "id": 1,
                            "name": "Veja",
                            "enabled": True,
                            "headlines": [{"title": "Capa", "url": "https://x", "published": "09:00"}],
                            "error": "",
                        }
                    ],
                }
            ]
        }

    monkeypatch.setattr(dashboard, "build_source_preview", fake_preview)
    r = client.get("/api/preview")
    assert r.status_code == 200
    assert r.get_json()["categories"][0]["feeds"][0]["headlines"][0]["title"] == "Capa"


def test_jev_themes_get_lists_catalog(client):
    r = client.get("/api/jev/themes")
    assert r.status_code == 200
    themes = r.get_json()["themes"]
    ids = [t["id"] for t in themes]
    assert "economia" in ids
    assert themes[0]["rank"] == 1


def test_jev_themes_put_requires_token(client):
    r = client.put("/api/jev/themes", json=[])
    assert r.status_code == 401


def test_jev_themes_put_rejects_empty_list(client):
    auth = {"Authorization": "Bearer test-token"}
    r = client.put("/api/jev/themes", json=[], headers=auth)
    assert r.status_code == 400


def test_jev_themes_put_reorder_persists(client):
    auth = {"Authorization": "Bearer test-token"}
    listed = client.get("/api/jev/themes").get_json()["themes"]
    by_id = {t["id"]: dict(t) for t in listed}
    by_id["economia"]["rank"] = 1
    by_id["política"]["rank"] = 2
    body = sorted(by_id.values(), key=lambda t: t["rank"])
    r = client.put("/api/jev/themes", json=body, headers=auth)
    assert r.status_code == 200
    saved = r.get_json()["themes"]
    assert saved[0]["id"] == "economia"
    assert saved[0]["rank"] == 1
    assert saved[1]["id"] == "política"
    assert saved[1]["rank"] == 2
    again = client.get("/api/jev/themes").get_json()["themes"]
    assert again[0]["id"] == "economia"


def test_jev_themes_put_rejects_bad_id(client):
    auth = {"Authorization": "Bearer test-token"}
    listed = client.get("/api/jev/themes").get_json()["themes"]
    listed[0]["id"] = "Not Valid!"
    r = client.put("/api/jev/themes", json=listed, headers=auth)
    assert r.status_code == 400


def test_jev_themes_put_replaces_list(client):
    auth = {"Authorization": "Bearer test-token"}
    body = [
        {
            "id": "economia",
            "label_en": "Economy",
            "label_pt": "economia",
            "rank": 1,
            "enabled": True,
        },
        {
            "id": "mundo",
            "label_en": "World",
            "label_pt": "mundo",
            "rank": 2,
            "enabled": True,
        },
    ]
    r = client.put("/api/jev/themes", json=body, headers=auth)
    assert r.status_code == 200
    saved = r.get_json()["themes"]
    assert len(saved) == 2
    assert {t["id"] for t in saved} == {"economia", "mundo"}
    assert [t["rank"] for t in saved] == [1, 2]


def test_put_settings_skips_blank_smtp_password(client):
    store.set_setting("smtp_password", "keep-me")
    r = client.put(
        "/api/settings",
        json={"smtp_password": ""},
        headers={"Authorization": "Bearer test-token"},
    )
    assert r.status_code == 200
    assert store.load_settings().smtp_password == "keep-me"


def test_digest_status_idle(client, monkeypatch):
    import digest_run

    runner = digest_run.DigestRunner()
    monkeypatch.setattr(dashboard, "runner", runner)
    r = client.get("/api/digest/run")
    assert r.status_code == 200
    body = r.get_json()
    assert body["status"] == "idle"
    assert [s["id"] for s in body["steps"]] == [
        "feeds",
        "fulltext",
        "score",
        "covers",
        "epub",
        "kindle",
        "books",
    ]


def test_digest_start_requires_token(client):
    r = client.post("/api/digest/run")
    assert r.status_code == 401


def test_digest_start_busy_returns_409(client, monkeypatch):
    import digest_run

    runner = digest_run.DigestRunner()
    monkeypatch.setattr(dashboard, "runner", runner)

    class SlowProc:
        def __init__(self):
            self.stdout = io.StringIO("✓  Fetched 1 raw articles\n")
            self.returncode = None

        def wait(self):
            time.sleep(0.4)
            self.returncode = 0
            return 0

    monkeypatch.setattr(digest_run.subprocess, "Popen", lambda *a, **k: SlowProc())
    auth = {"Authorization": "Bearer test-token"}
    first = client.post("/api/digest/run", headers=auth)
    assert first.status_code == 202
    second = client.post("/api/digest/run", headers=auth)
    assert second.status_code == 409

