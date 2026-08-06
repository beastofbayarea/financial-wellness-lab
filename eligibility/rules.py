"""Deterministic eligibility rules for an earned-wage-access advance.

Two design constraints, both enforced by the code rather than by convention:

1. A rule cannot be registered without a `remedy`. A denial with no path
   forward is a dead end for the user and a support ticket for the business.
   Forcing the field at registration time is what surfaced that several
   plausible rules have no honest remedy.

2. Rules are pure functions of an `Applicant`. Same input, same answer, every
   time. Nothing here calls a network or a model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable
import yaml


class RemedyCategory(str, Enum):
    WAIT_TENURE = "wait_tenure"            # e.g., deposit history countdown
    USER_ACTION = "user_action"            # e.g., repay outstanding balance
    SUPPORT = "support_intervention"       # e.g., resolve hold on account
    PERMANENT = "out_of_scope"             # e.g., state not serviced


def _load_config() -> dict:
    config_path = Path(__file__).parent / "rules_config.yaml"
    defaults = {
        "restricted_states": ["NY", "CT"],
        "min_deposit_history_days": 60,
        "min_deposit_count": 2,
        "base_limit_cents": 25_000,
        "direct_deposit_limit_cents": 50_000,
    }
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f)
                if loaded and isinstance(loaded, dict):
                    defaults.update(loaded)
        except Exception:
            pass
    return defaults


CONFIG = _load_config()

RESTRICTED_STATES = frozenset(s.upper() for s in CONFIG.get("restricted_states", ["NY", "CT"]))
MIN_DEPOSIT_HISTORY_DAYS = int(CONFIG.get("min_deposit_history_days", 60))
MIN_DEPOSIT_COUNT = int(CONFIG.get("min_deposit_count", 2))
BASE_LIMIT_CENTS = int(CONFIG.get("base_limit_cents", 25_000))
DIRECT_DEPOSIT_LIMIT_CENTS = int(CONFIG.get("direct_deposit_limit_cents", 50_000))


@dataclass(frozen=True)
class Applicant:
    """Everything a rule may consider. Deliberately small."""

    user_id: str
    state: str
    deposit_history_days: int
    recurring_deposit_count: int
    has_direct_deposit: bool
    outstanding_advance_cents: int
    prior_defaults: int
    account_frozen: bool = False


@dataclass(frozen=True)
class Remedy:
    text: str
    category: RemedyCategory = RemedyCategory.USER_ACTION
    estimated_days: int | None = None


@dataclass(frozen=True)
class Rule:
    code: str
    remedy: str | Remedy | Callable[[Applicant], str | Remedy]
    predicate: Callable[[Applicant], bool]
    facts: Callable[[Applicant], dict] = field(default=lambda a: {})
    category: RemedyCategory = RemedyCategory.USER_ACTION

    def __post_init__(self) -> None:
        remedy_val = self.remedy
        if callable(remedy_val):
            # Callable remedies will be evaluated at runtime; we verify registration isn't None
            if remedy_val is None:
                raise ValueError(f"Rule {self.code} has no remedy.")
            return

        if isinstance(remedy_val, Remedy):
            text = remedy_val.text
        else:
            text = str(remedy_val)

        if not text or not text.strip():
            raise ValueError(
                f"Rule {self.code} has no remedy. Every denial must tell the "
                f"user what would change it."
            )

    def resolve_remedy(self, applicant: Applicant) -> Remedy:
        if callable(self.remedy):
            res = self.remedy(applicant)
            if isinstance(res, Remedy):
                return res
            return Remedy(text=str(res), category=self.category)
        elif isinstance(self.remedy, Remedy):
            return self.remedy
        else:
            return Remedy(text=str(self.remedy), category=self.category)


@dataclass(frozen=True)
class DenialReason:
    code: str
    remedy: str
    category: RemedyCategory
    facts: dict = field(default_factory=dict)
    estimated_days: int | None = None


@dataclass(frozen=True)
class Decision:
    approved: bool
    limit_cents: int
    denials: tuple[DenialReason, ...] = field(default_factory=tuple)
    facts: dict = field(default_factory=dict)

    @property
    def reason_code(self) -> str | None:
        if self.denials:
            return self.denials[0].code
        return "APPROVED" if self.approved else None

    @property
    def remedy(self) -> str | None:
        if self.denials:
            return self.denials[0].remedy
        return None

    @property
    def primary_denial(self) -> DenialReason | None:
        return self.denials[0] if self.denials else None


# --- The rule set -----------------------------------------------------------
# Ordered. First match wins by default, or all matching rules collected if requested.

RULES: list[Rule] = [
    Rule(
        code="ACCOUNT_FROZEN",
        remedy=Remedy("Contact support to resolve the hold on your account.", RemedyCategory.SUPPORT),
        predicate=lambda a: a.account_frozen,
        category=RemedyCategory.SUPPORT,
    ),
    Rule(
        code="STATE_NOT_SERVICED",
        remedy=Remedy("This product is not offered in your state today.", RemedyCategory.PERMANENT),
        predicate=lambda a: a.state.upper() in RESTRICTED_STATES,
        category=RemedyCategory.PERMANENT,
    ),
    Rule(
        code="OUTSTANDING_ADVANCE",
        remedy=lambda a: f"Repay your current advance of ${a.outstanding_advance_cents / 100:,.2f} to request another.",
        predicate=lambda a: a.outstanding_advance_cents > 0,
        facts=lambda a: {"outstanding_cents": a.outstanding_advance_cents},
        category=RemedyCategory.USER_ACTION,
    ),
    Rule(
        code="DEPOSIT_HISTORY_TOO_SHORT",
        remedy=lambda a: Remedy(
            text=f"Keep your account connected for {max(0, MIN_DEPOSIT_HISTORY_DAYS - a.deposit_history_days)} more days to reach the 60-day requirement.",
            category=RemedyCategory.WAIT_TENURE,
            estimated_days=max(0, MIN_DEPOSIT_HISTORY_DAYS - a.deposit_history_days),
        ),
        predicate=lambda a: a.deposit_history_days < MIN_DEPOSIT_HISTORY_DAYS,
        facts=lambda a: {
            "days_required": MIN_DEPOSIT_HISTORY_DAYS,
            "days_observed": a.deposit_history_days,
        },
        category=RemedyCategory.WAIT_TENURE,
    ),
    Rule(
        code="TOO_FEW_DEPOSITS",
        remedy=lambda a: Remedy(
            text=f"Receive {max(0, MIN_DEPOSIT_COUNT - a.recurring_deposit_count)} more recurring deposit(s) to qualify.",
            category=RemedyCategory.WAIT_TENURE,
        ),
        predicate=lambda a: a.recurring_deposit_count < MIN_DEPOSIT_COUNT,
        category=RemedyCategory.WAIT_TENURE,
    ),
    # Note: kept deliberately. See DECISIONS.md D3 — the remedy here is weak,
    # which is a signal the rule itself deserves review rather than a signal
    # to drop the remedy field.
    Rule(
        code="PRIOR_DEFAULTS",
        remedy=Remedy("Repay past balances in full, then reapply after 90 days.", RemedyCategory.USER_ACTION, estimated_days=90),
        predicate=lambda a: a.prior_defaults >= 2,
        category=RemedyCategory.USER_ACTION,
    ),
]


def limit_for(applicant: Applicant) -> int:
    return (
        DIRECT_DEPOSIT_LIMIT_CENTS
        if applicant.has_direct_deposit
        else BASE_LIMIT_CENTS
    )


def evaluate(applicant: Applicant, collect_all: bool = False) -> Decision:
    """Decide eligibility. Pure, deterministic, no I/O."""
    denials: list[DenialReason] = []
    
    for rule in RULES:
        if rule.predicate(applicant):
            rem = rule.resolve_remedy(applicant)
            f = rule.facts(applicant)
            denial = DenialReason(
                code=rule.code,
                remedy=rem.text,
                category=rem.category,
                facts=f,
                estimated_days=rem.estimated_days,
            )
            denials.append(denial)
            if not collect_all:
                break

    if denials:
        primary = denials[0]
        return Decision(
            approved=False,
            limit_cents=0,
            denials=tuple(denials),
            facts=primary.facts,
        )

    limit = limit_for(applicant)
    return Decision(
        approved=True,
        limit_cents=limit,
        denials=(),
        facts={"limit_cents": limit},
    )
