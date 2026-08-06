# Card Economics Model

**Question:** Sponsor bank, program manager, or direct issuance — and what assumption would flip the answer?

---

## Design architecture and purpose

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

## Mathematical formulation

The financial engine evaluates each issuance model deterministically using the following arithmetic rules:

### 1. Revenue dynamics
- **Annual Spend ($)**: $\text{Active Cards} \times \text{Monthly Spend Per Card} \times 12$
- **Interchange Revenue ($)**: $\text{Annual Spend} \times \text{Interchange Rate}$
- **Revolving Balance ($)**: $\text{Active Cards} \times \text{Revolve Rate} \times \text{Avg Balance}$
- **Interest Revenue ($)**: $\text{Revolving Balance} \times \text{APR}$ *(Accrues ONLY if `owns_receivable = True`)*

### 2. Costs and balance-sheet exposure
- **Partner Fees ($)**: $\text{Interchange Revenue} \times \text{Partner Fee Share}$
- **Credit Losses ($)**: $\text{Revolving Balance} \times \text{Loss Rate}$ *(Borne ONLY if `owns_receivable = True`)*
- **Compliance Cost ($)**: $\text{Compliance Headcount} \times \text{Cost Per Head}$
- **Balance Sheet Exposure ($)**: $\text{Revolving Balance}$ *(reported only if `owns_receivable = True`)*

### 3. Net contribution and unit economics
- **Annual Contribution ($)**: $\text{Interchange} + \text{Interest} - \text{Partner Fees} - \text{Credit Losses} - \text{Fixed Costs} - \text{Compliance Costs}$
- **Contribution Per Card ($/Card/Yr)**: $\frac{\text{Annual Contribution}}{\text{Active Cards}}$
- **Return on Capital (%)**: $\frac{\text{Annual Contribution}}{\text{Balance Sheet Exposure}} \times 100$

---

## Default scenario results

These results come from the checked-in `assumptions.yaml`. They are a worked
example, not a forecast; see [`../LIMITATIONS.md`](../LIMITATIONS.md).

| Issuance Path | Annual Contribution | Unit Economics ($/Card/Yr) | Balance Sheet Exposure | Time-to-Market | Viability Status |
|---|---|---|---|---|---|
| **Program manager** | **$3.79M** | **$37.91** | **$0** | **6 months** | **Recommended** |
| **Sponsor bank** | **$3.02M** | **$30.20** | **$0** | **9 months** | Viable |
| **Direct issuance** | **-$3.42M** | **-$34.18** | **$12.92M** | **30 months** | *Excluded* |

### Core findings

1. **Indistinguishable Partner Paths:** Program Manager ranks first, but leads Sponsor Bank by **$0.77M** — below the pre-declared **$1.50M** decisiveness threshold (`min_margin_advantage_over_next_best_usd`). The honest reading is that partner paths are economically indistinguishable, so the decision must hinge on non-financial strategic drivers (such as time-to-market).
2. **Receivable ownership and exposure:** Direct issuance holds **$12.92M** of modeled revolving receivables ($340 average balance × 100k cards × 38% revolve rate), while partner paths report **$0** balance-sheet exposure. The model does not calculate regulatory capital requirements or funding costs.
3. **Volume Inflection Thresholds:**
   - **Contribution Floor:** Direct Issuance clears the `$2.50M` annual contribution floor at **$702/mo** spend per card (assuming time-to-market constraints are relaxed).
   - **Crossover Inflection:** Direct Issuance overtakes Program Manager in annual contribution at **$1,430/mo** spend per card due to capturing 100% of interchange revenue.

---

## Command-line use

Run the interactive comparative model:
```bash
python -m card_economics.compare
```

Run unit test suite:
```bash
python -m pytest card_economics
```

To test alternative economic assumptions, edit parameters directly in [`assumptions.yaml`](./assumptions.yaml) and re-run.

---

## Output contract

`compare()` returns all path results, the highest-contribution viable path,
the margin over the next viable path, a decisiveness flag and reason, and the
threshold failures for excluded paths. “Recommended” means highest annual
contribution among paths that clear every configured gate; it does not override
the separate decisiveness result.

`break_even_spend()` searches monthly spend from $1 to $5,000 for the point at
which a path clears the contribution floor. `find_crossover_spend()` searches
$1 to $10,000 for the point at which two paths have equal annual contribution.

## Where the LLM sits

The language model operates purely as an explanation layer:

$$\text{Pre-computed Results} \longrightarrow \text{LLM Narrator (\texttt{shared/narrator.py})} \longrightarrow \text{Executive Memo}$$

The Gemini model receives structured, pre-calculated figures and never computes
financial formulas. When Vertex AI configuration or credentials are
unavailable, `compare.py` falls back deterministically to
`write_memo_fallback()`.
