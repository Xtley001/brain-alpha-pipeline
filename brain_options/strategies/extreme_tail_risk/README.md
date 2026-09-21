# Extreme Tail Risk Asymmetry & OTM Put Jump Diffusion Strategy

## 1. Academic & Economic Foundations
The volatility smirk in individual equity options captures the market's pricing of negative jump risk. Under the Bakshi, Kapadia, & Madan (2003) framework, the difference in implied volatility between out-of-the-money puts and at-the-money calls directly measures higher-order moments (risk-neutral skewness and kurtosis). Xing, Zhang, & Zhao (2010) empirically prove that firms with the steepest smirks underperform those with flatter smirks by over 10% annualized, as sophisticated investors bid up protective puts ahead of negative firm-specific shocks.

## 2. Mathematical Formulation
Let $\text{IV}(\Delta=-0.25)$ be the implied volatility of a 25-delta put and $\text{IV}(\Delta=0.50)$ be the ATM call implied volatility:

$$\text{Smirk}_t = \text{IV}_{25\Delta put, t} - \text{IV}_{50\Delta call, t}$$

The normalized tail risk cross-sectional signal is:
$$\alpha_{\text{TailRisk}} = -\text{group\_neutralize}\left(\text{ts\_zscore}(\text{Smirk}_t, 60), \text{subindustry}\right)$$

Concurrently testing interaction with surface convexity:
$$\alpha_{\text{Convexity}} = -\text{group\_rank}(\text{SurfaceConvexity}_t, \text{industry})$$

## 3. Academic Citations
* **Bakshi, G., Kapadia, N., & Madan, D. (2003)**. *Stock Return Characteristics, Skew Laws, and the Differential Pricing of Individual Equity Options*. The Review of Financial Studies, 16(1), 101-143.
* **Xing, Y., Zhang, X., & Zhao, R. (2010)**. *What Does the Individual Option Volatility Smirk Tell Us About Future Equity Returns?* Journal of Financial and Quantitative Analysis, 45(3), 641-662.
* **Bennett, C. (2014)**. *Trading Volatility: Correlation, Term Structure and Skew*. CreateSpace Independent Publishing.
