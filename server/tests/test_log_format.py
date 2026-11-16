import json
import logging

from bitesize_server.log_format import JsonFormatter


def make_record(message="Edition %s failed", args=(7,), exc_info=None, **extra):
    record = logging.LogRecord("editions.services", logging.ERROR, __file__, 1, message, args, exc_info)
    record.created = 1763164800.25  # 2025-11-15T00:00:00.250Z
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_formats_a_record_as_one_json_line():
    line = JsonFormatter().format(make_record())

    assert json.loads(line) == {
        "time": "2025-11-15T00:00:00.250+00:00",
        "level": "ERROR",
        "logger": "editions.services",
        "message": "Edition 7 failed",
    }
    assert "\n" not in line


def test_includes_the_status_code_of_request_errors():
    entry = json.loads(JsonFormatter().format(make_record("Internal Server Error: /x", (), status_code=500)))

    assert entry["status_code"] == 500


def test_includes_the_traceback_on_one_line():
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = make_record(exc_info=sys.exc_info())

    line = JsonFormatter().format(record)
    entry = json.loads(line)

    assert "\n" not in line
    assert entry["exception"].startswith("Traceback (most recent call last):")
    assert entry["exception"].endswith("ValueError: boom")
