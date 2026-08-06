"""Deterministic eligibility engine for earned-wage-access advances.

This package provides a rule-based decision engine that evaluates whether
a user qualifies for an advance based on configurable policy rules. Every
denial includes an actionable remedy explaining what the user can do to
change the outcome.

Key design principles:
- **Every rule carries a remedy**: A denial without a path forward is
  rejected at registration time.
- **Pure functions**: Rules are deterministic functions of an Applicant;
  no network calls or external state.
- **Structural boundary**: The LLM explanation layer receives only scrubbed
  reason codes and allowlisted facts, never raw user data.

Example:
    >>> from eligibility.rules import Applicant, evaluate
    >>> applicant = Applicant(
    ...     user_id="u123",
    ...     state="CA",
    ...     deposit_history_days=180,
    ...     recurring_deposit_count=5,
    ...     has_direct_deposit=True,
    ...     outstanding_advance_cents=0,
    ...     prior_defaults=0,
    ... )
    >>> decision = evaluate(applicant)
    >>> print(f"Approved: {decision.approved}, Limit: ${decision.limit_cents/100:.0f}")
    Approved: True, Limit: $500
"""
