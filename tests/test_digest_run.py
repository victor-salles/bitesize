import io
import threading
import time

import digest_run


def test_classify_line_maps_pipeline_messages():
    assert digest_run.classify_line("✓  Fetched 170 raw articles") == "feeds"
    assert digest_run.classify_line("Fetching Gmail…") == "feeds"
    assert (
        digest_run.classify_line("✓  Full content retrieved for 153 / 170 articles")
        == "fulltext"
    )
    assert digest_run.classify_line("🤖  Running AI processing…") == "score"
    assert digest_run.classify_line("  Jev triage (ads, relevance, temas)…") == "score"
    assert digest_run.classify_line("📰  Generating section covers…") == "covers"
    assert digest_run.classify_line("✅  Done!  168 articles saved.") == "epub"
    assert digest_run.classify_line("📬  Sending to Kindle…") == "kindle"
    assert digest_run.classify_line("📚  Copying to iCloud Books…") == "books"
    assert digest_run.classify_line("  Skipped Kindle delivery (disabled).") == "kindle"
    assert digest_run.classify_line("noise") is None


def test_apply_line_advances_steps_in_order():
    steps = digest_run.fresh_steps()
    digest_run.apply_line(steps, "✓  Fetched 2 raw articles")
    assert steps[0]["id"] == "feeds"
    assert steps[0]["state"] == "running"
    digest_run.apply_line(steps, "✓  Full content retrieved for 2 / 2 articles")
    assert steps[0]["state"] == "done"
    assert steps[1]["state"] == "running"
    digest_run.apply_line(steps, "✅  Done!  2 articles saved.")
    assert steps[1]["state"] == "done"
    assert next(s for s in steps if s["id"] == "epub")["state"] == "running"


class _FakeProc:
    def __init__(self, lines: list[str], code: int = 0):
        self.stdout = io.StringIO("\n".join(lines) + "\n")
        self.returncode = None
        self._code = code

    def wait(self):
        self.returncode = self._code
        return self._code


def test_runner_records_lines_and_finishes(monkeypatch):
    runner = digest_run.DigestRunner()

    def fake_popen(*args, **kwargs):
        return _FakeProc(
            [
                "✓  Fetched 2 raw articles",
                "✓  Full content retrieved for 2 / 2 articles",
                "🤖  Running AI processing…",
                "✅  Done!  2 articles saved.",
            ]
        )

    snap = runner.start(popen=fake_popen)
    assert snap["status"] == "running"
    deadline = time.time() + 2
    while runner.snapshot()["status"] == "running" and time.time() < deadline:
        time.sleep(0.02)
    done = runner.snapshot()
    assert done["status"] == "done"
    assert done["returncode"] == 0
    assert any("Fetched 2" in line for line in done["lines"])
    assert next(s for s in done["steps"] if s["id"] == "feeds")["state"] == "done"
    again = runner.start(popen=fake_popen)
    assert again["status"] == "running"


def test_runner_rejects_second_start_while_running():
    runner = digest_run.DigestRunner()
    gate = threading.Event()

    class SlowProc:
        def __init__(self):
            self.stdout = io.StringIO("✓  Fetched 1 raw articles\n")
            self.returncode = None

        def wait(self):
            gate.wait(timeout=2)
            self.returncode = 0
            return 0

    runner.start(popen=lambda *a, **k: SlowProc())
    try:
        runner.start(popen=lambda *a, **k: SlowProc())
        raise AssertionError("expected BusyError")
    except digest_run.BusyError:
        pass
    finally:
        gate.set()
        deadline = time.time() + 2
        while runner.snapshot()["status"] == "running" and time.time() < deadline:
            time.sleep(0.02)
