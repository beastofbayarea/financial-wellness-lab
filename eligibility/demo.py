"""Run a handful of applicants through the engine and narrate each result.

Works without an API key: narration falls back gracefully to a deterministic,
structured explanation. That fallback is the point, not a convenience — the decision
must never depend on a network call.
"""

from __future__ import annotations

from eligibility.rules import Applicant, evaluate
from shared.narrator import explain_decision, explain_decision_fallback

FIXTURES = [
    ("approved, direct deposit", Applicant(
        user_id="u1", state="CA", deposit_history_days=180,
        recurring_deposit_count=6, has_direct_deposit=True,
        outstanding_advance_cents=0, prior_defaults=0)),
    ("approved, no direct deposit", Applicant(
        user_id="u2", state="TX", deposit_history_days=95,
        recurring_deposit_count=3, has_direct_deposit=False,
        outstanding_advance_cents=0, prior_defaults=0)),
    ("too new", Applicant(
        user_id="u3", state="CA", deposit_history_days=31,
        recurring_deposit_count=1, has_direct_deposit=True,
        outstanding_advance_cents=0, prior_defaults=0)),
    ("already borrowed", Applicant(
        user_id="u4", state="FL", deposit_history_days=200,
        recurring_deposit_count=8, has_direct_deposit=True,
        outstanding_advance_cents=12_500, prior_defaults=0)),
    ("restricted state", Applicant(
        user_id="u5", state="NY", deposit_history_days=400,
        recurring_deposit_count=20, has_direct_deposit=True,
        outstanding_advance_cents=0, prior_defaults=0)),
    ("multiple issues (full diagnostic)", Applicant(
        user_id="u6", state="CT", deposit_history_days=15,
        recurring_deposit_count=0, has_direct_deposit=False,
        outstanding_advance_cents=5_000, prior_defaults=2)),
]


def main() -> None:
    print("=== SINGLE REASON EVALUATION (DEFAULT) ===")
    for label, applicant in FIXTURES[:5]:
        d = evaluate(applicant)
        verdict = f"${d.limit_cents / 100:,.0f}" if d.approved else "denied"
        print(f"\n--- {label}: {verdict} [{d.reason_code}]")
        if not d.approved and d.primary_denial:
            print(f"    category: {d.primary_denial.category.value}")
            print(f"    remedy: {d.remedy}")
        sentence = explain_decision(d.reason_code or "DENIED", {**d.facts, "remedy": d.remedy or ""})
        if sentence:
            print(f"    narration: {sentence}")
        else:
            fallback = explain_decision_fallback(d.reason_code or "DENIED", {**d.facts, "remedy": d.remedy or ""})
            print(f"    narration (fallback): {fallback}")

    print("\n=== MULTI-REASON DIAGNOSTIC EVALUATION (COLLECT ALL) ===")
    label, multi_applicant = FIXTURES[-1]
    d_multi = evaluate(multi_applicant, collect_all=True)
    print(f"\n--- {label}: denied [{len(d_multi.denials)} rules triggered]")
    for i, denial in enumerate(d_multi.denials, 1):
        print(f"    Rule #{i}: [{denial.code}] ({denial.category.value})")
        print(f"            Remedy: {denial.remedy}")


if __name__ == "__main__":
    main()
