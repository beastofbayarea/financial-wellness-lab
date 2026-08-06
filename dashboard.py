"""Interactive dashboard for the financial-wellness decision workflows."""

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
from shared.narrator import (
    explain_decision,
    explain_decision_fallback,
    write_memo,
    write_memo_fallback,
)


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
    """Render the deterministic eligibility review."""
    st.markdown("### Applicant profile")
    st.caption("Enter the account and deposit details used by the eligibility policy.")

    with st.form("eligibility_form"):
        left, right = st.columns(2)
        with left:
            state = st.selectbox(
                "State", STATES, index=STATES.index("CA"),
                help="NY and CT trigger STATE_NOT_SERVICED. Other listed states do not fail the jurisdiction rule.",
            )
            deposit_days = st.number_input(
                "Deposit history (days)", min_value=0, max_value=3650, value=180,
                help="Values below 60 trigger a denial and a countdown showing how many more connected days are required.",
            )
            deposit_count = st.number_input(
                "Recurring deposits", min_value=0, max_value=250, value=6,
                help="Fewer than 2 recurring deposits triggers TOO_FEW_DEPOSITS and reports how many more are needed.",
            )
            direct_deposit = st.checkbox(
                "Has direct deposit", value=True,
                help="Does not decide eligibility. It raises an approved limit from $250 to $500.",
            )
        with right:
            outstanding_dollars = st.number_input(
                "Outstanding advance", min_value=0.0, max_value=100_000.0,
                value=0.0, step=25.0, format="%.2f",
                help="Any amount above $0 triggers OUTSTANDING_ADVANCE. The remedy uses this amount as the balance to repay.",
            )
            prior_defaults = st.number_input(
                "Prior defaults", min_value=0, max_value=100, value=0,
                help="Two or more prior defaults triggers PRIOR_DEFAULTS and a 90-day reapplication remedy.",
            )
            account_frozen = st.checkbox(
                "Account frozen",
                help="Triggers ACCOUNT_FROZEN, the highest-priority denial, with a support-intervention remedy.",
            )
        st.form_submit_button("Review eligibility", type="primary", width="stretch")

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
    decision = evaluate(applicant, collect_all=True)

    st.markdown("### Eligibility decision")
    if decision.approved:
        status, limit, reasons = st.columns(3)
        status.metric("Status", "Eligible")
        limit.metric("Available advance", usd(decision.limit_cents / 100, 0))
        reasons.metric("Policy exceptions", "None")
    else:
        status, limit, reasons = st.columns(3)
        status.metric("Status", "Not eligible")
        limit.metric("Available advance", "$0")
        reasons.metric("Policy exceptions", len(decision.denials))
        st.markdown("#### What needs attention")
        for denial in decision.denials:
            with st.container(border=True):
                st.markdown(f"**{denial.code.replace('_', ' ').title()}**")
                st.write(denial.remedy)
                if denial.estimated_days is not None:
                    st.caption(f"Estimated wait: {denial.estimated_days} days")

    explanation = explain_decision_fallback(
        decision.reason_code or "DENIED",
        {**decision.facts, "remedy": decision.remedy or ""},
    )
    st.markdown("#### Customer-ready explanation")
    with st.container(border=True):
        st.write(explanation)
    if st.button("Refine explanation with AI", width="stretch"):
        with st.spinner("Preparing a grounded explanation…"):
            generated = explain_decision(
                decision.reason_code or "DENIED",
                {**decision.facts, "remedy": decision.remedy or ""},
            )
        if generated:
            with st.container(border=True):
                st.write(generated)
        else:
            st.warning(
                "AI-assisted wording is temporarily unavailable. The eligibility "
                "decision and explanation above are unchanged."
            )

    with st.expander("Decision audit details"):
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
    """Render the card-program strategy analysis."""
    defaults = load()
    portfolio = defaults["portfolio"]
    thresholds = defaults["thresholds"]
    revenue = defaults["revenue"]

    st.markdown("### Scenario assumptions")
    st.caption("Set the portfolio economics and investment criteria for this analysis.")

    with st.form("economics_form"):
        volume, economics, gates = st.columns(3)
        with volume:
            st.markdown("**Portfolio**")
            active_cards = st.number_input(
                "Active cards", min_value=1, max_value=10_000_000,
                value=int(portfolio["active_cards"]), step=10_000,
                help="Scales annual spend, interchange, revolving balances, contribution, and receivable exposure. Fixed costs do not scale with this input.",
            )
            monthly_spend = st.number_input(
                "Monthly spend per card", min_value=1.0, max_value=10_000.0,
                value=float(portfolio["monthly_spend_per_card_usd"]), step=25.0,
                help="Raises annual interchange for every path. Higher spend can move paths above the contribution floor and change their ranking.",
            )
        with economics:
            st.markdown("**Economics**")
            average_balance = st.number_input(
                "Average revolving balance", min_value=0.0, max_value=25_000.0,
                value=float(portfolio["avg_revolving_balance_usd"]), step=25.0,
                help="Changes interest revenue, credit losses, and receivable exposure for direct issuance. Partner paths do not own the receivable.",
            )
            revolve_rate_pct = st.slider(
                "Accounts revolving", min_value=0.0, max_value=100.0,
                value=float(portfolio["revolve_rate"] * 100), step=1.0,
                format="%.0f%%",
                help="Sets the share of accounts carrying balances. It affects direct-issuance interest, losses, exposure, and return on capital.",
            )
            interchange_rate_pct = st.number_input(
                "Net interchange rate (%)", min_value=0.0, max_value=10.0,
                value=float(revenue["interchange_rate"] * 100), step=0.05,
                help="Multiplies annual card spend into interchange revenue. Partner fees also rise because they are a share of interchange.",
            )
        with gates:
            st.markdown("**Investment criteria**")
            contribution_floor = st.number_input(
                "Minimum annual contribution", min_value=-50_000_000.0,
                max_value=100_000_000.0,
                value=float(thresholds["min_annual_contribution_usd"]),
                step=250_000.0,
                help="Excludes any path whose computed annual contribution falls below this pre-declared walk-away floor.",
            )
            max_months = st.number_input(
                "Maximum months to launch", min_value=1, max_value=120,
                value=int(thresholds["max_months_to_first_customer"]),
                help="Excludes paths that take longer to reach a first customer. Direct issuance defaults to 30 months.",
            )
            decisive_margin = st.number_input(
                "Decisive margin", min_value=0.0, max_value=100_000_000.0,
                value=float(thresholds["min_margin_advantage_over_next_best_usd"]),
                step=250_000.0,
                help="Controls confidence, not viability. The leading viable path is marked decisive only when its lead meets this amount.",
            )
        st.form_submit_button("Evaluate strategies", type="primary", width="stretch")

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

    st.markdown("### Recommendation")
    winner, margin, confidence = st.columns(3)
    winner.metric("Leading strategy", output["recommended"] or "No viable option")
    margin.metric(
        "Lead over runner-up",
        usd(output["margin_over_next_best_usd"], 0)
        if output["margin_over_next_best_usd"] is not None else "N/A",
    )
    confidence.metric("Confidence", "Decisive" if output["decisive"] else "Further review")

    if output["recommended"] is None:
        st.error("No strategy meets all investment criteria. Adjust the assumptions or review the excluded options.")
    elif output["decisive"]:
        st.success(f"{output['recommended']} leads the viable strategies by a decisive margin.")
    else:
        st.warning(
            f"{output['recommended']} leads, but the advantage is below the confidence threshold. Review strategic factors before committing."
        )

    st.markdown("#### Strategy comparison")

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

    st.markdown("#### Volume sensitivity")
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

    st.markdown("### Executive summary")
    with st.container(border=True):
        st.markdown(write_memo_fallback(output))
    if st.button("Refine executive summary with AI", width="stretch"):
        with st.spinner("Preparing a grounded executive summary…"):
            generated_memo = write_memo(output)
        if generated_memo:
            with st.container(border=True):
                st.write(generated_memo)
        else:
            st.warning(
                "AI-assisted wording is temporarily unavailable. The calculated "
                "recommendation and summary above are unchanged."
            )
    with st.expander("Model audit details"):
        st.json(output)


