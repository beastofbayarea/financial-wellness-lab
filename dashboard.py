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
from shared.narrator import (
    explain_decision,
    explain_decision_fallback,
    llm_config,
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
    if st.button("Generate explanation with Gemini", width="stretch"):
        with st.spinner("Generating from the already-computed decision…"):
            generated = explain_decision(
                decision.reason_code or "DENIED",
                {**decision.facts, "remedy": decision.remedy or ""},
            )
        if generated:
            st.success(generated)
        else:
            st.warning(
                "Gemini narration is unavailable. The deterministic decision and "
                "fallback above remain valid; check Vertex AI credentials and access."
            )

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
    if st.button("Generate executive memo with Gemini", width="stretch"):
        with st.spinner("Narrating the already-computed comparison…"):
            generated_memo = write_memo(output)
        if generated_memo:
            st.success(generated_memo)
        else:
            st.warning(
                "Gemini narration is unavailable. The deterministic results and memo "
                "remain valid; check Vertex AI credentials and access."
            )
    with st.expander("Structured comparison output"):
        st.json(output)


def apply_dashboard_styles() -> None:
    """Apply the shared high-contrast visual treatment to every dashboard page."""
    st.markdown(
        """
        <style>
        :root { color-scheme: light; }
        .stApp {
            background: linear-gradient(145deg, #f7f8f5 0%, #e9f1eb 100%);
            color: #17211b;
        }
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
        [data-testid="stAlert"] p { color: inherit; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_home() -> None:
    """Explain the application workflow and link to each independent MVP page."""
    st.title("Financial Wellness Lab")
    st.markdown(
        "Two deterministic product experiments with one shared principle: "
        "**software makes the decision; language only explains the result.**"
    )

    config = llm_config()
    with st.container(border=True):
        status, provider, model = st.columns(3)
        status.metric("LLM configuration", "Configured" if config.configured else "Fallback only")
        provider.metric("Optional provider", "Vertex AI")
        model.metric("Narration model", config.model)
        st.caption(
            f"Project: {config.project or 'not set'} · Location: {config.location}. "
            "Authentication uses Google Application Default Credentials and is checked only "
            "when you request Gemini narration."
        )

    st.subheader("How the application works")
    st.caption(
        "Both workflows keep user-entered scenarios separate from optional narration. "
        "No language model approves an advance or calculates card economics."
    )
    steps = st.columns(4)
    workflow = (
        ("01 · Enter", "Create a synthetic scenario", "Use a form to change applicant facts or portfolio assumptions. Nothing is persisted."),
        ("02 · Decide", "Run deterministic logic", "Eligibility evaluates ordered rules. Card economics executes fixed formulas and pre-declared gates."),
        ("03 · Inspect", "Review evidence", "See reasons, remedies, financial metrics, exclusions, thresholds, and structured output."),
        ("04 · Explain", "Translate the result", "Deterministic text is immediate. An explicit button can ask Gemini to narrate the already-computed result."),
    )
    for column, (number, title, body) in zip(steps, workflow):
        column.markdown(
            f'<div class="workflow-card"><div class="workflow-step">{number}</div>'
            f'<h4>{title}</h4><p>{body}</p></div>',
            unsafe_allow_html=True,
        )

    st.subheader("Choose an MVP")
    eligibility, economics = st.columns(2)
    with eligibility:
        with st.container(border=True):
            st.markdown("### Advance eligibility")
            st.write(
                "Test approval limits and ordered denial rules using state, deposit "
                "history, outstanding advances, defaults, and account status."
            )
            st.markdown(
                "**Output:** approval and limit, or reason codes with categorized remedies."
            )
            st.link_button(
                "Open Eligibility MVP",
                "/Eligibility",
                icon=":material/fact_check:",
                width="stretch",
            )
    with economics:
        with st.container(border=True):
            st.markdown("### Card economics")
            st.write(
                "Compare sponsor-bank, program-manager, and direct-issuance paths "
                "while changing portfolio economics and walk-away gates."
            )
            st.markdown(
                "**Output:** viable ranking, decisiveness, exclusions, contribution, "
                "exposure, break-even points, and crossover sensitivity."
            )
            st.link_button(
                "Open Card Economics MVP",
                "/Card_Economics",
                icon=":material/finance_mode:",
                width="stretch",
            )

    st.subheader("Architecture boundaries")
    boundary_rows = [
        {
            "Layer": "Scenario input",
            "Eligibility": "Synthetic applicant facts",
            "Card economics": "Portfolio and gate assumptions",
        },
        {
            "Layer": "Decision engine",
            "Eligibility": "Ordered pure rules",
            "Card economics": "Arithmetic formulas and thresholds",
        },
        {
            "Layer": "Evidence",
            "Eligibility": "Reason codes, remedies, allowlisted facts",
            "Card economics": "Computed metrics and failed gates",
        },
        {
            "Layer": "Explanation",
            "Eligibility": "Plain-language deterministic fallback",
            "Card economics": "Deterministic executive memo",
        },
    ]
    st.dataframe(boundary_rows, hide_index=True, width="stretch")

    with st.expander("What this lab does not do"):
        st.markdown(
            "- It does not use real customer data or persist form submissions.\n"
            "- It does not provide lending, compliance, legal, or investment advice.\n"
            "- It does not let a language model change a decision or calculation.\n"
            "- It does not implement the planned EWA portfolio simulator."
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
