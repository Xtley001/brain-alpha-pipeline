# Strategy Module: Volatility Skew & Smirk Asymmetry

## Theoretical Edge
Downside implied volatility skew measures the cost premium charged by option market makers for out-of-the-money put options compared to at-the-money calls. Institutional investors bid up put skew when possessing negative private information, hedging jump risk, or anticipating earnings shocks.

## Mathematical Formulation
* **Square-Root-Time Scaling:** Skew decays with $\sqrt{T}$. Scaling by $\sqrt{T/252}$ standardizes steepness across option expirations:
  $$\text{ScaledSkew}_t = \text{implied\_volatility\_mean\_skew}_t \times \sqrt{\frac{T}{252}}$$

## Optimal Execution Parameters
* **Universes:** `TOP1000`, `TOP2000`, `TOP3000`
* **Holding Decays:** 18 to 26 Days
* **Neutralizations:** `SUBINDUSTRY`, `SECTOR`
