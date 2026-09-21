# Strategy Module: Analyst Consensus Revisions & PEAD

## Theoretical Edge
Sell-side equity analysts adjust earnings forecasts slowly due to cognitive anchoring, institutional friction, and reputational risk. Consequently, when consensus revisions turn sharply positive, earnings and price drift persist for 30 to 60 trading days. Furthermore, wide analyst disagreement reflects high uncertainty; under short-sale constraints, high-dispersion stocks become overpriced and underperform.

## Optimal Execution Parameters
* **Universes:** `TOPSP500`, `TOP500`, `TOP1000`
* **Holding Decays:** 18 to 30 Days
* **Neutralizations:** `SUBINDUSTRY`, `SECTOR`, `INDUSTRY`
