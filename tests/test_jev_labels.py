from pathlib import Path

import pytest

import jev_labels
import jev_log


@pytest.fixture(autouse=True)
def label_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(jev_labels, "LABELS_PATH", tmp_path / "jev_labels.json")
    monkeypatch.setattr(jev_log, "JEV_DIR", tmp_path / "jev")


def test_save_label_round_trip_per_score():
    jev_labels.save_label(
        "run1",
        {"url": "https://ex.com/a", "title": "A", "source": "G1"},
        {"ad": 0.9, "clickbait": 0.2, "relevance": 10, "tipo": "resumo", "temas": ["economia"]},
    )
    got = jev_labels.label_for(
        "run1",
        {"url": "https://ex.com/a", "title": "A", "source": "G1"},
    )
    assert got["ad"] == 0.9
    assert got["clickbait"] == 0.2
    assert got["relevance"] == 10
    assert got["tipo"] == "resumo"
    assert got["temas"] == ["economia"]


def test_attach_labels_to_run():
    payload = jev_log.write_run(
        [
            {
                "title": "Story",
                "source": "G1",
                "link": "https://ex.com/s",
                "skip": False,
                "relevance": 70,
                "tipo": "resumo",
                "temas": ["mundo"],
                "jev": {"answers": {"ad": 0.01, "clickbait": 0.1}},
            }
        ]
    )
    jev_labels.save_label(
        payload["id"],
        payload["items"][0],
        {"ad": 0.5, "relevance": 40},
    )
    merged = jev_labels.attach_labels(jev_log.load_run(payload["id"]))
    human = merged["items"][0]["human"]
    assert human["ad"] == 0.5
    assert human["relevance"] == 40
    assert "keep" not in human


def test_export_jsonl_pairs_prediction_and_label():
    payload = jev_log.write_run(
        [
            {
                "title": "Story",
                "source": "G1",
                "link": "https://ex.com/s",
                "skip": False,
                "relevance": 70,
                "tipo": "artigo-completo",
                "temas": ["tecnologia"],
                "jev": {"answers": {"ad": 0.01, "clickbait": 0.1}},
            }
        ]
    )
    jev_labels.save_label(
        payload["id"],
        payload["items"][0],
        {"ad": 0.4},
    )
    rows = jev_labels.export_rows()
    assert len(rows) == 1
    assert rows[0]["run_id"] == payload["id"]
    assert rows[0]["predicted"]["ad"] == 0.01
    assert "keep" not in rows[0]["predicted"]
    assert rows[0]["label"]["ad"] == 0.4
    assert rows[0]["url"] == "https://ex.com/s"
