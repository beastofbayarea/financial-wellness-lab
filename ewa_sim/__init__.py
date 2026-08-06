"""Earned Wage Access (EWA) portfolio simulator — planned.

This package is reserved for future simulation capabilities that will model:
- Synthetic paycheck and spending series per user
- Advance request patterns and repayment behavior
- Portfolio margin sensitivity to advance limit changes
- Cohort-level outcomes across different user segments

Design principles (when implemented):
- **Deterministic given seed**: Simulations produce reproducible results
- **Sensitivity over levels**: Useful for understanding how outcomes change,
  not for predicting absolute performance without real data
- **Explanation boundary preserved**: Any LLM narration stays outside the
  simulation core, describing results rather than generating parameters

See :file:`ewa_sim/README.md` for the current scope and known limitations.
"""
