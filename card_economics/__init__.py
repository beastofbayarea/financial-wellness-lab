"""Card economics comparison model for credit program launch strategies.

This package compares three operating models for launching a credit card program:
sponsor bank, program manager, and direct issuance. It evaluates each path against
pre-declared walk-away thresholds to determine viability and ranks viable options
by annual contribution.

Key design principles:
- **Thresholds declared first**: Walk-away criteria are set in `assumptions.yaml`
  before the comparison runs, preventing post-hoc rationalization.
- **Deterministic arithmetic**: All calculations are pure functions with no external
  dependencies or network calls.
- **Viability ≠ Decisiveness**: A path can be viable (clears all thresholds) without
  being decisive (leading by a sufficient margin).

Example:
    >>> from card_economics.model import compare, load
    >>> assumptions = load()
    >>> result = compare(assumptions)
    >>> print(f"Recommended: {result['recommended']}\")
    >>> print(f"Decisive: {result['decisive']}\")
    Recommended: Program manager
    Decisive: False
"""
