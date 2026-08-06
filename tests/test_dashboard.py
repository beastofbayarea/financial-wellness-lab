"""Fast source-contract checks for the Streamlit presentation layer."""

import ast
from pathlib import Path


ROOT = Path(__file__).parents[1]
DASHBOARD = ROOT / "dashboard.py"


def test_dashboard_routes_and_theme_are_present():
    source = DASHBOARD.read_text(encoding="utf-8")
    theme = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")

    assert "How the application works" in source
    assert "/Eligibility" in source and "/Card_Economics" in source
    assert (ROOT / "pages" / "1_Eligibility.py").is_file()
    assert (ROOT / "pages" / "2_Card_Economics.py").is_file()
    assert 'base = "light"' in theme and 'textColor = "#17211B"' in theme


def test_every_scenario_input_has_help_text():
    tree = ast.parse(DASHBOARD.read_text(encoding="utf-8"))
    input_methods = {"selectbox", "number_input", "checkbox", "slider"}
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in input_methods
    ]

    assert len(calls) == 16
    assert all(any(keyword.arg == "help" for keyword in call.keywords) for call in calls)
