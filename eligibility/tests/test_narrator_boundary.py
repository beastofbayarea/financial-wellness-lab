"""The architectural claim of this repo, asserted as a test.

If the explanation layer can see the inputs, it can construct an outcome.
These tests fail if that boundary ever erodes.
"""

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
