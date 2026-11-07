"""Run the digest from the dashboard and map console output to pipeline steps."""

from __future__ import annotations

import re
import subprocess
import sys
import threading
from typing import Any, Callable

from config import BASE_DIR

STEP_DEFS = (
    ("feeds", "Fetch stories"),
    ("fulltext", "Full text"),
    ("score", "Score and summarize"),
    ("covers", "Section covers"),
    ("epub", "Write EPUB"),
    ("kindle", "Send to Kindle"),
    ("books", "Copy to Books"),
)

_LINE_TO_STEP = (
    (re.compile(r"Fetched\s+\d+\s+raw articles", re.I), "feeds"),
    (re.compile(r"Fetching Gmail", re.I), "feeds"),
    (re.compile(r"Fetching Google Calendar", re.I), "feeds"),
    (re.compile(r"Full content retrieved", re.I), "fulltext"),
    (re.compile(r"Running AI processing", re.I), "score"),
    (re.compile(r"Jev triage", re.I), "score"),
    (re.compile(r"Generating section covers", re.I), "covers"),
    (re.compile(r"Done!", re.I), "epub"),
    (re.compile(r"Sending to Kindle", re.I), "kindle"),
    (re.compile(r"Skipped Kindle", re.I), "kindle"),
    (re.compile(r"Copying to iCloud Books", re.I), "books"),
    (re.compile(r"Skipped iCloud Books", re.I), "books"),
)

_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


class BusyError(RuntimeError):
    pass


def strip_ansi(text: str) -> str:
    return _ANSI.sub("", text)


def fresh_steps() -> list[dict[str, str]]:
    return [{"id": sid, "label": label, "state": "pending"} for sid, label in STEP_DEFS]


def classify_line(text: str) -> str | None:
    clean = strip_ansi(text)
    for pattern, step_id in _LINE_TO_STEP:
        if pattern.search(clean):
            return step_id
    return None


def apply_line(steps: list[dict[str, str]], text: str) -> str | None:
    step_id = classify_line(text)
    if not step_id:
        return None
    ids = [s["id"] for s in steps]
    target = ids.index(step_id)
    for i, step in enumerate(steps):
        if i < target and step["state"] != "skipped":
            step["state"] = "done"
        elif i == target:
            if re.search(r"Skipped\s", strip_ansi(text), re.I):
                step["state"] = "skipped"
            else:
                step["state"] = "running"
    return step_id


def _finish_steps(steps: list[dict[str, str]], ok: bool) -> None:
    for step in steps:
        if step["state"] == "running":
            step["state"] = "done" if ok else "error"
        elif step["state"] == "pending" and ok:
            if step["id"] in ("kindle", "books"):
                continue
            step["state"] = "done"


class DigestRunner:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._proc: subprocess.Popen[str] | None = None
        self._thread: threading.Thread | None = None
        self.status = "idle"
        self.steps = fresh_steps()
        self.lines: list[str] = []
        self.returncode: int | None = None
        self.error: str | None = None

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "status": self.status,
                "steps": [dict(s) for s in self.steps],
                "lines": list(self.lines[-200:]),
                "returncode": self.returncode,
                "error": self.error,
            }

    def start(
        self,
        popen: Callable[..., subprocess.Popen[str]] = subprocess.Popen,
    ) -> dict[str, Any]:
        with self._lock:
            if self.status == "running":
                raise BusyError("A digest is already running")
            self.status = "running"
            self.steps = fresh_steps()
            self.lines = []
            self.returncode = None
            self.error = None
            cmd = [sys.executable, "-u", str(BASE_DIR / "main.py"), "--all"]
            self._proc = popen(
                cmd,
                cwd=str(BASE_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            self._thread = threading.Thread(target=self._pump, daemon=True)
            self._thread.start()
        return self.snapshot()

    def _pump(self) -> None:
        proc = self._proc
        if proc is None or proc.stdout is None:
            with self._lock:
                self.status = "error"
                self.error = "Digest process did not start"
            return
        try:
            for raw in proc.stdout:
                line = strip_ansi(raw).rstrip("\n")
                if not line.strip():
                    continue
                with self._lock:
                    self.lines.append(line)
                    apply_line(self.steps, line)
            proc.wait()
            code = proc.returncode
            with self._lock:
                self.returncode = code
                ok = code == 0
                self.status = "done" if ok else "error"
                if not ok:
                    self.error = f"Digest exited {code}"
                _finish_steps(self.steps, ok)
        except Exception as exc:
            with self._lock:
                self.status = "error"
                self.error = str(exc)
                _finish_steps(self.steps, False)


runner = DigestRunner()