def apply_dashboard_styles() -> None:
    """Apply the shared high-contrast visual treatment to every dashboard page."""
    st.markdown(
        """
        <style>
        :root { color-scheme: light; }
        .stApp {
            background: #f5f7f5;
            color: #17211b;
        }
        .block-container { max-width: 1280px; padding-top: 2.5rem; padding-bottom: 3rem; }
        .stApp h1, .stApp h2, .stApp h3, .stApp h4,
        .stApp p, .stApp label, .stApp [data-testid="stCaptionContainer"] {
            color: #17211b;
        }
        [data-testid="stMetric"], .workflow-card {
            background: #ffffff;
            border: 1px solid #c8d5cc;
            border-radius: 14px;
            padding: 1rem;
        }
        .workflow-card {
            min-height: 185px;
            margin-bottom: 0.75rem;
        }
        .workflow-step {
            color: #8f2f29;
            font-size: 0.78rem;
            font-weight: 750;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }
        .hero-kicker {
            color: #8f2f29; font-size: 0.78rem; font-weight: 750;
            letter-spacing: 0.12em; text-transform: uppercase; margin-bottom: 0.6rem;
        }
        .hero-copy { color: #526158; font-size: 1.12rem; max-width: 720px; margin-bottom: 2rem; }
        .principle { padding: 0.6rem 0; }
        .principle strong { display: block; font-size: 0.96rem; margin-bottom: 0.2rem; }
        .principle span { color: #66756c; font-size: 0.88rem; }
        [data-testid="stForm"] {
            background: #ffffff;
            border-color: #c8d5cc;
        }
        [data-baseweb="input"] > div,
        [data-baseweb="select"] > div {
            background: #ffffff;
            color: #17211b;
        }
        [data-testid="stFormSubmitButton"] button {
            color: #ffffff;
            font-weight: 650;
        }
        [data-testid="stFormSubmitButton"] button p,
        button[kind="primary"] p {
            color: #ffffff !important;
        }
        [data-testid="stAlert"] p { color: inherit; }
        [data-testid="stSidebar"] { border-right: 1px solid #d7e0d9; }
        .product-name { font-size: 1.05rem; font-weight: 750; color: #17211b; }
        .product-kicker { color: #5e6f64; font-size: 0.82rem; margin-bottom: 1.25rem; }
        .nav-item {
            display: block; padding: 0.68rem 0.8rem; margin: 0.2rem 0;
            border-radius: 0.55rem; color: #34463a !important;
            text-decoration: none !important; font-weight: 550;
        }
        .nav-item:hover { background: #dfe9e2; }
        .nav-item.active { background: #cddfd2; color: #173b25 !important; font-weight: 700; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_navigation(active: str) -> None:
    """Render stable, product-style navigation independent of page discovery."""
    st.sidebar.markdown('<div class="product-name">Financial Wellness</div>', unsafe_allow_html=True)
    st.sidebar.markdown('<div class="product-kicker">Decision Studio</div>', unsafe_allow_html=True)
    links = (
        ("Overview", "/"),
        ("Advance eligibility", "/Eligibility"),
        ("Card strategy", "/Card_Economics"),
    )
    for label, href in links:
        selected = " active" if label == active else ""
        st.sidebar.markdown(
            f'<a class="nav-item{selected}" href="{href}" target="_self">{label}</a>',
            unsafe_allow_html=True,
        )
    st.sidebar.markdown("---")
    st.sidebar.caption("Deterministic decisions · AI-assisted explanations")


def render_home() -> None:
    """Render a minimal entry point for the two decision workflows."""
    render_navigation("Overview")
    st.markdown(
        '<div class="hero-kicker">Decision intelligence</div>',
        unsafe_allow_html=True,
    )
    st.title("Financial decisions, made transparent.")
    st.markdown(
        '<div class="hero-copy">Review advance eligibility and compare card-program '
        'strategies with deterministic models, complete evidence, and clear explanations.</div>',
        unsafe_allow_html=True,
    )

    eligibility, economics = st.columns(2)
    with eligibility:
        with st.container(border=True):
            st.markdown("#### Advance eligibility")
            st.write(
                "Review an applicant against policy rules and return every reason "
                "behind the decision."
            )
            st.link_button(
                "Review eligibility",
                "/Eligibility",
                icon=":material/fact_check:",
                width="stretch",
            )
    with economics:
        with st.container(border=True):
            st.markdown("#### Card program strategy")
            st.write(
                "Compare issuance strategies across contribution, speed, exposure, "
                "and investment criteria."
            )
            st.link_button(
                "Open strategy analysis",
                "/Card_Economics",
                icon=":material/finance_mode:",
                width="stretch",
            )

    st.markdown("---")
    principles = st.columns(3)
    principle_copy = (
        ("Deterministic", "Rules and formulas—not prompts—produce every decision."),
        ("Explainable", "Every outcome includes the evidence and next action."),
        ("Session-based", "Scenario inputs are evaluated without being persisted."),
    )
    for column, (title, body) in zip(principles, principle_copy):
        column.markdown(
            f'<div class="principle"><strong>{title}</strong><span>{body}</span></div>',
            unsafe_allow_html=True,
        )


def render_footer() -> None:
    st.divider()
    st.caption("Illustrative, synthetic scenarios only — not lending, legal, or investment advice.")


def main() -> None:
    st.set_page_config(
        page_title="Financial Wellness Lab",
        page_icon="⚖️",
        layout="wide",
    )
    apply_dashboard_styles()
    render_home()
    render_footer()


if __name__ == "__main__":
    main()
