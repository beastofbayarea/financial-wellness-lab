"""Interactive dashboard for the financial-wellness decision workflows."""

from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path

# Ensure repository root is on sys.path for Streamlit Cloud deployment
_ROOT_DIR = Path(__file__).resolve().parent
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))

import altair as alt
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

CRITERION_LABELS = {
    "min_annual_contribution_usd": "Annual contribution is below the required minimum",
    "max_months_to_first_customer": "Launch would take longer than the allowed timeline",
    "max_annual_loss_rate": "Expected annual credit losses exceed the risk limit",
}


def usd(value: float, decimals: int = 2) -> str:
    """Format a numeric value as US dollars."""
    return f"${value:,.{decimals}f}"


def plain_criteria(failed: list[str] | tuple[str, ...]) -> str:
    """Translate internal criterion identifiers into executive-facing language."""
    return "; ".join(CRITERION_LABELS.get(item, "Does not meet an investment criterion") for item in failed)


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
    memo_slot = st.empty()

    st.markdown('<div class="section-kicker">Decision scope</div>', unsafe_allow_html=True)
    st.markdown("## Three operating models cover the practical ways to launch a card program")
    st.markdown(
        '<div class="scope-copy">These are operating archetypes, not individual vendors. '
        'They represent the three materially different choices for who provides the bank '
        'license, runs the program, and carries customer balances. Specific providers can '
        'be evaluated after management selects the preferred operating model.</div>',
        unsafe_allow_html=True,
    )
    option_columns = st.columns(3)
    option_details = (
        (
            "01 · Sponsor bank",
            "Use a bank as the regulated issuer while your team coordinates the customer experience and other partners.",
            "Best when",
            "Management wants more control than a fully managed program without building a bank-grade operating platform.",
            "Primary trade-off",
            "More partner coordination and a moderately longer launch than a program manager.",
        ),
        (
            "02 · Program manager",
            "Use one specialist partner to coordinate the issuing bank, processing, compliance, and day-to-day program operations.",
            "Best when",
            "Speed, lower implementation complexity, and a single accountable operating partner matter most.",
            "Primary trade-off",
            "Higher partner fees and less direct control over the operating model.",
        ),
        (
            "03 · Direct issuance",
            "Build and operate the issuing capability directly, retaining the economics while holding customer receivables and credit risk.",
            "Best when",
            "Scale, strategic control, and long-term economics justify substantial investment and regulatory responsibility.",
            "Primary trade-off",
            "The longest launch, highest fixed cost, and direct exposure to credit losses and customer balances.",
        ),
    )
    for column, details in zip(option_columns, option_details):
        title, definition, fit_label, fit, tradeoff_label, tradeoff = details
        with column:
            st.markdown(
                f'<div class="strategy-card"><div class="strategy-card-title">{title}</div>'
                f'<p>{definition}</p><div class="strategy-card-label">{fit_label}</div>'
                f'<p>{fit}</p><div class="strategy-card-label">{tradeoff_label}</div>'
                f'<p>{tradeoff}</p></div>',
                unsafe_allow_html=True,
            )

    st.markdown("### Scenario assumptions")
    st.caption("Set the portfolio economics and investment criteria for this analysis.")

    with st.form("economics_form"):
        volume, economics, gates = st.columns(3)
        with volume:
            st.markdown("**Portfolio**")
            active_cards = st.number_input(
                "Active cards", min_value=1, max_value=10_000_000,
                value=int(portfolio["active_cards"]), step=10_000,
                help="The number of cards expected to be actively used. More active cards increase purchase volume and interchange revenue, but also increase revolving balances and credit exposure. Fixed operating costs stay unchanged, so larger portfolios usually improve contribution per program.",
            )
            monthly_spend = st.number_input(
                "Monthly spend per card", min_value=1.0, max_value=10_000.0,
                value=float(portfolio["monthly_spend_per_card_usd"]), step=25.0,
                help="The average amount one active cardholder spends each month. Higher spend produces more interchange revenue for every strategy and can help a strategy clear the minimum annual contribution requirement. It is the most important volume sensitivity in this comparison.",
            )
        with economics:
            st.markdown("**Economics**")
            average_balance = st.number_input(
                "Average revolving balance", min_value=0.0, max_value=25_000.0,
                value=float(portfolio["avg_revolving_balance_usd"]), step=25.0,
                help="The typical unpaid balance among customers who carry debt from one month to the next. For direct issuance, a larger balance increases interest income, expected credit losses, and the receivables held on the balance sheet. Partner-led strategies do not hold these receivables in this model.",
            )
            revolve_rate_pct = st.slider(
                "Accounts revolving", min_value=0.0, max_value=100.0,
                value=float(portfolio["revolve_rate"] * 100), step=1.0,
                format="%.0f%%",
                help="The percentage of active cardholders who do not pay their full statement balance each month. A higher percentage increases interest income for direct issuance, but also increases expected losses and balance-sheet exposure. It does not create interest income for the partner-led strategies.",
            )
            interchange_rate_pct = st.number_input(
                "Net interchange rate (%)", min_value=0.0, max_value=10.0,
                value=float(revenue["interchange_rate"] * 100), step=0.05,
                help="The share of purchase volume retained as interchange after network costs. A higher rate increases revenue for every strategy. Partner fees also increase because they are calculated as a share of interchange revenue.",
            )
        with gates:
            st.markdown("**Investment criteria**")
            contribution_floor = st.number_input(
                "Minimum annual contribution", min_value=-50_000_000.0,
                max_value=100_000_000.0,
                value=float(thresholds["min_annual_contribution_usd"]),
                step=250_000.0,
                help="The lowest annual profit contribution management is willing to accept. A strategy below this amount is removed from consideration even if it performs better on speed or strategic control. Raising the minimum makes the screen more selective.",
            )
            max_months = st.number_input(
                "Maximum months to launch", min_value=1, max_value=120,
                value=int(thresholds["max_months_to_first_customer"]),
                help="The longest acceptable time before the first customer can use the card. A strategy taking longer is removed from consideration. A tighter timeline favors partner-led launches; a longer timeline may allow direct issuance to remain in the comparison.",
            )
            decisive_margin = st.number_input(
                "Decisive margin", min_value=0.0, max_value=100_000_000.0,
                value=float(thresholds["min_margin_advantage_over_next_best_usd"]),
                step=250_000.0,
                help="The minimum annual contribution advantage required to call the financial result conclusive. This does not remove a strategy from consideration. It determines whether the leading option is strong enough to decide on economics alone or needs further strategic review.",
            )
        st.form_submit_button("Update analysis", type="primary", width="stretch")

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

    with memo_slot.container():
        st.markdown('<div class="section-kicker">Executive memorandum</div>', unsafe_allow_html=True)
        st.markdown("## Decision brief")
        with st.spinner("Preparing the executive memorandum…"):
            executive_memo = write_memo(output)
        with st.container(border=True):
            st.markdown(executive_memo or write_memo_fallback(output))
        if executive_memo is None:
            st.caption(
                "The standard decision brief is shown because AI-assisted wording is temporarily unavailable."
            )

    if output["recommended"] is None:
        takeaway = "No strategy meets the current investment criteria"
    elif output["decisive"]:
        takeaway = f"{output['recommended']} leads with a decision-ready economic advantage"
    else:
        takeaway = f"{output['recommended']} leads, but economics alone do not settle the decision"

    st.markdown('<div class="section-kicker">Executive takeaway</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="takeaway-headline">{takeaway}</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="takeaway-subtitle">The recommendation applies the stated '
        'contribution, launch-time, loss-rate, and confidence criteria.</div>',
        unsafe_allow_html=True,
    )
    winner, margin, confidence = st.columns(3)
    winner.metric("Leading strategy", output["recommended"] or "No viable option")
    margin.metric(
        "Lead over runner-up",
        usd(output["margin_over_next_best_usd"], 0)
        if output["margin_over_next_best_usd"] is not None else "N/A",
    )
    confidence.metric("Confidence", "Decisive" if output["decisive"] else "Further review")

    if output["recommended"] is None:
        decision_note = "Adjust the assumptions or review which investment criterion is most flexible."
    elif output["decisive"]:
        decision_note = "The modeled advantage clears the confidence threshold; economics support moving forward."
    else:
        decision_note = "The lead is below the confidence threshold; use operating control, partner capability, and execution risk to break the tie."
    st.markdown(f'<div class="decision-note">{decision_note}</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-kicker">Comparative economics</div>', unsafe_allow_html=True)
    excluded_count = len(output["excluded"])
    if output["recommended"] is None:
        comparison_headline = "No strategy clears all investment criteria"
    elif excluded_count == 1:
        comparison_headline = f"{output['recommended']} leads; one strategy does not meet all criteria"
    elif excluded_count > 1:
        comparison_headline = f"{output['recommended']} leads; {excluded_count} strategies do not meet all criteria"
    else:
        comparison_headline = f"{output['recommended']} leads annual contribution"
    st.markdown(f"### {comparison_headline}")

    rows = [
        {
            "Strategy": result["label"],
            "Annual contribution": result["annual_contribution_usd"],
            "Per active card": result["annual_contribution_per_card_usd"],
            "Receivables held": result["balance_sheet_exposure_usd"],
            "Time to launch": result["months_to_first_customer"],
            "Assessment": "Meets all criteria" if not result["failed_thresholds"] else "Does not meet criteria",
            "Reason": plain_criteria(result["failed_thresholds"]) or "No concerns under the current assumptions",
        }
        for result in output["results"]
    ]
    st.dataframe(
        rows,
        column_config={
            "Strategy": st.column_config.TextColumn(help="The operating model used to issue and manage the card program."),
            "Annual contribution": st.column_config.NumberColumn(format="dollar", help="Annual revenue less partner fees, expected credit losses, fixed operating costs, and compliance staffing."),
            "Per active card": st.column_config.NumberColumn(format="dollar", help="Annual contribution divided by active cards, making strategies comparable on a per-customer basis."),
            "Receivables held": st.column_config.NumberColumn(format="dollar", help="Revolving customer balances held on the program's balance sheet. This is exposure, not required regulatory capital."),
            "Time to launch": st.column_config.NumberColumn(format="%d months", help="Estimated time until the first customer can use the program."),
            "Assessment": st.column_config.TextColumn(help="Whether the strategy satisfies every stated investment criterion."),
            "Reason": st.column_config.TextColumn(help="Why a strategy was removed from consideration, or confirmation that it cleared the screen."),
        },
        hide_index=True,
        width="stretch",
    )
    chart_rows = [
        {
            "Strategy": result["label"],
            "Annual contribution": result["annual_contribution_usd"],
            "Highlight": "Recommended" if result["label"] == output["recommended"] else "Other",
        }
        for result in output["results"]
    ]
    chart = (
        alt.Chart(alt.Data(values=chart_rows))
        .mark_bar(cornerRadiusEnd=4, size=28)
        .encode(
            y=alt.Y("Strategy:N", sort="-x", title=None, axis=alt.Axis(labelColor="#cbd5e1", labelFontSize=12)),
            x=alt.X(
                "Annual contribution:Q",
                title="Annual contribution",
                axis=alt.Axis(format="$,.0s", grid=True, gridColor="#1e293b", labelColor="#94a3b8", titleColor="#94a3b8"),
            ),
            color=alt.condition(alt.datum.Highlight == "Recommended", alt.value("#6366f1"), alt.value("#334155")),
            tooltip=[alt.Tooltip("Strategy:N"), alt.Tooltip("Annual contribution:Q", format="$,.0f")],
        )
        .properties(height=190)
        .configure_view(strokeWidth=0)
    )
    st.altair_chart(chart, width="stretch")
    st.caption("Annual contribution reflects the current scenario and is shown before tax. Indigo identifies the recommended strategy.")

    st.markdown('<div class="section-kicker">What needs to be true</div>', unsafe_allow_html=True)
    st.markdown("### Monthly spend required to meet the contribution minimum")
    milestone_columns = st.columns(len(assumptions["paths"]))
    for column, key in zip(milestone_columns, assumptions["paths"]):
        point = break_even_spend(key, assumptions)
        column.metric(
            assumptions["paths"][key]["label"],
            usd(point, 0) + "/mo" if point is not None else "Not reached",
            help=f"The average monthly card spend needed for {assumptions['paths'][key]['label']} to reach management's minimum annual contribution. A lower amount means the strategy can succeed at a smaller customer-spend level.",
        )
    crossover = find_crossover_spend("direct_issuance", "program_manager", assumptions)
    if crossover is not None:
        st.info(
            f"At approximately {usd(crossover, 0)} in monthly spend per active card, "
            "Direct issuance and Program manager produce the same annual contribution. "
            "Above that point, Direct issuance contributes more, assuming every other input stays unchanged."
        )



