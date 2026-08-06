# Card Economics Model

**Question:** Sponsor bank, program manager, or direct issuance — and what assumption would flip the answer?

---

## Design Architecture & Point of the Module

The primary contribution of this module is not the specific path recommendation. Rather, it demonstrates a structural diligence principle: **walk-away thresholds are declared in `assumptions.yaml` before the comparison runs**, and `tests/test_model.py` asserts they actually bind. Setting the line after seeing the numbers is how a diligence process talks itself into a bad deal.

```
+------------------------+      Loads Params      +------------------------+
|    assumptions.yaml    | ---------------------> |        model.py        |
| (Thresholds & Costs)   |                        | (Deterministic Engine) |
+------------------------+                        +------------------------+
                                                              |
                                                    PathResult / Metrics
                                                              |
                                                              v
                                                  +------------------------+
                                                  |    Narrator (LLM)      |
                                                  |  (shared/narrator.py)  |
                                                  +------------------------+
                                                              |
                                                              v
                                                   Executive Decision Memo
```

---

## Mathematical Formulation

The financial engine evaluates each issuance model deterministically using the following arithmetic rules:

### 1. Revenue Dynamics
- **Annual Spend ($)**: $\text{Active Cards} \times \text{Monthly Spend Per Card} \times 12$
- **Interchange Revenue ($)**: $\text{Annual Spend} \times \text{Interchange Rate}$
- **Revolving Balance ($)**: $\text{Active Cards} \times \text{Revolve Rate} \times \text{Avg Balance}$
- **Interest Revenue ($)**: $\text{Revolving Balance} \times \text{APR}$ *(Accrues ONLY if `owns_receivable = True`)*

### 2. Cost Dynamics & Capital Exposure
- **Partner Fees ($)**: $\text{Interchange Revenue} \times \text{Partner Fee Share}$
- **Credit Losses ($)**: $\text{Revolving Balance} \times \text{Loss Rate}$ *(Borne ONLY if `owns_receivable = True`)*
- **Compliance Cost ($)**: $\text{Compliance Headcount} \times \text{Cost Per Head}$
- **Balance Sheet Exposure ($)**: $\text{Revolving Balance}$ *(Required capital held ONLY if `owns_receivable = True`)*

### 3. Net Contribution & Unit Economics
- **Annual Contribution ($)**: $\text{Interchange} + \text{Interest} - \text{Partner Fees} - \text{Credit Losses} - \text{Fixed Costs} - \text{Compliance Costs}$
- **Contribution Per Card ($/Card/Yr)**: $\frac{\text{Annual Contribution}}{\text{Active Cards}}$
- **Return on Capital (%)**: $\frac{\text{Annual Contribution}}{\text{Balance Sheet Exposure}} \times 100$

---

## Comparative Results Summary

| Issuance Path | Annual Contribution | Unit Economics ($/Card/Yr) | Balance Sheet Exposure | Time-to-Market | Viability Status |
|---|---|---|---|---|---|
| **Program manager** | **$3.79M** | **$37.91** | **$0** | **6 months** | **Recommended** |
| **Sponsor bank** | **$3.02M** | **$30.20** | **$0** | **9 months** | Viable |
| **Direct issuance** | **-$3.42M** | **-$34.18** | **$12.92M** | **30 months** | *Excluded* |

### Core Financial Findings

1. **Indistinguishable Partner Paths:** Program Manager ranks first, but leads Sponsor Bank by **$0.77M** — below the pre-declared **$1.50M** decisiveness threshold (`min_margin_advantage_over_next_best_usd`). The honest reading is that partner paths are economically indistinguishable, so the decision must hinge on non-financial strategic drivers (such as time-to-market).
2. **Capital Efficiency & Exposure:** Direct Issuance requires **$12.92M** in balance sheet capital exposure ($340 avg balance × 100k cards × 38% revolve rate) to earn interest income, whereas Partner paths require **$0** capital balance.
3. **Volume Inflection Thresholds:**
   - **Contribution Floor:** Direct Issuance clears the `$2.50M` annual contribution floor at **$702/mo** spend per card (assuming time-to-market constraints are relaxed).
   - **Crossover Inflection:** Direct Issuance overtakes Program Manager in annual contribution at **$1,430/mo** spend per card due to capturing 100% of interchange revenue.

---

## Command Line Tools & Execution

Run the interactive comparative model:
```bash
python -m card_economics.compare
```

Run unit test suite:
```bash
pytest card_economics
```

To test alternative economic assumptions, edit parameters directly in [`assumptions.yaml`](./assumptions.yaml) and re-run.

---

## Where the LLM Sits

The language model operates purely as an explanation layer:

$$\text{Pre-computed Results} \longrightarrow \text{LLM Narrator (\texttt{shared/narrator.py})} \longrightarrow \text{Executive Memo}$$

The model receives structured, pre-calculated figures and never computes financial formulas. When running without an API key, `compare.py` falls back deterministically to `write_memo_fallback()`.
