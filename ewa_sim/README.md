# EWA simulator — planned

**Question:** how does portfolio margin move as advance limits rise?

Not built yet. Sketch of the intended shape, kept here so the repo is honest about what exists.

**Core loop.** Synthetic paycheck and spending series per user → advance requests → repayment simulation including partial repayment → margin across turbo fees and defaults.

**Where the LLM would sit.** Two places, both away from the simulation itself: generating persona parameters to give the synthetic population realistic cash-flow variety, and writing the cohort summary once results exist. The simulation stays deterministic given a seed.

**The known weakness,** stated up front: recovering structure I deliberately put into the synthetic data is not a finding. The simulator would be useful for *sensitivity*, how outcomes move as limits change, and not for *levels*.
