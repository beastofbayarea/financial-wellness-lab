"""Optional Vertex AI explanation layer.

The single entry point for language-model calls in this repo.

Design constraint, enforced here rather than by convention: callers pass a
reason code and a small dict of pre-approved, non-identifying values. Raw user
records never reach this module. If the model is never given the inputs, it
cannot construct an outcome, and the worst failure mode is a badly worded
sentence rather than a wrong decision.

Falls open: if no API key is configured or the call fails, callers get None and
are expected to fall back to the structured output.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

import google.auth
from dotenv import load_dotenv
from google import genai
from google.genai import types


# This repository's ignored .env is its explicit local runtime contract. It must
# override unrelated variables inherited from another project's terminal.
load_dotenv(override=True)

DEFAULT_LOCATION = "global"
DEFAULT_MODEL = "gemini-flash-latest"
DEFAULT_MAX_TOKENS = 8192

# Values that may be interpolated into an explanation. Anything not on this
# list is dropped before the request is built.
ALLOWED_FIELDS = {
    "reason_code",
    "remedy",
    "remedy_category",
    "days_required",
    "days_observed",
    "limit_cents",
    "outstanding_cents",
}


@dataclass(frozen=True)
class LlmConfig:
    """Non-secret Vertex AI runtime configuration."""

    project: str | None
    location: str
    model: str
    max_tokens: int

    @property
    def configured(self) -> bool:
        return bool(self.project)


def llm_config() -> LlmConfig:
    """Read Cent-compatible Vertex settings from the process environment."""
    raw_max_tokens = os.environ.get("GEMINI_MAX_TOKENS", str(DEFAULT_MAX_TOKENS))
    try:
        max_tokens = max(1, int(raw_max_tokens))
    except ValueError:
        max_tokens = DEFAULT_MAX_TOKENS
    return LlmConfig(
        project=os.environ.get("GCP_PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT"),
        location=(
            os.environ.get("GCP_REGION")
            or os.environ.get("GOOGLE_CLOUD_LOCATION")
            or DEFAULT_LOCATION
        ),
        model=os.environ.get("GEMINI_MODEL", DEFAULT_MODEL),
        max_tokens=max_tokens,
    )


def _local_adc_path() -> Path | None:
    """Return the standard gcloud ADC file when it exists on this machine."""
    app_data = os.environ.get("APPDATA")
    if not app_data:
        return None
    candidate = Path(app_data) / "gcloud" / "application_default_credentials.json"
    return candidate if candidate.is_file() else None


def llm_credential_status() -> tuple[bool, str]:
    """Describe whether a usable local credential source can be resolved."""
    explicit = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if explicit and Path(explicit).is_file():
        return True, "Explicit service-account or ADC file"
    local_adc = _local_adc_path()
    if local_adc:
        if explicit:
            return True, "Local gcloud ADC (stale external credential path ignored)"
        return True, "Local gcloud Application Default Credentials"
    if explicit:
        return False, f"Credential file does not exist on this machine: {explicit}"
    return False, "No local Application Default Credentials found"


def _load_vertex_credentials():
    """Load credentials while recovering from a stale cross-platform file path."""
    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    explicit = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if explicit and Path(explicit).is_file():
        credentials, _ = google.auth.load_credentials_from_file(explicit, scopes=scopes)
        return credentials
    local_adc = _local_adc_path()
    if local_adc:
        credentials, _ = google.auth.load_credentials_from_file(
            str(local_adc), scopes=scopes
        )
        return credentials
    credentials, _ = google.auth.default(scopes=scopes)
    return credentials


def explain_decision_fallback(reason_code: str, facts: dict) -> str:
    """Generate a deterministic fallback explanation without calling an LLM."""
    if reason_code == "APPROVED":
        limit = facts.get("limit_cents", 0)
        return f"Your advance request of ${limit / 100:,.0f} has been approved."

    remedy = facts.get("remedy")
    if remedy:
        return f"Request declined ({reason_code}). Remedy: {remedy}"

    return f"Request declined ({reason_code})."



def _scrub(facts: dict) -> dict:
    return {k: v for k, v in facts.items() if k in ALLOWED_FIELDS}


def _grounded_explanation(text: str, facts: dict) -> str | None:
    """Reject unsupported numeric or time claims and normalize finance wording."""
    cleaned = text.replace(r"\$", "$").replace("credit limit", "advance limit")
    allowed_numbers: set[str] = set()
    for key, value in facts.items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            allowed_numbers.add(str(value))
            allowed_numbers.add(f"{value:g}" if isinstance(value, float) else str(value))
            if key.endswith("_cents"):
                dollars = value / 100
                allowed_numbers.add(f"{dollars:g}")
                allowed_numbers.add(f"{dollars:,.0f}")
                allowed_numbers.add(f"{dollars:,.2f}")
    observed_numbers = {
        token.replace(",", "")
        for token in re.findall(r"\d[\d,]*(?:\.\d+)?", cleaned)
    }
    normalized_allowed = {token.replace(",", "") for token in allowed_numbers}
    if not observed_numbers.issubset(normalized_allowed):
        return None
    has_duration_fact = any(key.startswith("days_") for key in facts)
    if not has_duration_fact and re.search(
        r"\b(?:day|days|week|weeks|month|months|year|years)\b", cleaned, re.I
    ):
        return None
    return cleaned.strip() or None


def _call(system: str, user: str, max_tokens: int = 400) -> str | None:
    """Call Gemini on Vertex AI, returning ``None`` on missing config or failure."""
    config = llm_config()
    if not config.configured:
        return None

    try:
        client = genai.Client(
            vertexai=True,
            project=config.project,
            location=config.location,
            credentials=_load_vertex_credentials(),
            http_options=types.HttpOptions(api_version="v1", timeout=30_000),
        )
        response = client.models.generate_content(
            model=config.model,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=min(max_tokens, config.max_tokens),
            ),
        )
    except Exception:
        return None

    text = (response.text or "").strip()
    return text or None


def explain_decision(reason_code: str, facts: dict) -> str | None:
    """Turn a machine reason code into a sentence a user would accept.

    Returns None when narration is unavailable. Callers must handle that.
    """
    safe = _scrub(dict(facts, reason_code=reason_code))
    system = (
        "You write one short explanation for a consumer finance app. "
        "You are given a decision that has ALREADY been made and may not "
        "question, soften, or reverse it. Two sentences maximum. "
        "State what happened, then what would change it. "
        "Plain language, no jargon, no apology, no emoji. "
        "Never invent a number that is not given to you."
    )
    generated = _call(system, json.dumps(safe), max_tokens=200)
    if not generated:
        return None
    return _grounded_explanation(generated, safe) or explain_decision_fallback(
        reason_code, safe
    )


def write_memo(results: dict) -> str | None:
    """Narrate a computed comparison. Receives figures only, never formulas."""
    system = (
        "You write a short decision memo for a product executive. "
        "You are given COMPUTED results and must not recalculate anything. "
        "Structure: recommendation, the reasoning in three bullets, then the "
        "single assumption that would most change the answer if wrong. "
        "Under 200 words. Every number you cite must appear in the input."
    )
    return _call(system, json.dumps(results), max_tokens=600)


def write_memo_fallback(results: dict) -> str:
    """Generate a structured executive decision memo deterministically without calling an LLM."""
    rec = results.get("recommended") or "None"
    margin = results.get("margin_over_next_best_usd")
    decisive = results.get("decisive", False)
    excluded = [e["label"] for e in results.get("excluded", [])]
    
    margin_str = f"${margin/1e6:,.2f}M" if margin is not None else "N/A"
    decisive_str = "decisive" if decisive else "NOT decisive"

    bullets = [
        f"Recommendation: Proceed with {rec}.",
        f"Economics: Margins yield {margin_str} advantage ({decisive_str}).",
        f"Exclusions: Excluded paths ({', '.join(excluded) if excluded else 'None'}) failed pre-declared thresholds.",
    ]
    
    key_assumption = (
        "Key Assumption Sensitivity: Monthly card spend per card. Direct issuance overtakes "
        "partner models at higher volume thresholds."
    )
    
    return "EXECUTIVE MEMO (Deterministic Fallback)\n" + "\n".join(f"- {b}" for b in bullets) + "\n\n" + key_assumption
