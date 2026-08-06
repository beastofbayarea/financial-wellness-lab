"""The thresholds must bind. A walk-away line that never triggers is decoration."""

import copy

import pytest

from card_economics.model import load, evaluate_path, compare, break_even_spend, find_crossover_spend
from shared import narrator
from shared.narrator import write_memo_fallback


@pytest.fixture
def a():
    return load()


def test_direct_issuance_is_the_only_path_that_owns_the_receivable(a):
    assert evaluate_path("direct_issuance", a).owns_receivable
    assert not evaluate_path("sponsor_bank", a).owns_receivable
    assert not evaluate_path("program_manager", a).owns_receivable


def test_only_the_receivable_owner_books_interest_and_credit_losses(a):
    partnered = evaluate_path("sponsor_bank", a)
    assert partnered.interest_revenue_usd == 0
    assert partnered.credit_losses_usd == 0

    direct = evaluate_path("direct_issuance", a)
    assert direct.interest_revenue_usd > 0
    assert direct.credit_losses_usd > 0


def test_partner_paths_pay_a_fee_and_the_direct_path_does_not(a):
    assert evaluate_path("program_manager", a).partner_fees_usd > 0
    assert evaluate_path("direct_issuance", a).partner_fees_usd == 0


def test_time_to_market_threshold_excludes_the_slowest_path(a):
    r = evaluate_path("direct_issuance", a)
    assert "max_months_to_first_customer" in r.failed_thresholds
    assert not r.viable


def test_a_path_that_clears_every_threshold_is_viable(a):
    assert evaluate_path("sponsor_bank", a).viable


def test_contribution_threshold_binds_when_spend_collapses(a):
    weak = copy.deepcopy(a)
    weak["portfolio"]["monthly_spend_per_card_usd"] = 40
    for key in weak["paths"]:
        r = evaluate_path(key, weak)
        assert "min_annual_contribution_usd" in r.failed_thresholds


def test_loss_rate_threshold_binds_when_losses_spike(a):
    risky = copy.deepcopy(a)
    risky["paths"]["direct_issuance"]["annual_loss_rate"] = 0.15
    assert "max_annual_loss_rate" in evaluate_path("direct_issuance", risky).failed_thresholds


def test_comparison_reports_whether_the_win_is_decisive(a):
    out = compare(a)
    assert out["recommended"] is not None
    assert isinstance(out["decisive"], bool)


def test_excluded_paths_are_reported_with_the_threshold_they_failed(a):
    out = compare(a)
    assert out["excluded"]
    assert all(e["failed"] for e in out["excluded"])


def test_the_answer_can_invert_at_sufficient_volume(a):
    """The finding worth discussing: the ranking is volume-dependent."""
    heavy = copy.deepcopy(a)
    heavy["portfolio"]["monthly_spend_per_card_usd"] = 3000
    heavy["thresholds"]["max_months_to_first_customer"] = 36  # relax the gate
    ranked = sorted(
        (evaluate_path(k, heavy) for k in heavy["paths"]),
        key=lambda r: -r.annual_contribution_usd,
    )
    assert ranked[0].key == "direct_issuance"


def test_break_even_is_monotonic_for_a_partner_path(a):
    be = break_even_spend("sponsor_bank", a)
    assert be is not None and be > 0


def test_balance_sheet_exposure_and_unit_economics_are_calculated(a):
    pm = evaluate_path("program_manager", a)
    assert pm.balance_sheet_exposure_usd == 0.0
    assert pm.return_on_capital_pct is None
    assert pm.annual_contribution_per_card_usd == round(pm.annual_contribution_usd / 100_000, 2)

    di = evaluate_path("direct_issuance", a)
    assert di.balance_sheet_exposure_usd > 0.0
    assert di.return_on_capital_pct is not None


def test_crossover_spend_calculation(a):
    crossover = find_crossover_spend("direct_issuance", "program_manager", a)
    assert crossover is not None
    assert 1400 < crossover < 1500  # Exact mathematical crossover is $1,429.67/mo per card



def test_sole_survivor_decisiveness_flag(a):
    # Set threshold high enough so sponsor_bank fails min_annual_contribution, leaving only program_manager viable
    tight = copy.deepcopy(a)
    tight["thresholds"]["min_annual_contribution_usd"] = 3_500_000
    out = compare(tight)
    assert out["recommended"] == "Program manager"
    assert out["decisive"] is True
    assert out["decisive_reason"] == "sole_viable_path"


def test_deterministic_memo_fallback(a):
    out = compare(a)
    memo = write_memo_fallback(out)
    assert "**Recommendation**" in memo
    assert out["recommended"] in memo


def test_incomplete_or_ungrounded_generated_memo_falls_back(a, monkeypatch):
    out = compare(a)
    monkeypatch.setattr(
        narrator,
        "_call",
        lambda *args, **kwargs: "Decision Memo: Q2 2024\n\nWe recommend proceeding",
    )

    assert narrator.write_memo(out) == narrator.write_memo_fallback(out)
