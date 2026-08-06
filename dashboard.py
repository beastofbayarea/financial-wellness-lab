"""Interactive dashboard for the two implemented financial-wellness MVPs."""

from __future__ import annotations

from copy import deepcopy

import streamlit as st

from card_economics.model import (
    break_even_spend,
    compare,
    find_crossover_spend,
    load,
)
from eligibility.rules import Applicant, evaluate
from shared.narrator import explain_decision_fallback, write_memo_fallback


STATES = (
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
)


def usd(value: float, decimals: int = 2) -> str:
    """Format a numeric value as US dollars."""
    return f"${value:,.{decimals}f}"


def build_card_assumptions(
    *,
    active_cards: int,
    monthly_spend: float,
    average_balance: float,
    revolve_rate_pct: float,
    interchange_rate_pct: float,
    contribution_floor: float,
    max_months: int,
    decisive_margin: float,
) -> dict:
    """Return an isolated assumptions dictionary populated from dashboard inputs."""
    assumptions = deepcopy(load())
    assumptions["portfolio"].update(
        {
            "active_cards": active_cards,
            "monthly_spend_per_card_usd": monthly_spend,
            "avg_revolving_balance_usd": average_balance,
            "revolve_rate": revolve_rate_pct / 100,
        }
    )
    assumptions["revenue"]["interchange_rate"] = interchange_rate_pct / 100
    assumptions["thresholds"].update(
        {
            "min_annual_contribution_usd": contribution_floor,
            "max_months_to_first_customer": max_months,
            "min_margin_advantage_over_next_best_usd": decisive_margin,
        }
    )
    return assumptions


def render_eligibility() -> None:
    """Render the deterministic eligibility scenario builder."""
    st.subheader("Advance eligibility")
    st.caption("Change the applicant facts, run the rules, and inspect every reason behind the result.")

    with st.form("eligibility_form"):
        left, right = st.columns(2)
        with left:
            state = st.selectbox("State", STATES, index=STATES.index("CA"))
            deposit_days = st.number_input(
                "Deposit history (days)", min_value=0, max_value=3650, value=180
            )
            deposit_count = st.number_input(
                "Recurring deposits", min_value=0, max_value=250, value=6
            )
            direct_deposit = st.checkbox("Has direct deposit", value=True)
        with right:
            outstanding_dollars = st.number_input(
                "Outstanding advance", min_value=0.0, max_value=100_000.0,
                value=0.0, step=25.0, format="%.2f",
            )
            prior_defaults = st.number_input(
                "Prior defaults", min_value=0, max_value=100, value=0
            )
            account_frozen = st.checkbox("Account frozen")
            collect_all = st.checkbox("Show every triggered rule", value=True)
        st.form_submit_button("Evaluate applicant", type="primary", width="stretch")

    applicant = Applicant(
        user_id="dashboard-scenario",
        state=state,
        deposit_history_days=int(deposit_days),
        recurring_deposit_count=int(deposit_count),
        has_direct_deposit=direct_deposit,
        outstanding_advance_cents=round(outstanding_dollars * 100),
        prior_defaults=int(prior_defaults),
        account_frozen=account_frozen,
    )
    decision = evaluate(applicant, collect_all=collect_all)

    if decision.approved:
        st.success(f"Approved up to {usd(decision.limit_cents / 100, 0)}")
        st.metric("Advance limit", usd(decision.limit_cents / 100, 0))
    else:
        st.error(f"Declined · {len(decision.denials)} rule(s) triggered")
        for denial in decision.denials:
            with st.container(border=True):
                st.markdown(f"**{denial.code.replace('_', ' ').title()}**")
                st.caption(denial.category.value.replace("_", " ").title())
                st.write(denial.remedy)
                if denial.estimated_days is not None:
                    st.metric("Estimated wait", f"{denial.estimated_days} days")

    explanation = explain_decision_fallback(
        decision.reason_code or "DENIED",
        {**decision.facts, "remedy": decision.remedy or ""},
    )
    st.info(f"Plain-language result: {explanation}")

    with st.expander("Structured decision output"):
        st.json(
            {
                "approved": decision.approved,
                "limit_cents": decision.limit_cents,
                "reason_code": decision.reason_code,
                "denials": [
                    {
                        "code": d.code,
                        "remedy": d.remedy,
                        "category": d.category.value,
                        "estimated_days": d.estimated_days,
                        "facts": d.facts,
                    }
                    for d in decision.denials
                ],
            }
        )


