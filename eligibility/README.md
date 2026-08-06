# Eligibility Engine

**Question:** Can this user take an advance, and can we tell them *why* in a sentence they would accept?

## Design architecture

This module implements a deterministic rule engine for Earned Wage Access (EWA) advance eligibility based on two strict constraints:

1. **Every rule carries a remedy.** `Rule.__post_init__` enforces that no static rule can be registered without non-empty remedy text. Callable remedies are resolved when the rule fires. A remedy may be an action, a wait period, a support path, or an honest statement that the product is unavailable.
2. **Structural boundary between Decision and Narration.** Rules are pure, deterministic functions of an `Applicant`. The language model never sees raw user records—it receives scrubbed reason codes, remedies, and allowlisted facts, acting strictly as a translation layer to render decisions legible.

```
+------------------+     Deterministic     +------------------+
|    Applicant     | --------------------> | Decision Engine  |
| (user facts/PII) |                       |   (rules.py)     |
+------------------+                       +------------------+
                                                    |
                                            Scrubbed Facts & Reason Code
                                                    |
                                                    v
                                           +------------------+
                                           |  Narrator (LLM)  |
                                           |  (narrator.py)   |
                                           +------------------+
                                                    |
                                                    v
                                           Human Legible Sentence
```

---

## Core capabilities

### 1. Multi-reason diagnostic evaluation
By default, `evaluate(applicant)` stops at the first failing rule to return a primary decision. Callers can enable full diagnostic reporting with `collect_all=True` to retrieve every rule triggered:

```python
from eligibility.rules import Applicant, evaluate

applicant = Applicant(
    user_id="u123",
    state="CT",                  # Restricted state
    deposit_history_days=15,     # < 60 days
    recurring_deposit_count=0,
    has_direct_deposit=False,
    outstanding_advance_cents=5000, # Active balance
    prior_defaults=0,
)

# Diagnostic evaluation
decision = evaluate(applicant, collect_all=True)
print(f"Approved: {decision.approved}")
print(f"Total Rules Triggered: {len(decision.denials)}")

for denial in decision.denials:
    print(f"- [{denial.code}] ({denial.category.value}): {denial.remedy}")
```

### 2. Dynamic remedies and categorization

Remedies are categorized into actionable types (`RemedyCategory`) and dynamic day/dollar metrics:
- **`WAIT_TENURE`**: Countdowns to eligibility (e.g. *"Keep your account connected for 29 more days"*).
- **`USER_ACTION`**: Direct borrower actions (e.g. *"Repay your current advance of $125.00"*).
- **`SUPPORT`**: Operational holds requiring assistance (e.g. *"Contact support to resolve hold"*).
- **`PERMANENT`**: Policy or regional limits (e.g. *"Product not offered in state"*).

### 3. Externalized configuration

Thresholds live in [`rules_config.yaml`](./rules_config.yaml) and are loaded at module import:
- Minimum deposit tenure (`min_deposit_history_days: 60`)
- Minimum deposit frequency (`min_deposit_count: 2`)
- Restricted jurisdictions (`restricted_states: ["NY", "CT"]`)
- Advance limit tiers (`base_limit_cents`, `direct_deposit_limit_cents`)

### 4. Deterministic narration fallback

When Vertex AI configuration, Application Default Credentials, or the API call
is unavailable, narration degrades gracefully to
`explain_decision_fallback()` without blocking or altering the decision. The
dashboard calls Gemini only after the user presses its generation button.

---

## Decision contract

`evaluate(applicant)` returns an immutable `Decision`. An approval contains a
limit and no denials. A denial has a zero limit and one reason by default; with
`collect_all=True`, `denials` contains every triggered rule in declared order.
The first denial remains the primary reason.

The configured limits are $250 without direct deposit and $500 with direct
deposit. They are illustrative ceilings, not requested-amount calculations.

## Running and testing

Run the interactive demonstration suite:
```bash
python -m eligibility.demo
```

Run the unit tests:
```bash
python -m pytest eligibility
```
