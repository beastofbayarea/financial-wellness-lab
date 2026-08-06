# EWA simulator — planned

**Question:** how does portfolio margin move as advance limits rise?

Not built yet. This directory contains only this scope note and package marker;
there is no simulation API, command, data generator, or test suite today.

**Proposed core loop.** Synthetic paycheck and spending series per user →
advance requests → repayment simulation including partial repayment → margin
across optional delivery fees and defaults.

**Proposed explanation boundary.** Any future language model would stay outside
the simulation itself: it could describe reviewed persona parameters or write a
cohort summary from computed results. The simulation would remain deterministic
given a seed. Generated parameters would need explicit validation before use.

**The known weakness,** stated up front: recovering structure I deliberately put into the synthetic data is not a finding. The simulator would be useful for *sensitivity*, how outcomes move as limits change, and not for *levels*.
