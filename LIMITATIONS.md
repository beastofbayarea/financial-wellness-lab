# Limitations

Stated plainly, because the numbers here look more authoritative than they are.

## The data is synthetic

No real customer data of any kind was used. User fixtures in `eligibility/` are hand-written to exercise rule paths. Any distributions in `ewa_sim/` are generated. Nothing here is derived from any employer's internal data, past or present.

## The parameters are illustrative

Figures in `card_economics/assumptions.yaml` are order-of-magnitude estimates assembled from public sources — published interchange schedules, disclosed program-manager pricing, and reported loss rates from public filings of comparable consumer lenders. They are plausible. They are not researched to the standard you would use to actually commit capital.

**What this means:** the *structure* of the comparison is the contribution. The specific output is a worked example. If you took the recommendation and acted on it without replacing the inputs, that would be my failure and yours.

## The rule set is not a compliance artifact

`eligibility/rules.py` encodes plausible eligibility logic to demonstrate a design pattern. It is not a legal review, does not reflect any specific state lending regime, and should not be treated as a compliance baseline.

## The simulation, when it lands, will have a modeling weakness

Synthetic repayment behavior is generated from assumed distributions. Recovering structure that I put in myself is not a finding. The simulator is useful for *sensitivity* — how outcomes move as limits change — and not for *levels*.

## What I would do differently with real data

Replace assumed loss curves with observed cohort performance, replace assumed take rates with actual fee capture, and back-test the eligibility rules against declined applicants who later performed well. All three are impossible without production data, which is why this is a lab and not a recommendation.
