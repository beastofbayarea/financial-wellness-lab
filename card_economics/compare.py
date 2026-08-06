"""Run the comparison and, if narration is available, write the memo."""

from __future__ import annotations

from card_economics.model import compare, break_even_spend, find_crossover_spend, load
from shared.narrator import write_memo, write_memo_fallback


def usd(x: float) -> str:
    return f"${x/1e6:,.2f}M"


def main() -> None:
    a = load()
    out = compare(a)

    print("\nPATH COMPARISON (annual contribution & capital efficiency)\n" + "-" * 72)
    print(f"{'Path':<18} {'Contribution':>12} {'$/Card/Yr':>10} {'Cap Exposure':>14} {'TTM':>5}")
    print("-" * 72)
    for r in out["results"]:
        flag = "" if not r["failed_thresholds"] else " [EXCLUDED]"
        cap_str = usd(r['balance_sheet_exposure_usd']) if r['balance_sheet_exposure_usd'] > 0 else "$0"
        per_card = f"${r['annual_contribution_per_card_usd']:.2f}"
        print(f"{r['label']:<18} {usd(r['annual_contribution_usd']):>12}"
              f" {per_card:>10}"
              f" {cap_str:>14}"
              f" {r['months_to_first_customer']:>3}mo{flag}")

        if r["failed_thresholds"]:
            print(f"{'':<18} failed: {', '.join(r['failed_thresholds'])}")

    print("-" * 72)
    print(f"Recommended: {out['recommended']}")
    if out["margin_over_next_best_usd"] is not None:
        decisive_reason = f" ({out['decisive_reason']})" if out.get("decisive_reason") else ""
        print(f"Margin over next best: {usd(out['margin_over_next_best_usd'])}"
              f"  ({'decisive' if out['decisive'] else 'NOT decisive'}{decisive_reason})")
    elif out.get("decisive_reason") == "sole_viable_path":
        print(f"Decision Status: decisive (sole viable path; all competitors failed thresholds)")

    print("\nBreak-even monthly spend per card (to clear contribution floor):")
    for key in a["paths"]:
        be = break_even_spend(key, a)
        print(f"  {a['paths'][key]['label']:<20} "
              f"{'$' + format(be, ',.0f') if be else 'does not clear at any spend'}")

    crossover = find_crossover_spend("direct_issuance", "program_manager", a)
    if crossover:
        print(f"\nVolume Crossover Milestone:\n  Direct issuance overtakes Program manager at ${crossover:,.0f}/mo spend per card.")

    memo = write_memo(out)
    print("\nMEMO\n" + "-" * 72)
    if memo:
        print(memo)
    else:
        print(write_memo_fallback(out))


if __name__ == "__main__":
    main()
