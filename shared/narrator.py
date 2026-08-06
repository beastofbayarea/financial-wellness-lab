"""Explanation layer.

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
import urllib.error
import urllib.request

API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-4-6"

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


def _call(system: str, user: str, max_tokens: int = 400) -> str | None:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None

    payload = json.dumps(
        {
            "model": MODEL,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
    ).encode()

    req = urllib.request.Request(
        API_URL,
        data=payload,
        headers={
            "content-type": "application/json",
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None

    parts = [b.get("text", "") for b in body.get("content", []) if b.get("type") == "text"]
    text = "".join(parts).strip()
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
    return _call(system, json.dumps(safe), max_tokens=200)


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


