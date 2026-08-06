# Eligibility Engine

**Question:** Can this user take an advance, and can we tell them *why* in a sentence they would accept?

## Design Architecture

This module implements a deterministic rule engine for Earned Wage Access (EWA) advance eligibility based on two strict constraints:

1. **Every rule carries an actionable remedy.** `Rule.__post_init__` enforces that no rule can be registered without a non-empty remedy. A denial without a remedy is a dead end for the applicant and a support burden for the business.
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

## Core Capabilities

### 1. Multi-Reason Diagnostic Evaluation
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

### 2. Dynamic Remedies & Categorization
Remedies are categorized into actionable types (`RemedyCategory`) and dynamic day/dollar metrics:
- **`WAIT_TENURE`**: Countdowns to eligibility (e.g. *"Keep your account connected for 29 more days"*).
- **`USER_ACTION`**: Direct borrower actions (e.g. *"Repay your current advance of $125.00"*).
- **`SUPPORT`**: Operational holds requiring assistance (e.g. *"Contact support to resolve hold"*).
- **`PERMANENT`**: Policy or regional limits (e.g. *"Product not offered in state"*).

### 3. Externalized Configuration
Thresholds live in [`rules_config.yaml`](./rules_config.yaml) and are loaded at startup:
- Minimum deposit tenure (`min_deposit_history_days: 60`)
- Minimum deposit frequency (`min_deposit_count: 2`)
- Restricted jurisdictions (`restricted_states: ["NY", "CT"]`)
- Advance limit tiers (`base_limit_cents`, `direct_deposit_limit_cents`)

### 4. Deterministic Narration Fallback
When `ANTHROPIC_API_KEY` is not present or API calls fail, narration degrades gracefully to `explain_decision_fallback()` without blocking or altering the decision.

---

## Running & Testing

Run the interactive demonstration suite:
```bash
python -m eligibility.demo
```

Run the unit tests:
```bash
pytest eligibility
```
