# Strategy Module: Volatility Term Structure & Variance Risk Premium (VRP)

## Theoretical Edge
Option implied volatility reflects the market's forward-looking risk assessment, but systematically overprices expected realized variance due to institutional demand for downside tail insurance. In addition, inversions of the implied volatility term structure ($IV_{30} > IV_{90}$) indicate temporary event panic that reliably mean-reverts.

## Academic & Institutional Pedigree
* **Carr & Wu (2009):** Synthetic variance swap replication shows variance risk premium is quadratic in implied volatility.
* **Sinclair (2013):** Mean-reverting volatility models enter optimal positions when standard deviations cross ~0.75 SD.
* **Bennett (2014):** Forward volatility notches isolate scheduled catalyst mispricings.

## Optimal Execution Parameters
* **Universes:** `TOP1000`, `TOP2000`, `TOP3000`
* **Holding Decays:** 16 to 24 Days (Low Turnover: 2.5% – 5.0%)
* **Neutralizations:** `SUBINDUSTRY`, `INDUSTRY`, `SECTOR`