def render_card_economics() -> None:
    """Render the card-program assumption lab and computed results."""
    defaults = load()
    portfolio = defaults["portfolio"]
    thresholds = defaults["thresholds"]
    revenue = defaults["revenue"]

    st.subheader("Card economics")
    st.caption("Stress the portfolio assumptions and see which issuance paths clear the gates.")

    with st.form("economics_form"):
        volume, economics, gates = st.columns(3)
        with volume:
            st.markdown("**Portfolio**")
            active_cards = st.number_input(
                "Active cards", min_value=1, max_value=10_000_000,
                value=int(portfolio["active_cards"]), step=10_000,
            )
            monthly_spend = st.number_input(
                "Monthly spend per card", min_value=1.0, max_value=10_000.0,
                value=float(portfolio["monthly_spend_per_card_usd"]), step=25.0,
            )
        with economics:
            st.markdown("**Economics**")
            average_balance = st.number_input(
                "Average revolving balance", min_value=0.0, max_value=25_000.0,
                value=float(portfolio["avg_revolving_balance_usd"]), step=25.0,
            )
            revolve_rate_pct = st.slider(
                "Accounts revolving", min_value=0.0, max_value=100.0,
                value=float(portfolio["revolve_rate"] * 100), step=1.0,
                format="%.0f%%",
            )
            interchange_rate_pct = st.number_input(
                "Net interchange rate (%)", min_value=0.0, max_value=10.0,
                value=float(revenue["interchange_rate"] * 100), step=0.05,
            )
        with gates:
            st.markdown("**Walk-away gates**")
            contribution_floor = st.number_input(
                "Minimum annual contribution", min_value=-50_000_000.0,
                max_value=100_000_000.0,
                value=float(thresholds["min_annual_contribution_usd"]),
                step=250_000.0,
            )
            max_months = st.number_input(
                "Maximum months to launch", min_value=1, max_value=120,
                value=int(thresholds["max_months_to_first_customer"]),
            )
            decisive_margin = st.number_input(
                "Decisive margin", min_value=0.0, max_value=100_000_000.0,
                value=float(thresholds["min_margin_advantage_over_next_best_usd"]),
                step=250_000.0,
            )
        st.form_submit_button("Run comparison", type="primary", width="stretch")

    assumptions = build_card_assumptions(
        active_cards=int(active_cards),
        monthly_spend=float(monthly_spend),
        average_balance=float(average_balance),
        revolve_rate_pct=float(revolve_rate_pct),
        interchange_rate_pct=float(interchange_rate_pct),
        contribution_floor=float(contribution_floor),
        max_months=int(max_months),
        decisive_margin=float(decisive_margin),
    )
    output = compare(assumptions)

    winner, margin, confidence = st.columns(3)
    winner.metric("Highest-ranked viable path", output["recommended"] or "None")
    margin.metric(
        "Lead over runner-up",
        usd(output["margin_over_next_best_usd"], 0)
        if output["margin_over_next_best_usd"] is not None else "N/A",
    )
    confidence.metric("Decision status", "Decisive" if output["decisive"] else "Not decisive")

    if output["recommended"] is None:
        st.error("No path clears every configured walk-away gate.")
    elif output["decisive"]:
        st.success(f"{output['recommended']} ranks first and the result is decisive.")
    else:
        st.warning(
            f"{output['recommended']} ranks first, but its lead does not clear the decisive-margin gate."
        )

    rows = [
        {
            "Path": result["label"],
            "Annual contribution": result["annual_contribution_usd"],
            "Contribution / card": result["annual_contribution_per_card_usd"],
            "Receivable exposure": result["balance_sheet_exposure_usd"],
            "Launch (months)": result["months_to_first_customer"],
            "Status": "Viable" if not result["failed_thresholds"] else "Excluded",
            "Failed gates": ", ".join(result["failed_thresholds"]) or "—",
        }
        for result in output["results"]
    ]
    st.dataframe(
        rows,
        column_config={
            "Annual contribution": st.column_config.NumberColumn(format="dollar"),
            "Contribution / card": st.column_config.NumberColumn(format="dollar"),
            "Receivable exposure": st.column_config.NumberColumn(format="dollar"),
        },
        hide_index=True,
        width="stretch",
    )
    st.bar_chart(rows, x="Path", y="Annual contribution", color="Status")

    st.markdown("#### Sensitivity milestones")
    milestone_columns = st.columns(len(assumptions["paths"]))
    for column, key in zip(milestone_columns, assumptions["paths"]):
        point = break_even_spend(key, assumptions)
        column.metric(
            assumptions["paths"][key]["label"],
            usd(point, 0) + "/mo" if point is not None else "Not reached",
            help="Monthly spend per card needed to clear the contribution floor.",
        )
    crossover = find_crossover_spend("direct_issuance", "program_manager", assumptions)
    if crossover is not None:
        st.info(
            f"Direct issuance and Program manager have equal contribution at approximately "
            f"{usd(crossover, 0)} monthly spend per card."
        )

    with st.expander("Deterministic executive memo"):
        st.text(write_memo_fallback(output))
    with st.expander("Structured comparison output"):
        st.json(output)


def main() -> None:
    st.set_page_config(
        page_title="Financial Wellness Lab",
        page_icon="⚖️",
        layout="wide",
    )
    st.markdown(
        """
        <style>
        .stApp { background: linear-gradient(145deg, #f7f8f5 0%, #edf3ef 100%); }
        [data-testid="stMetric"] {
            background: rgba(255, 255, 255, 0.76);
            border: 1px solid #d7e2db;
            border-radius: 14px;
            padding: 1rem;
        }
        [data-testid="stForm"] {
            background: rgba(255, 255, 255, 0.62);
            border-color: #d7e2db;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.title("Financial Wellness Lab")
    st.markdown(
        "Test both shipped MVPs from one place. Decisions and calculations stay "
        "deterministic; the dashboard only collects scenarios and presents results."
    )
    eligibility_tab, economics_tab = st.tabs(["Eligibility", "Card economics"])
    with eligibility_tab:
        render_eligibility()
    with economics_tab:
        render_card_economics()
    st.divider()
    st.caption("Illustrative, synthetic scenarios only — not lending, legal, or investment advice.")


if __name__ == "__main__":
    main()
