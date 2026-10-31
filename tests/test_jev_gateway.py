from unittest.mock import MagicMock

from typesafe_sdk import Choice, Noul

import jev_triage
from jev_questions import news_questions


def test_evaluate_questions_maps_noul_to_boolean():
    payload = jev_triage.evaluate_questions(
        {
            "ad": Noul(instructions="Is this an ad?", criteria={"true": "yes", "false": "no"}),
            "tipo": Choice(
                instructions="Length",
                criteria={"resumo": "short", "artigo-completo": "long"},
            ),
        }
    )
    assert payload["ad"]["type"] == "boolean"
    assert payload["ad"]["instructions"] == "Is this an ad?"
    assert payload["ad"]["criteria"]["true"] == "yes"
    assert payload["tipo"]["type"] == "choice"
    assert payload["tipo"]["criteria"]["resumo"] == "short"


def test_response_from_evaluate_feeds_flatten_response(monkeypatch):
    monkeypatch.setattr(
        jev_triage,
        "tema_nouls",
        lambda: {"tema_economia": "economia"},
    )
    response = jev_triage.response_from_evaluate(
        {
            "model": "typesafe-ai/jev",
            "answers": {
                "ad": {"type": "boolean", "probability": 0.91},
                "clickbait": {"type": "boolean", "probability": 0.1},
                "press_release": {"type": "boolean", "probability": 0.05},
                "paywall_teaser": {"type": "boolean", "probability": 0.02},
                "tema_economia": {"type": "boolean", "probability": 0.8},
                "tipo": {
                    "type": "choice",
                    "choice": "resumo",
                    "probabilities": {"resumo": 0.9, "artigo-completo": 0.1},
                },
            },
            "usage": {"inputTokens": 10, "outputTokens": 3},
        }
    )
    answers = jev_triage.flatten_response(response)
    assert answers["ad"] == 0.91
    assert answers["tipo"] == "resumo"
    assert answers["temas"]["economia"] == 0.8
    assert answers["usage"]["input_tokens"] == 10
    assert answers["model"] == "typesafe-ai/jev"


def test_classify_article_posts_evaluate_on_gateway(monkeypatch):
    monkeypatch.setattr(
        jev_triage,
        "get_settings",
        lambda: MagicMock(jev_min_keep=0),
    )
    monkeypatch.setenv("TYPESAFE_API_KEY", "vck_test")
    monkeypatch.delenv("TYPESAFE_BASE_URL", raising=False)
    seen = {}

    def fake_post(url, *, json, headers):
        seen["url"] = url
        seen["model"] = json["model"]
        seen["auth"] = headers["Authorization"]
        return {
            "model": "typesafe-ai/jev",
            "answers": {
                "ad": {"type": "boolean", "probability": 0.01},
                "clickbait": {"type": "boolean", "probability": 0.01},
                "press_release": {"type": "boolean", "probability": 0.01},
                "paywall_teaser": {"type": "boolean", "probability": 0.01},
                **{
                    qid: {"type": "boolean", "probability": 0.2}
                    for qid in jev_triage.tema_nouls()
                },
                "tipo": {"type": "choice", "choice": "artigo-completo"},
            },
            "usage": {"inputTokens": 5, "outputTokens": 1},
        }

    monkeypatch.setattr(jev_triage, "gateway_post", fake_post)
    out = jev_triage.classify_article(
        {"title": "Rates", "content": "The bank held rates. " * 20, "source": "G1"}
    )
    assert "jev_error" not in out
    assert seen["url"] == "https://ai-gateway.vercel.sh/v1/evaluate"
    assert seen["model"] == "typesafe-ai/jev"
    assert seen["auth"] == "Bearer vck_test"
    assert out["skip"] is False


class FakeResponse:
    def __init__(self, status, body="", headers=None):
        self.status_code = status
        self.text = body
        self.headers = headers or {}

    def json(self):
        return {"ok": True}


def test_gateway_post_retries_rate_limits_then_succeeds(monkeypatch):
    replies = [FakeResponse(429, "busy"), FakeResponse(503, "down"), FakeResponse(200)]
    sleeps = []
    monkeypatch.setattr(jev_triage, "_http_post", lambda *a, **k: replies.pop(0))
    monkeypatch.setattr(jev_triage.time, "sleep", sleeps.append)
    assert jev_triage.gateway_post("u", json={}, headers={}) == {"ok": True}
    assert sleeps == [1.0, 2.0]


def test_gateway_post_honors_retry_after(monkeypatch):
    replies = [FakeResponse(429, "busy", {"retry-after": "7"}), FakeResponse(200)]
    sleeps = []
    monkeypatch.setattr(jev_triage, "_http_post", lambda *a, **k: replies.pop(0))
    monkeypatch.setattr(jev_triage.time, "sleep", sleeps.append)
    jev_triage.gateway_post("u", json={}, headers={})
    assert sleeps == [7.0]


def test_gateway_post_does_not_retry_access_errors(monkeypatch):
    calls = []

    def post(*a, **k):
        calls.append(1)
        return FakeResponse(403, '{"error":"Free tier users do not have access"}')

    monkeypatch.setattr(jev_triage, "_http_post", post)
    monkeypatch.setattr(jev_triage.time, "sleep", lambda s: None)
    try:
        jev_triage.gateway_post("u", json={}, headers={})
    except jev_triage.GatewayError as exc:
        assert exc.status == 403
        assert jev_triage.is_access_error(exc)
    else:
        raise AssertionError("expected GatewayError")
    assert len(calls) == 1


def test_gateway_post_gives_up_after_retries(monkeypatch):
    calls = []

    def post(*a, **k):
        calls.append(1)
        return FakeResponse(429, "busy")

    monkeypatch.setattr(jev_triage, "_http_post", post)
    monkeypatch.setattr(jev_triage.time, "sleep", lambda s: None)
    try:
        jev_triage.gateway_post("u", json={}, headers={})
    except jev_triage.GatewayError as exc:
        assert exc.status == 429
        assert not jev_triage.is_access_error(exc)
    assert len(calls) == jev_triage.GATEWAY_RETRIES + 1


def test_sdk_auth_errors_count_as_access_errors():
    from typesafe_sdk import TypeSafeAuthenticationError, TypeSafePermissionDeniedError

    for cls in (TypeSafeAuthenticationError, TypeSafePermissionDeniedError):
        exc = cls.__new__(cls)
        assert jev_triage.is_access_error(exc)
