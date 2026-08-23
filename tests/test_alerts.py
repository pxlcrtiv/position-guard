"""Alert writer: deterministic template backend (golden wording), LLM backend
graceful fallback, margin narration."""

from __future__ import annotations

from position_guard.alerts import AlertWriter
from position_guard.models import AssetPosition, Position
from position_guard.state import Level


def _demo_position() -> Position:
    return Position(
        "0x" + "d3" * 20,
        "aave-v3",
        [AssetPosition("ETH", 2.5, 8500.0, True, 0.825)],
        [AssetPosition("USDC", 6250.0, 6250.0, False)],
    )


def test_critical_template_matches_one_liner():
    writer = AlertWriter(backend="template")
    alert = writer.write(_demo_position(), 1.122, Level.CRITICAL)
    assert alert.backend == "template"
    # the project one-liner shape: "your ETH collateral is at 1.12 HF, ~$762 of margin left"
    assert "1.12 HF" in alert.message
    assert "$762" in alert.message
    assert alert.message.startswith(("CRITICAL — your ETH collateral", "Your ETH position"))


def test_template_is_deterministic():
    writer = AlertWriter(backend="template")
    a = writer.write(_demo_position(), 1.122, Level.CRITICAL)
    b = writer.write(_demo_position(), 1.122, Level.CRITICAL)
    assert a.message == b.message
    # a different address still yields one of the curated critical variants
    other = Position("0x" + "ab" * 20, "aave-v3", _demo_position().collateral, _demo_position().debt)
    c = writer.write(other, 1.122, Level.CRITICAL)
    assert c.message.startswith(("CRITICAL — your ETH collateral", "Your ETH position"))


def test_healthy_and_liquidation_wording():
    writer = AlertWriter(backend="template")
    healthy = writer.write(_demo_position(), 2.1, Level.HEALTHY)
    assert "2.10" in healthy.message
    liq = writer.write(_demo_position(), 0.94, Level.LIQUIDATION)
    assert "liquidat" in liq.message.lower()


def test_no_debt_renders_infinite_hf():
    writer = AlertWriter(backend="template")
    pos = Position("0x" + "d3" * 20, "aave-v3", [AssetPosition("ETH", 1, 3400, True, 0.825)], [])
    alert = writer.write(pos, None, Level.HEALTHY)
    assert "∞" in alert.message


def test_llm_backend_falls_back_to_template(monkeypatch):
    monkeypatch.setenv("POSITION_GUARD_ALERT_BACKEND", "llm")
    monkeypatch.setenv("POSITION_GUARD_LLM_API_KEY", "sk-fake")
    monkeypatch.setenv("POSITION_GUARD_LLM_BASE_URL", "http://127.0.0.1:1")  # connection refused
    writer = AlertWriter()
    alert = writer.write(_demo_position(), 1.122, Level.CRITICAL)
    assert alert.backend == "template"  # degraded, never dropped
    assert "1.12 HF" in alert.message


def test_llm_backend_skipped_without_key(monkeypatch):
    monkeypatch.delenv("POSITION_GUARD_LLM_API_KEY", raising=False)
    monkeypatch.setenv("POSITION_GUARD_ALERT_BACKEND", "llm")
    writer = AlertWriter()
    alert = writer.write(_demo_position(), 1.122, Level.CRITICAL)
    assert alert.backend == "template"


def test_llm_backend_parses_valid_response(monkeypatch):
    import json

    import httpx

    monkeypatch.setenv("POSITION_GUARD_ALERT_BACKEND", "llm")
    monkeypatch.setenv("POSITION_GUARD_LLM_API_KEY", "sk-fake")

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["model"] == "gpt-4o-mini"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Your ETH collateral is at 1.12 HF — top up!"}}]},
        )

    writer = AlertWriter(transport=httpx.MockTransport(handler))
    alert = writer.write(_demo_position(), 1.122, Level.CRITICAL)
    assert alert.backend == "llm"
    assert "1.12 HF" in alert.message