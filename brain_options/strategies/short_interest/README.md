# Strategy Module: Short Interest & Borrow Squeeze Dynamics

## Theoretical Edge
Aggregate short interest is widely documented as one of the strongest cross-sectional predictors of equity returns. When short demand surges against constrained lending supply (manifesting as elevated borrow fees), the stock suffers significant subsequent downward drift. Conversely, when highly shorted stocks experience sudden upward volume breakouts, trapped shorts are forced to cover, triggering sharp explosive rallies.

## Optimal Execution Parameters
* **Universes:** `TOP500`, `TOP1000`, `TOPSP500`
* **Holding Decays:** 16 to 24 Days
* **Neutralizations:** `SUBINDUSTRY`, `SECTOR`, `INDUSTRY`
