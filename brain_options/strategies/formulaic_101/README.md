# WorldQuant Classic Formulaic Alpha Synthesis Strategy

## 1. Academic & Economic Foundations
In 2015, Zura Kakushadze published the seminal paper *101 Formulaic Alphas*, unveiling quantitative expressions historically deployed by WorldQuant. These alphas rely on non-linear price-volume relationships, cross-sectional ranking operators, time-series decay functions, and liquidity interactions. Unlike traditional fundamental or static factor models, formulaic alphas exploit transient microstructural order imbalances, liquidity exhaustion, and geometric relative positioning.

## 2. Mathematical Formulation
Key representations from the canonical 101 formulas:

### Alpha #6 (Liquidity Exhaustion Reversal):
$$\alpha_{6} = -\text{group\_neutralize}\left(\text{rank}\left(\text{ts\_corr}(\text{open}, \text{volume}, 10)\right), \text{subindustry}\right)$$

### Alpha #41 (Geometric Range Skew):
$$\alpha_{41} = \text{group\_neutralize}\left(\text{rank}\left(\sqrt{\text{high} \times \text{low}} - \text{vwap}\right), \text{subindustry}\right)$$

### Alpha #54 (Volume-Weighted Extremes):
$$\alpha_{54} = -\text{group\_rank}(\text{ts\_rank}(\text{volume}, 20), \text{industry}) \times \text{group\_rank}(\text{ts\_delta}(\text{close}, 5), \text{industry})$$

## 3. Academic Citations
* **Kakushadze, Z. (2015)**. *101 Formulaic Alphas*. Wilmott Magazine, 2015(84), 84-90.
* **Tulchinsky, I. (2019)**. *Finding Alphas: A Quantitative Approach to Building Trading Strategies*. WorldQuant / John Wiley & Sons.
