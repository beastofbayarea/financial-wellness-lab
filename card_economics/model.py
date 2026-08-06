"""Compare financial and operational paths to launching a credit card programme.

The contribution of this module is not the recommendation. It is that the
walk-away thresholds are declared in `assumptions.yaml` before the comparison
runs, and that tests assert they actually bind. Setting the line after seeing
the numbers is how a diligence process talks itself into a deal.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass, asdict

import yaml

HERE = pathlib.Path(__file__).parent
DEFAULT_ASSUMPTIONS = HERE / "assumptions.yaml"


@dataclass(frozen=True)
class PathResult:
    """Financial, operational, and compliance evaluation result for a single card issuance path.
    
    Attributes:
        key: Short identifier for the path (e.g. 'program_manager').
        label: Human-readable label (e.g. 'Program manager').
        interchange_revenue_usd: Annual net interchange revenue earned ($).
        interest_revenue_usd: Annual interest revenue earned ($). Zero if not receivable owner.
        partner_fees_usd: Annual revenue share paid to bank/partner ($). Zero if direct issuer.
        credit_losses_usd: Annual credit charge-offs ($). Zero if not receivable owner.
        fixed_costs_usd: Annual fixed operational overhead ($).
        compliance_costs_usd: Annual fully loaded compliance staffing cost ($).
        annual_contribution_usd: Net annual contribution ($) (Revenues - Costs).
        annual_contribution_per_card_usd: Net contribution divided by active card count ($/card/yr).
        balance_sheet_exposure_usd: Total revolving loan balance held on balance sheet ($).
        return_on_capital_pct: Annual contribution as a percentage of balance sheet exposure (%).
        months_to_first_customer: Time-to-market in months.
        owns_receivable: Whether the program holds credit receivables on its balance sheet.
        failed_thresholds: List of pre-declared walk-away thresholds violated by this path.
    """

    key: str
    label: str
    interchange_revenue_usd: float
    interest_revenue_usd: float
    partner_fees_usd: float
    credit_losses_usd: float
    fixed_costs_usd: float
    compliance_costs_usd: float
    annual_contribution_usd: float
    annual_contribution_per_card_usd: float
    balance_sheet_exposure_usd: float
    return_on_capital_pct: float | None
    months_to_first_customer: int
    owns_receivable: bool
    failed_thresholds: tuple[str, ...]

    @property
    def viable(self) -> bool:
        """True if the path clears all pre-declared walk-away thresholds."""
        return not self.failed_thresholds


def load(path: pathlib.Path | str = DEFAULT_ASSUMPTIONS) -> dict:
    """Load model parameters and walk-away thresholds from a YAML assumptions file.
    
    Args:
        path: Absolute or relative file path to the assumptions YAML file.
        
    Returns:
        Dictionary containing portfolio, revenue, threshold, and path parameters.
    """
    return yaml.safe_load(pathlib.Path(path).read_text())


def evaluate_path(key: str, a: dict) -> PathResult:
    """Evaluate a single card issuance path against portfolio rules and walk-away gates.
    
    Args:
        key: The key of the path to evaluate ('sponsor_bank', 'program_manager', 'direct_issuance').
        a: Dictionary of model assumptions (loaded via load()).
        
    Returns:
        A PathResult dataclass populated with computed financial metrics and threshold checks.
    """
    p = a["paths"][key]
    pf, rev, th = a["portfolio"], a["revenue"], a["thresholds"]

    annual_spend = pf["active_cards"] * pf["monthly_spend_per_card_usd"] * 12
    interchange = annual_spend * rev["interchange_rate"]
    partner_fees = interchange * p["partner_fee_share_of_interchange"]

    revolving = (
        pf["active_cards"] * pf["revolve_rate"] * pf["avg_revolving_balance_usd"]
    )
    # Interest accrues and credit losses land ONLY where the receivable is held.
    interest = revolving * rev["apr"] if p["owns_receivable"] else 0.0
    losses = revolving * p["annual_loss_rate"] if p["owns_receivable"] else 0.0

    compliance = p["compliance_headcount"] * a["fully_loaded_compliance_cost_per_head_usd"]
    fixed = p["fixed_annual_cost_usd"]

    contribution = interchange + interest - partner_fees - losses - fixed - compliance
    contribution_per_card = contribution / pf["active_cards"] if pf["active_cards"] > 0 else 0.0

    balance_sheet_exposure = revolving if p["owns_receivable"] else 0.0
    return_on_capital = (
        (contribution / balance_sheet_exposure) * 100.0
        if balance_sheet_exposure > 0
        else None
    )

    failed = []
    if contribution < th["min_annual_contribution_usd"]:
        failed.append("min_annual_contribution_usd")
    if p["months_to_first_customer"] > th["max_months_to_first_customer"]:
        failed.append("max_months_to_first_customer")
    if p["annual_loss_rate"] > th["max_annual_loss_rate"]:
        failed.append("max_annual_loss_rate")

    return PathResult(
        key=key,
        label=p["label"],
        interchange_revenue_usd=round(interchange, 2),
        interest_revenue_usd=round(interest, 2),
        partner_fees_usd=round(partner_fees, 2),
        credit_losses_usd=round(losses, 2),
        fixed_costs_usd=round(float(fixed), 2),
        compliance_costs_usd=round(float(compliance), 2),
        annual_contribution_usd=round(contribution, 2),
        annual_contribution_per_card_usd=round(contribution_per_card, 2),
        balance_sheet_exposure_usd=round(balance_sheet_exposure, 2),
        return_on_capital_pct=round(return_on_capital, 2) if return_on_capital is not None else None,
        months_to_first_customer=p["months_to_first_customer"],
        owns_receivable=p["owns_receivable"],
        failed_thresholds=tuple(failed),
    )


def compare(a: dict | None = None) -> dict:
    """Compare all available issuance paths, filter by walk-away gates, and rank viable options.
    
    Args:
        a: Optional model assumptions dict. Defaults to loading DEFAULT_ASSUMPTIONS.
        
    Returns:
        Dict containing all path results, recommendation label, margin over runner-up,
        decisiveness status, and excluded path details.
    """
    a = a or load()
    results = [evaluate_path(k, a) for k in a["paths"]]
    viable = [r for r in results if r.viable]
    ranked = sorted(viable, key=lambda r: -r.annual_contribution_usd)

    winner = ranked[0] if ranked else None
    runner_up = ranked[1] if len(ranked) > 1 else None
    margin = (
        winner.annual_contribution_usd - runner_up.annual_contribution_usd
        if winner and runner_up else None
    )

    if winner:
        if runner_up:
            decisive = margin >= a["thresholds"]["min_margin_advantage_over_next_best_usd"]
            decisive_reason = "margin_clears_threshold" if decisive else "margin_below_threshold"
        else:
            decisive = True
            decisive_reason = "sole_viable_path"
    else:
        decisive = False
        decisive_reason = "no_viable_paths"

    return {
        "results": [asdict(r) for r in results],
        "recommended": winner.label if winner else None,
        "margin_over_next_best_usd": round(margin, 2) if margin is not None else None,
        "decisive": decisive,
        "decisive_reason": decisive_reason,
        "excluded": [
            {"label": r.label, "failed": list(r.failed_thresholds)}
            for r in results if not r.viable
        ],
    }


def break_even_spend(key: str, a: dict | None = None) -> float | None:
    """Find the monthly spend per card at which the specified path clears the contribution floor.
    
    Args:
        key: Issuance path key ('sponsor_bank', 'program_manager', 'direct_issuance').
        a: Optional model assumptions dict.
        
    Returns:
        Monthly spend per card ($) required to clear min_annual_contribution_usd, or None if unreachable.
    """
    a = a or load()
    lo, hi = 1.0, 5000.0
    target = a["thresholds"]["min_annual_contribution_usd"]
    for _ in range(50):
        mid = (lo + hi) / 2
        trial = {**a, "portfolio": {**a["portfolio"], "monthly_spend_per_card_usd": mid}}
        if evaluate_path(key, trial).annual_contribution_usd < target:
            lo = mid
        else:
            hi = mid
    return round(hi, 2) if hi < 4999 else None


def find_crossover_spend(key1: str, key2: str, a: dict | None = None) -> float | None:
    """Calculate the monthly spend per card at which key1 contribution equals key2 contribution.
    
    Args:
        key1: First issuance path key (e.g. 'direct_issuance').
        key2: Second issuance path key (e.g. 'program_manager').
        a: Optional model assumptions dict.
        
    Returns:
        Monthly spend per card ($) at the crossover inflection point, or None if no crossover occurs.
    """
    a = a or load()
    lo, hi = 1.0, 10000.0
    
    # Evaluate at bounds to verify crossover exists
    res1_lo = evaluate_path(key1, {**a, "portfolio": {**a["portfolio"], "monthly_spend_per_card_usd": lo}})
    res2_lo = evaluate_path(key2, {**a, "portfolio": {**a["portfolio"], "monthly_spend_per_card_usd": lo}})
    diff_lo = res1_lo.annual_contribution_usd - res2_lo.annual_contribution_usd

    res1_hi = evaluate_path(key1, {**a, "portfolio": {**a["portfolio"], "monthly_spend_per_card_usd": hi}})
    res2_hi = evaluate_path(key2, {**a, "portfolio": {**a["portfolio"], "monthly_spend_per_card_usd": hi}})
    diff_hi = res1_hi.annual_contribution_usd - res2_hi.annual_contribution_usd

    if (diff_lo * diff_hi) > 0:
        return None  # No crossover in the range

    for _ in range(50):
        mid = (lo + hi) / 2
        trial = {**a, "portfolio": {**a["portfolio"], "monthly_spend_per_card_usd": mid}}
        c1 = evaluate_path(key1, trial).annual_contribution_usd
        c2 = evaluate_path(key2, trial).annual_contribution_usd
        diff_mid = c1 - c2
        if (diff_lo * diff_mid) <= 0:
            hi = mid
        else:
            lo = mid

    return round(hi, 2)
