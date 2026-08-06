"""The architectural claim and Vertex boundary of this repo, asserted as tests.

If the explanation layer can see the inputs, it can construct an outcome.
These tests fail if that boundary ever erodes.
"""

import json

from shared import narrator
from shared.narrator import ALLOWED_FIELDS, _scrub


def test_narrator_drops_identifying_and_decision_relevant_fields():
    leaky = {
        "reason_code": "DEPOSIT_HISTORY_TOO_SHORT",
        "days_observed": 31,
        "user_id": "u-12345",
        "state": "CA",
        "prior_defaults": 2,
        "has_direct_deposit": True,
        "email": "someone@example.com",
    }
    safe = _scrub(leaky)
    assert safe == {"reason_code": "DEPOSIT_HISTORY_TOO_SHORT", "days_observed": 31}
    for blocked in ("user_id", "state", "prior_defaults", "has_direct_deposit", "email"):
        assert blocked not in safe


def test_allowlist_contains_no_field_that_could_reconstruct_the_decision():
    forbidden = {"user_id", "state", "prior_defaults", "recurring_deposit_count",
                 "has_direct_deposit", "deposit_history_days", "account_frozen"}
    assert ALLOWED_FIELDS.isdisjoint(forbidden)


def test_vertex_call_uses_cent_compatible_configuration(monkeypatch):
    captured = {}

    class FakeModels:
        def generate_content(self, **kwargs):
            captured["request"] = kwargs
            return type("Response", (), {"text": "  Clear explanation.  "})()

    class FakeClient:
        def __init__(self, **kwargs):
            captured["client"] = kwargs
            self.models = FakeModels()

    monkeypatch.setenv("GCP_PROJECT_ID", "example-project")
    monkeypatch.setenv("GCP_REGION", "global")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-flash-latest")
    monkeypatch.setenv("GEMINI_MAX_TOKENS", "8192")
    monkeypatch.setattr(narrator.genai, "Client", FakeClient)
    monkeypatch.setattr(narrator, "_load_vertex_credentials", lambda: object())

    result = narrator.explain_decision(
        "DEPOSIT_HISTORY_TOO_SHORT",
        {"days_observed": 31, "state": "CA", "remedy": "Wait 29 days."},
    )

    assert result == "Clear explanation."
    assert captured["client"]["vertexai"] is True
    assert captured["client"]["project"] == "example-project"
    assert captured["client"]["location"] == "global"
    assert captured["client"]["credentials"] is not None
    assert captured["request"]["model"] == "gemini-flash-latest"
    assert captured["request"]["config"].max_output_tokens == 200
    sent = json.loads(captured["request"]["contents"])
    assert sent["days_observed"] == 31
    assert "state" not in sent


def test_vertex_call_falls_open_when_project_is_missing(monkeypatch):
    monkeypatch.delenv("GCP_PROJECT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)

    def unexpected_client(**kwargs):
        raise AssertionError("Client must not be created without a project")

    monkeypatch.setattr(narrator.genai, "Client", unexpected_client)
    assert narrator.explain_decision("APPROVED", {"limit_cents": 50_000}) is None


def test_stale_explicit_credential_path_falls_back_to_local_gcloud_adc(
    monkeypatch, tmp_path
):
    adc = tmp_path / "gcloud" / "application_default_credentials.json"
    adc.parent.mkdir()
    adc.write_text("{}", encoding="utf-8")
    sentinel = object()
    captured = {}

    def fake_load(path, scopes):
        captured["path"] = path
        return sentinel, "example-project"

    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv(
        "GOOGLE_APPLICATION_CREDENTIALS", "/missing/linux/service-account.json"
    )
    monkeypatch.setattr(
        narrator.google.auth, "load_credentials_from_file", fake_load
    )

    ready, source = narrator.llm_credential_status()
    credentials = narrator._load_vertex_credentials()

    assert ready is True
    assert "stale external credential path ignored" in source
    assert credentials is sentinel
    assert captured["path"] == str(adc)
