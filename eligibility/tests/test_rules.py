"""Tests name the behaviour, not the function. The suite is the demo."""

import pytest

from eligibility.rules import (
    Applicant, Rule, RemedyCategory, evaluate,
    BASE_LIMIT_CENTS, DIRECT_DEPOSIT_LIMIT_CENTS, RULES,
)
from shared.narrator import explain_decision_fallback


def applicant(**overrides) -> Applicant:
    base = dict(
        user_id="u", state="CA", deposit_history_days=180,
        recurring_deposit_count=5, has_direct_deposit=True,
        outstanding_advance_cents=0, prior_defaults=0, account_frozen=False,
    )
    base.update(overrides)
    return Applicant(**base)


def test_seasoned_user_with_direct_deposit_gets_the_higher_limit():
    d = evaluate(applicant())
    assert d.approved and d.limit_cents == DIRECT_DEPOSIT_LIMIT_CENTS


def test_seasoned_user_without_direct_deposit_gets_the_base_limit():
    d = evaluate(applicant(has_direct_deposit=False))
    assert d.approved and d.limit_cents == BASE_LIMIT_CENTS


def test_denies_advance_when_deposit_history_under_60_days_and_explains_why():
    d = evaluate(applicant(deposit_history_days=31))
    assert not d.approved
    assert d.reason_code == "DEPOSIT_HISTORY_TOO_SHORT"
    assert d.facts["days_required"] == 60
    assert d.facts["days_observed"] == 31
    assert d.remedy
    assert "29 more days" in d.remedy


def test_denies_second_advance_while_one_is_outstanding():
    d = evaluate(applicant(outstanding_advance_cents=12_500))
    assert not d.approved and d.reason_code == "OUTSTANDING_ADVANCE"
    assert "$125.00" in d.remedy


def test_denies_in_restricted_state_regardless_of_perfect_history():
    d = evaluate(applicant(state="NY", deposit_history_days=999,
                           recurring_deposit_count=99))
    assert not d.approved and d.reason_code == "STATE_NOT_SERVICED"


def test_frozen_account_is_checked_before_anything_else():
    d = evaluate(applicant(account_frozen=True, state="NY",
                           outstanding_advance_cents=999))
    assert d.reason_code == "ACCOUNT_FROZEN"


def test_decision_is_deterministic_across_repeated_calls():
    a = applicant(deposit_history_days=45)
    assert {evaluate(a).reason_code for _ in range(50)} == {"DEPOSIT_HISTORY_TOO_SHORT"}


def test_multi_reason_evaluation_collects_all_failing_rules():
    a = applicant(
        state="CT",
        outstanding_advance_cents=5_000,
        deposit_history_days=10,
    )
    d = evaluate(a, collect_all=True)
    assert not d.approved
    codes = [denial.code for denial in d.denials]
    assert "STATE_NOT_SERVICED" in codes
    assert "OUTSTANDING_ADVANCE" in codes
    assert "DEPOSIT_HISTORY_TOO_SHORT" in codes


def test_structured_remedy_categories_are_assigned_correctly():
    d_frozen = evaluate(applicant(account_frozen=True))
    assert d_frozen.primary_denial.category == RemedyCategory.SUPPORT

    d_state = evaluate(applicant(state="NY"))
    assert d_state.primary_denial.category == RemedyCategory.PERMANENT

    d_history = evaluate(applicant(deposit_history_days=10))
    assert d_history.primary_denial.category == RemedyCategory.WAIT_TENURE
    assert d_history.primary_denial.estimated_days == 50


def test_deterministic_narrator_fallback_generates_explanation():
    a = applicant(deposit_history_days=31)
    d = evaluate(a)
    fallback = explain_decision_fallback(d.reason_code, {**d.facts, "remedy": d.remedy})
    assert "DEPOSIT_HISTORY_TOO_SHORT" in fallback
    assert "29 more days" in fallback


# --- The constraint that matters most --------------------------------------

def test_every_rule_carries_a_remedy():
    sample_applicant = applicant()
    for rule in RULES:
        remedy_obj = rule.resolve_remedy(sample_applicant)
        assert remedy_obj.text.strip(), f"{rule.code} has no remedy"


def test_a_rule_without_a_remedy_cannot_be_constructed():
    with pytest.raises(ValueError, match="no remedy"):
        Rule(code="NO_REMEDY", remedy="", predicate=lambda a: True)


def test_denial_always_returns_a_reason_and_a_remedy_together():
    denials = [
        applicant(account_frozen=True),
        applicant(state="CT"),
        applicant(outstanding_advance_cents=1),
        applicant(deposit_history_days=1),
        applicant(recurring_deposit_count=0),
        applicant(prior_defaults=3),
    ]
    for a in denials:
        d = evaluate(a)
        assert not d.approved
        assert d.reason_code and d.remedy
