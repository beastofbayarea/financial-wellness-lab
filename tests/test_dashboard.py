"""Smoke and boundary tests for the combined Streamlit dashboard."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

from dashboard import build_card_assumptions, usd


ROOT = Path(__file__).parents[1]


def test_currency_formatter():
    assert usd(1234.5) == "$1,234.50"
    assert usd(-42, 0) == "$-42"


def test_dashboard_pins_an_accessible_light_theme():
    config = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")

    assert 'base = "light"' in config
    assert 'textColor = "#17211B"' in config
    assert 'backgroundColor = "#F4F7F3"' in config


def test_dashboard_assumptions_are_isolated_and_normalized():
    assumptions = build_card_assumptions(
        active_cards=250_000,
        monthly_spend=900,
        average_balance=500,
        revolve_rate_pct=40,
        interchange_rate_pct=2,
        contribution_floor=3_000_000,
        max_months=24,
        decisive_margin=2_000_000,
    )

    assert assumptions["portfolio"]["active_cards"] == 250_000
    assert assumptions["portfolio"]["revolve_rate"] == 0.4
    assert assumptions["revenue"]["interchange_rate"] == 0.02
    assert assumptions["thresholds"]["max_months_to_first_customer"] == 24


def test_dashboard_renders_both_mvp_sections_without_exceptions():
    app = AppTest.from_file(ROOT / "dashboard.py").run(timeout=20)

    assert not app.exception
    assert app.title[0].value == "Financial Wellness Lab"
    assert [tab.label for tab in app.tabs] == ["Eligibility", "Card economics"]
    assert any(metric.label == "Advance limit" for metric in app.metric)
    assert any(metric.label == "Highest-ranked viable path" for metric in app.metric)


def test_eligibility_form_reacts_to_a_restricted_state():
    app = AppTest.from_file(ROOT / "dashboard.py").run(timeout=20)

    state = next(widget for widget in app.selectbox if widget.label == "State")
    submit = next(button for button in app.button if button.label == "Evaluate applicant")
    state.set_value("NY")
    submit.click().run(timeout=20)

    assert not app.exception
    assert any("Declined" in message.value for message in app.error)
    assert any("State Not Serviced" in block.value for block in app.markdown)


def test_card_form_reacts_to_high_volume_and_a_relaxed_launch_gate():
    app = AppTest.from_file(ROOT / "dashboard.py").run(timeout=20)

    monthly_spend = next(
        widget for widget in app.number_input
        if widget.label == "Monthly spend per card"
    )
    max_months = next(
        widget for widget in app.number_input
        if widget.label == "Maximum months to launch"
    )
    submit = next(button for button in app.button if button.label == "Run comparison")
    monthly_spend.set_value(3_000.0)
    max_months.set_value(36)
    submit.click().run(timeout=20)

    assert not app.exception
    recommendation = next(
        metric for metric in app.metric
        if metric.label == "Highest-ranked viable path"
    )
    assert recommendation.value == "Direct issuance"
