"""Minimal checks for the default inner development loop."""

import ast
from pathlib import Path

from card_economics.model import compare
from eligibility.rules import Applicant, evaluate


ROOT = Path(__file__).parents[1]


def test_core_decision_paths():
    approved = evaluate(Applicant("a", "CA", 90, 3, True, 0, 0))
    denied = evaluate(Applicant("b", "NY", 1, 0, False, 100, 2), collect_all=True)
    economics = compare()

    assert approved.approved and approved.limit_cents == 50_000
    assert not denied.approved and len(denied.denials) >= 4
    assert economics["recommended"] and economics["results"]


def test_dashboard_contract():
    dashboard = (ROOT / "dashboard.py").read_text(encoding="utf-8")
    tree = ast.parse(dashboard)
    input_methods = {"selectbox", "number_input", "checkbox", "slider"}
    inputs = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in input_methods
    ]

    assert "/Eligibility" in dashboard and "/Card_Economics" in dashboard
    assert "Refine executive summary with AI" not in dashboard
    assert "Model audit details" not in dashboard
    assert "How the recommendation is calculated" not in dashboard
    assert "These are operating archetypes, not individual vendors" in dashboard
    assert all(label in dashboard for label in ("Sponsor bank", "Program manager", "Direct issuance"))
    assert len(inputs) == 15
    assert all(any(item.arg == "help" for item in call.keywords) for call in inputs)
