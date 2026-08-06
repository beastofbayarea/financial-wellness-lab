# Financial Wellness Lab

Small models exploring a single question: **in consumer credit products, which decisions should be deterministic, and where does language actually belong?**

My position is that the two get conflated. Teams reach for a model where a rule would do, and reach for a rule where a person needs an explanation. Each module here is an argument about where that line sits.

## The rule this repo follows

> **The LLM sits at the explanation layer, never the decision layer.**

Eligibility is decided by deterministic rules. Economics are computed by arithmetic. The language model is handed the *result* and asked to make it legible to a human. It is never handed the inputs and asked for an outcome. This is enforced structurally, not by prompt instruction: the model receives reason codes and computed figures, not raw user data or formulas.

## Modules

| Module                                 | Question it answers                                                                             | Status  |
| -------------------------------------- | ----------------------------------------------------------------------------------------------- | ------- |
| [`eligibility/`](./eligibility)       | Can this user take an advance, and can we tell them *why* in a sentence they'd accept?        | MVP     |
| [`card_economics/`](./card_economics) | Sponsor bank, program manager, or direct issuance — and what assumption would flip the answer? | MVP     |
| [`ewa_sim/`](./ewa_sim)               | How does portfolio margin move as advance limits rise?                                          | Planned |

## Findings so far

**Eligibility.** Denial reasons are a product surface, not an error state. Once you require every rule to carry a remedy ("what would change this"), roughly a third of the rules turn out to have no honest remedy — which is itself the finding. Those are the rules worth revisiting.

**Card economics.** Under the default assumptions the program-manager path ranks first at **$3.79M** annual contribution, ahead of sponsor bank at **$3.02M**. But the gap is **$0.77M**, below the decisiveness threshold declared before the model ran — so the model's honest output is *"these two are indistinguishable, decide on something else."* That something else is strategic: only direct issuance owns the receivable, and it is excluded here on time-to-market and contribution, yet it wins outright once monthly spend per card clears roughly **$700**.

The useful finding is therefore not a recommendation. It is that **the choice is volume-dependent and the near-term answer is a coin flip**, which means the real decision is whether you are optimizing for the next 18 months or for owning the receivable later.

## Quickstart

```bash
git clone https://github.com/beastofbayarea/financial-wellness-lab.git
cd financial-wellness-lab
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m pytest
```

On Windows PowerShell, activate the environment with
`.\.venv\Scripts\Activate.ps1` instead.

Run the modules:

```bash
python -m eligibility.demo
python -m card_economics.compare
```

Or explore both MVPs in the local dashboard:

```bash
streamlit run dashboard.py
```

The dashboard opens a workflow overview with separate pages for the eligibility
scenario builder and card-economics assumption lab. Both pages call the same
deterministic functions used by the CLI demos.

Both run without cloud credentials. Optional narration uses Gemini on Vertex AI
with Application Default Credentials; see [`SETUP.md`](./SETUP.md). Without
Vertex access, the modules preserve the structured result and use deterministic
fallback text.

The test suite covers rule ordering, multi-reason
diagnostics, narration boundaries and fallbacks, economic thresholds, unit
economics, volume sensitivity, and dashboard rendering.

## See also

- [`DECISIONS.md`](./DECISIONS.md) — choices made and rejected, with reasoning
- [`LIMITATIONS.md`](./LIMITATIONS.md) — what this is not, and what the numbers are worth
- [`SETUP.md`](./SETUP.md) — platform-specific installation, commands, and configuration

All data is synthetic. All parameters are illustrative and drawn from public sources.
