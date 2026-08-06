# Decision records

Short records of choices made, and the alternatives rejected. Format: context, decision, consequence.

---

## D1 — Deterministic rules, not a learned model, for eligibility

**Context.** Eligibility could be a scoring model. It would probably be more accurate at the margin.

**Decision.** Deterministic rules.

**Why.** An advance decision has to be explainable to the person it affects and auditable by someone who was not in the room. A rule engine gives both for free. A score gives neither without substantial extra machinery, and the accuracy gain at the margin is not worth it on a product where the downside of a wrong approval lands on someone living paycheck to paycheck.

**Consequence.** Accepted lower ceiling on approval optimization in exchange for explainability. Revisit if approval rate becomes the binding constraint.

---

## D2 — The LLM never sees raw user data

**Context.** The obvious implementation hands the model the user record and asks for an explanation.

**Decision.** The model receives a reason code and a small set of pre-approved template values. Nothing else.

**Why.** If the model can see the inputs, it can construct an outcome, and a model that *can* decide will eventually appear to have decided. Separating them structurally means the failure mode is a badly worded sentence, not a wrong decision. It also keeps PII out of the request entirely.

**Consequence.** Explanations are less specific than they could be. Worth it.

---

## D3 — Every denial rule must carry a remedy

**Context.** Rules naturally express what is wrong. Users need to know what would change it.

**Decision.** A rule cannot be registered without a `remedy` field.

**Why.** A denial without a path forward is a dead end for the user and a support ticket for the business. Forcing the field at registration time surfaced that several plausible rules have no honest remedy — which is a signal those rules deserve scrutiny.

**Consequence.** Slightly more friction to add rules. Intentional.

---

## D4 — Config-driven scenarios for card economics

**Context.** The comparison could be hardcoded, or parameterized.

**Decision.** Assumptions live in YAML. The engine loads and computes.

**Why.** The argument of that module is that walk-away thresholds should be set *before* diligence, not after. Putting thresholds in config, with tests asserting they trigger, makes that claim structural rather than rhetorical. It also lets someone disagree with an assumption by editing one line instead of reading code.

**Consequence.** More setup than a notebook. Buys the ability for a reader to challenge the inputs cheaply.

---

## D5 — Fail open on the narration layer

**Context.** What happens if the API key is missing or the call fails?

**Decision.** Return the structured output and skip narration. Never block the decision.

**Why.** The decision layer must not depend on a network call to a third party. If narration is unavailable, the product degrades to a reason code, which is worse UX and identical correctness.

**Consequence.** Two output paths to maintain. The deterministic fallback is
covered by tests and is the default behavior when no API key is configured.

---

## D6 — Treat viability and decisiveness as separate results

**Context.** The economically highest-ranked card path can clear every
walk-away gate while leading the runner-up by too little to support a confident
choice.

**Decision.** `compare()` reports both a recommended viable path and a separate
`decisive` flag with a machine-readable reason.

**Why.** Collapsing these into one label would turn a narrow modeled lead into
false certainty. The distinction preserves the ranking while making the
pre-declared margin threshold visible.

**Consequence.** Callers must present both fields. In the default scenario,
Program manager ranks first, but its $0.77M lead is below the $1.50M
decisiveness threshold.

---

## D7 — One thin dashboard over both deterministic engines

**Context.** The CLI demos prove the two MVPs work, but make scenario comparison
slower for readers who do not want to edit Python or YAML.

**Decision.** Provide one Streamlit application with a workflow overview and
separate pages for eligibility and card economics. The UI imports the existing
rule and model functions.

**Why.** A thin presentation layer makes both MVPs testable without creating a
second implementation of either decision path. Streamlit also keeps the project
Python-only and locally runnable.

**Consequence.** Streamlit becomes a runtime dependency. Lightweight source
contract tests verify the routes, theme, and input help without repeatedly
booting Streamlit; domain tests remain the source of truth for calculations.
The app pins a light, high-contrast theme so operating-system theme detection
cannot produce unreadable foreground/background combinations.

---

## D8 — Reuse the Cent Vertex AI contract for optional narration

**Context.** The related Cent Capital application standardizes generation on
Google's Gen AI SDK, Vertex AI, the global region, and the
`gemini-flash-latest` alias.

**Decision.** Use the Python `google-genai` SDK with the same environment names
and Application Default Credentials. Do not copy credentials into this repo.

**Why.** A shared provider contract reduces configuration drift while preserving
each repository's credential boundary. The rolling Flash alias is appropriate
for short explanation and memo tasks, and the decision engines remain fully
independent from it.

**Consequence.** Gemini narration requires a configured Google Cloud project,
Vertex access, and an authorized ADC identity. Missing configuration or any SDK
failure returns `None`; deterministic fallbacks remain the correctness path.