def apply_dashboard_styles() -> None:
    """Apply a sleek, minimalist dark-mode visual treatment to every dashboard page."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
        
        :root { color-scheme: dark; }
        
        html, body, [data-testid="stAppViewContainer"] {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }
        
        .stApp {
            background: #090d16;
            background-image: 
                radial-gradient(ellipse at 50% 0%, #151d30 0%, #090d16 75%),
                radial-gradient(circle at 85% 30%, rgba(99, 102, 241, 0.04) 0%, transparent 50%);
            color: #e2e8f0;
        }
        
        .block-container { max-width: 1280px; padding-top: 2.2rem; padding-bottom: 3.5rem; }
        
        .stApp h1, .stApp h2, .stApp h3, .stApp h4 {
            color: #f8fafc;
            font-weight: 700;
            letter-spacing: -0.02em;
        }
        
        .stApp p, .stApp label, .stApp [data-testid="stCaptionContainer"] {
            color: #94a3b8;
        }
        
        .section-kicker {
            color: #818cf8;
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.14em;
            text-transform: uppercase;
            margin-top: 2.2rem;
            margin-bottom: 0.4rem;
        }
        
        .takeaway-headline {
            color: #f8fafc;
            font-size: 2rem;
            font-weight: 700;
            line-height: 1.2;
            max-width: 920px;
            margin-bottom: 0.45rem;
            letter-spacing: -0.02em;
        }
        
        .takeaway-subtitle {
            color: #94a3b8;
            font-size: 1rem;
            max-width: 860px;
            margin-bottom: 1.25rem;
        }
        
        .decision-note {
            background: rgba(30, 41, 59, 0.6);
            border-left: 4px solid #6366f1;
            border-radius: 0 8px 8px 0;
            color: #e2e8f0;
            padding: 0.95rem 1.1rem;
            margin: 0.85rem 0 1.8rem;
            backdrop-filter: blur(8px);
        }
        
        .scope-copy {
            color: #94a3b8;
            font-size: 1rem;
            line-height: 1.6;
            max-width: 960px;
            margin: 0 0 1.4rem;
        }
        
        .strategy-card {
            background: rgba(17, 24, 39, 0.75);
            border-top: 3px solid #6366f1;
            border-right: 1px solid rgba(255, 255, 255, 0.08);
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            border-left: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 12px;
            min-height: 320px;
            padding: 1.2rem 1.25rem;
            margin-bottom: 1.2rem;
            backdrop-filter: blur(12px);
            transition: all 0.25s ease;
        }
        
        .strategy-card:hover {
            transform: translateY(-3px);
            border-color: rgba(99, 102, 241, 0.4);
            box-shadow: 0 12px 30px -10px rgba(0, 0, 0, 0.6), 0 0 20px rgba(99, 102, 241, 0.12);
        }
        
        .strategy-card-title {
            color: #f8fafc;
            font-size: 1.1rem;
            font-weight: 700;
            margin-bottom: 0.75rem;
        }
        
        .strategy-card p {
            color: #cbd5e1;
            font-size: 0.9rem;
            line-height: 1.5;
        }
        
        .strategy-card-label {
            color: #818cf8;
            font-size: 0.7rem;
            font-weight: 700;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            margin-top: 0.9rem;
        }
        
        [data-testid="stMetric"], .workflow-card {
            background: rgba(17, 24, 39, 0.75) !important;
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
            border-radius: 12px !important;
            padding: 1.1rem !important;
            backdrop-filter: blur(10px);
            transition: all 0.2s ease;
        }

        [data-testid="stMetric"]:hover {
            border-color: rgba(99, 102, 241, 0.3) !important;
        }
        
        [data-testid="stMetricLabel"] p {
            color: #94a3b8 !important;
            font-size: 0.82rem !important;
            font-weight: 600 !important;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        [data-testid="stMetricValue"] {
            color: #f8fafc !important;
            font-weight: 700 !important;
        }
        
        .workflow-card {
            min-height: 185px;
            margin-bottom: 0.75rem;
        }
        
        .hero-kicker {
            color: #818cf8;
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.14em;
            text-transform: uppercase;
            margin-bottom: 0.6rem;
        }
        
        .hero-copy {
            color: #cbd5e1;
            font-size: 1.15rem;
            max-width: 740px;
            margin-bottom: 2.2rem;
            line-height: 1.6;
        }
        
        .principle {
            padding: 0.8rem 1rem;
            background: rgba(17, 24, 39, 0.6);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 10px;
        }
        
        .principle strong {
            display: block;
            font-size: 0.96rem;
            color: #f8fafc;
            margin-bottom: 0.25rem;
        }
        
        .principle span {
            color: #94a3b8;
            font-size: 0.88rem;
            line-height: 1.45;
        }
        
        [data-testid="stForm"] {
            background: rgba(17, 24, 39, 0.8);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 14px;
            padding: 1.5rem;
            backdrop-filter: blur(12px);
        }
        
        /* Dark inputs & dropdowns */
        div[data-baseweb="input"] > div,
        div[data-baseweb="select"] > div {
            background: #1e293b !important;
            border-color: #334155 !important;
            color: #f8fafc !important;
            border-radius: 8px !important;
        }

        input {
            color: #f8fafc !important;
        }

        /* Buttons */
        [data-testid="stFormSubmitButton"] button,
        button[kind="primary"] {
            background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%) !important;
            border: none !important;
            color: #ffffff !important;
            font-weight: 600 !important;
            border-radius: 8px !important;
            box-shadow: 0 4px 14px 0 rgba(99, 102, 241, 0.35) !important;
            transition: all 0.2s ease !important;
        }

        [data-testid="stFormSubmitButton"] button:hover,
        button[kind="primary"]:hover {
            box-shadow: 0 6px 20px 0 rgba(99, 102, 241, 0.5) !important;
            transform: translateY(-1px);
        }

        [data-testid="stFormSubmitButton"] button p,
        button[kind="primary"] p {
            color: #ffffff !important;
            font-weight: 600 !important;
        }
        
        /* Container Cards */
        [data-testid="stVerticalBlock"] > div[data-testid="element-container"] > div[data-testid="stMarkdownContainer"] {
            color: #e2e8f0;
        }

        /* Sidebar Styling */
        [data-testid="stSidebar"] {
            background: #0b0f19 !important;
            border-right: 1px solid rgba(255, 255, 255, 0.08) !important;
        }
        
        .product-name {
            font-size: 1.15rem;
            font-weight: 800;
            color: #f8fafc;
            letter-spacing: -0.01em;
        }
        
        .product-kicker {
            color: #818cf8;
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            margin-bottom: 1.4rem;
        }
        
        .nav-item {
            display: block;
            padding: 0.72rem 0.9rem;
            margin: 0.25rem 0;
            border-radius: 0.6rem;
            color: #94a3b8 !important;
            text-decoration: none !important;
            font-weight: 500;
            font-size: 0.93rem;
            transition: all 0.2s ease;
        }
        
        .nav-item:hover {
            background: rgba(255, 255, 255, 0.05);
            color: #f8fafc !important;
        }
        
        .nav-item.active {
            background: linear-gradient(135deg, rgba(99, 102, 241, 0.22) 0%, rgba(79, 70, 229, 0.1) 100%);
            color: #818cf8 !important;
            border-left: 3px solid #6366f1;
            font-weight: 700;
        }
        
        hr {
            border-color: rgba(255, 255, 255, 0.08) !important;
        }
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
