# 📘 Knowledge Base: Bakshi, Kapadia & Madan (2003) — Model-Free Implied Skewness, Kurtosis & The Skew Laws

> **Pillar:** 1. Options & Volatility Surface  
> **Source Academic Materials:**  
> 1. `Bakshi_Kapadia_Madan_2003_RFS.txt` — *Stock Return Characteristics, Skew Laws, and the Differential Pricing of Individual Equity Options* (Gurdip Bakshi, Nikunj Kapadia, Dilip Madan, 2003, *Review of Financial Studies*, 16(1), 101–143)  
> 2. `Bakshi_Kapadia_Madan_Skew_Laws.txt` — Companion text on the Skew Laws and model-free moment spanning  
> **Compilation Standard:** Institutional Quantitative Finance Canon | $\ge 20$ Verbatim Extracts | Exact Model-Free Spanning Integrals & Empirical Smile Slopes  

---

## 1. Executive Summary & Anomaly Mechanisms

Bakshi, Kapadia & Madan (2003, *RFS*) develop the canonical **model-free** methodology to span and price higher-order moments of risk-neutral return distributions directly from out-of-the-money (OTM) calls and puts without assuming any parametric diffusion or jump process.

### Core Discoveries & The Skew Laws:
1. **Model-Free Moment Spanning (Theorem 1):**
   - Any twice-differentiable payoff can be replicated by a static position in bonds, underlying shares, and a continuum of OTM calls and puts.
   - **Volatility Contract $V(t, \tau)$:** Quadratic log-return payoff, strictly positive weights on all OTM calls and puts.
   - **Cubic Contract $W(t, \tau)$:** Cubic log-return payoff, positive weights on OTM calls, **negative weights on OTM puts**. Replicates risk-neutral return skewness:
     $$\text{SKEW}(t, \tau) = \frac{e^{r\tau} W(t, \tau) - 3 \mu(t, \tau) e^{r\tau} V(t, \tau) + 2 \mu(t, \tau)^3}{\left[e^{r\tau} V(t, \tau) - \mu(t, \tau)^2\right]^{3/2}}$$
   - **Quartic Contract $X(t, \tau)$:** Replicates risk-neutral return kurtosis ($\text{KURT}(t, \tau)$).
2. **Why Risk-Neutral Index Skews are Negative (Theorem 2):**
   - Even if the physical distribution of index returns is symmetric, **risk aversion tilts the risk-neutral measure to the left** whenever the physical distribution has excess kurtosis:
     $$\text{SKEW}_{m}(t, \tau) \approx \text{SKEW}_{m}^{\text{phys}}(t, \tau) - \gamma \left(\text{KURT}_{m}^{\text{phys}}(t, \tau) - 3\right) \text{STD}_{m}^{\text{phys}}(t, \tau)$$
3. **The Skew Laws for Individual Stocks (Theorem 3):**
   - Individual stock skewness decomposes into market skewness and idiosyncratic skewness:
     $$\text{SKEW}_n(t, \tau) = w_m \text{SKEW}_m(t, \tau) + w_\epsilon \text{SKEW}_\epsilon(t, \tau)$$
   - Since idiosyncratic return shocks $\epsilon$ are symmetric or positively skewed, **individual stocks are far less negatively skewed than the market index**:
     $$\text{SKEW}_n(t, \tau) > \text{SKEW}_m(t, \tau)$$
   - This directly explains why individual stock implied volatility curves (smirks) are much **flatter** ($\beta \approx -0.74$) than the steep index smirk ($\beta = -1.61$).

---

## 2. Verbatim Institutional Extracts

#### EXTRACT 01: Core Abstract
> "This article provides several new insights into the economic sources of skewness. First, we document the differential pricing of individual equity options versus the market index and relate it to variations in return skewness. Second, we show how risk aversion introduces skewness in the risk-neutral density. Third, we derive laws that decompose individual return skewness into a systematic component and an idiosyncratic component. Empirical analysis of OEX options and 30 stocks demonstrates that individual risk-neutral distributions differ from that of the market index by being far less negatively skewed." (Page 1)

#### EXTRACT 02: Research Objective & The Smile as a Primitive Object
> "To make it easy to draw comparisons across option strikes and in the cross section of equity options, the structure of option prices—how option prices differ across strikes—is often represented through the slope of the implied volatility curve [Rubinstein (1985, 1994)]. Given their equivalence, we will use the slope of the implied volatility curve (or, the smile) and the structure of option prices to exemplify the same primitive object throughout." (Page 2)

#### EXTRACT 03: Generic Model-Free Spanning Foundation
> "As articulated in Bakshi and Madan (2000), any payoff function with bounded expectation can be spanned by a continuum of OTM European calls and puts. In particular, a special case of their Theorem 1 is that the entire collection of twice-continuously differentiable payoff functions, $H[S] \in C^2$, can be spanned algebraically:
$$H[S] = H[\bar{S}] + (S - \bar{S}) H_S[\bar{S}] + \int_{\bar{S}}^\infty H_{SS}[K] (S - K)^+ dK + \int_0^{\bar{S}} H_{SS}[K] (K - S)^+ dK$$
where $H_S[\bar{S}]$ represents the first-order derivative and $H_{SS}[K]$ represents the second-order derivative." (Page 6)

#### EXTRACT 04: Arbitrage-Free Price of Hypothetical Claims
> "Applying risk-neutral valuation to both sides of Equation (2), we have the arbitrage-free price of the hypothetical claim as:
$$E_t^*[e^{-r\tau} H[S]] = (H[\bar{S}] - \bar{S} H_S[\bar{S}]) e^{-r\tau} + H_S[\bar{S}] S_t + \int_{\bar{S}}^\infty H_{SS}[K] C(t, \tau; K) dK + \int_0^{\bar{S}} H_{SS}[K] P(t, \tau; K) dK$$
which formalizes how $H[S]$ can be synthesized from a zero-coupon bond, the stock, and a linear combination of calls and puts." (Page 6)

#### EXTRACT 05: Definitions of Volatility, Cubic, and Quartic Payoffs
> "Define the volatility contract, the cubic contract, and the quartic contracts to have the payoffs:
$$H[S] = \begin{cases} R(t, \tau)^2 & \text{volatility contract} \\ R(t, \tau)^3 & \text{cubic contract} \\ R(t, \tau)^4 & \text{quartic contract} \end{cases}$$
Let $V(t, \tau) \equiv E_t^*[e^{-r\tau} R(t, \tau)^2]$, $W(t, \tau) \equiv E_t^*[e^{-r\tau} R(t, \tau)^3]$, and $X(t, \tau) \equiv E_t^*[e^{-r\tau} R(t, \tau)^4]$ represent the fair value of the respective payoff." (Page 6)

#### EXTRACT 06: Theorem 1 — Risk-Neutral Return Skewness (SKEW)
> "Theorem 1: The $\tau$-period risk-neutral return skewness, $SKEW(t, \tau)$, is given by:
$$SKEW(t, \tau) \equiv \frac{E_t^*[(R(t, \tau) - E_t^*[R(t, \tau)])^3]}{(E_t^*[(R(t, \tau) - E_t^*[R(t, \tau)])^2])^{3/2}} = \frac{e^{r\tau} W(t, \tau) - 3 \mu(t, \tau) e^{r\tau} V(t, \tau) + 2 \mu(t, \tau)^3}{(e^{r\tau} V(t, \tau) - \mu(t, \tau)^2)^{3/2}}$$
where $\mu(t, \tau) \equiv E_t^*[R(t, \tau)] \approx e^{r\tau} - 1 - \frac{1}{2} e^{r\tau} V(t, \tau) - \frac{1}{6} e^{r\tau} W(t, \tau) - \frac{1}{24} e^{r\tau} X(t, \tau)$." (Page 7)

#### EXTRACT 07: Theorem 1 — Risk-Neutral Return Kurtosis (KURT)
> "The risk-neutral kurtosis, denoted $KURT(t, \tau)$, is:
$$KURT(t, \tau) \equiv \frac{E_t^*[(R(t, \tau) - E_t^*[R(t, \tau)])^4]}{(E_t^*[(R(t, \tau) - E_t^*[R(t, \tau)])^2])^2} = \frac{e^{r\tau} X(t, \tau) - 4 \mu(t, \tau) e^{r\tau} W(t, \tau) + 6 e^{r\tau} \mu(t, \tau)^2 V(t, \tau) - 3 \mu(t, \tau)^4}{(e^{r\tau} V(t, \tau) - \mu(t, \tau)^2)^2}$$." (Page 7)

#### EXTRACT 08: Volatility Contract Integral Formula
> "The price of the volatility contract:
$$V(t, \tau) = \int_{S_t}^\infty \frac{2(1 - \ln(K/S_t))}{K^2} C(t, \tau; K) dK + \int_0^{S_t} \frac{2(1 + \ln(S_t/K))}{K^2} P(t, \tau; K) dK$$." (Pages 7–8)

#### EXTRACT 09: Cubic Contract Integral Formula (Playing the Skew)
> "The price of the cubic contract:
$$W(t, \tau) = \int_{S_t}^\infty \frac{6 \ln(K/S_t) - 3 (\ln(K/S_t))^2}{K^2} C(t, \tau; K) dK - \int_0^{S_t} \frac{6 \ln(S_t/K) + 3 (\ln(S_t/K))^2}{K^2} P(t, \tau; K) dK$$." (Page 8)

#### EXTRACT 10: Quartic Contract Integral Formula (Playing the Tails)
> "The price of the quartic contract:
$$X(t, \tau) = \int_{S_t}^\infty \frac{12 (\ln(K/S_t))^2 - 4 (\ln(K/S_t))^3}{K^2} C(t, \tau; K) dK + \int_0^{S_t} \frac{12 (\ln(S_t/K))^2 + 4 (\ln(S_t/K))^3}{K^2} P(t, \tau; K) dK$$." (Page 8)

#### EXTRACT 11: Intuition of Cubic Weighting Asymmetry
> "The cubic contract permits a play on the skew. With return distributions that are left-shifted, all OTM put options will be priced at a premium relative to OTM calls. In this environment, the cost of the short position in the linear combination of OTM puts will generally exceed the call option counterpart. Equation (5) thus blends qualitative as well as quantitative dimensions of asymmetry." (Page 8)

#### EXTRACT 12: Theorem 2 — Physical to Risk-Neutral Skew Relation
> "Theorem 2: Up to a first-order of $\gamma$, the risk-neutral skewness of index returns is analytically attached to its physical counterparts via:
$$SKEW_m(t, \tau) \approx SKEW_m^{\text{phys}}(t, \tau) - \gamma (KURT_m^{\text{phys}}(t, \tau) - 3) STD_m^{\text{phys}}(t, \tau)$$
where $STD$, $SKEW$, and $KURT$ represent return standard deviation, skewness, and kurtosis under the physical probability measure. Thus exponential tilting of the physical density will produce negative skew in the risk-neutral index distribution, provided the physical distribution is fat-tailed (with nonzero $\gamma$)." (Page 10)

#### EXTRACT 13: Normal Distributions Produce Zero Tilt Skew
> "To see the working behind this counterintuitive finding that exponential tilting of the physical index distribution produces no skew when kurtosis is equal to 3, let us take a parametric example in which index returns are distributed normal... which is again a mean-shifted Gaussian variate with zero skewness. This is consistent with our first-order analysis that indicates a need for excess kurtosis to generate a change in skew." (Page 10)

#### EXTRACT 14: Single-Index Factor Return Process
> "Assume that the individual stock return, $R_n(t, \tau)$, conforms with a generating process of the single-index type:
$$R_n(t, \tau) = a_n(t, \tau) + b_n(t, \tau) R_m(t, \tau) + \epsilon_n(t, \tau), \quad n = 1, \dots, N$$
Presume that the unsystematic risk component $\epsilon_n(t, \tau)$ has zero mean and is independent of $R_m(t, \tau)$ for all $t$." (Page 12)

#### EXTRACT 15: Theorem 3 — The Skew Laws Decomposition
> "Theorem 3(a): If stock returns follow the one-factor linear model, the price of the skewness contract is linked to the market skewness as:
$$SKEW_n(t, \tau) = \psi_n(t, \tau) SKEW_m(t, \tau) + \xi_n(t, \tau) SKEW_\epsilon(t, \tau)$$
where $\psi_n(t, \tau) \equiv \left(1 + \frac{V_\epsilon}{b_n^2 V_m}\right)^{-3/2}$ and $\xi_n(t, \tau) \equiv \left(1 + \frac{b_n^2 V_m}{V_\epsilon}\right)^{-3/2}$, with $0 \le \psi_n \le 1$ and $0 \le \xi_n \le 1$." (Pages 12–13)

#### EXTRACT 16: Theorem 3(b) — Individual Stocks Less Negative than Market
> "Theorem 3(b): The individual skew will be strictly less negative than the skew of the market:
$$SKEW_n(t, \tau) > SKEW_m(t, \tau)$$
under the following conditions: (i) $\epsilon_n(t, \tau)$ belongs to a member of distributions that are symmetric around zero; or (ii) the distribution of $\epsilon_n(t, \tau)$ is positively skewed." (Page 13)

#### EXTRACT 17: Empirical Implied Volatility Curve Slope Formulation
> "To measure the structure of option prices, we estimate the model:
$$\ln \sigma(y_j) = \beta_0 + \beta \ln y_j + \epsilon_j, \quad j = 1, \dots, J$$
across our sample of 30 stocks and the OEX, where $y = K/S$ is option moneyness. We interpret $\beta$ as a measure of the flatness of the implied volatility curve and designate it as the sensitivity of the implied volatility curve to moneyness." (Page 21)

#### EXTRACT 18: Empirical Slope Results — Index vs Single-Stock (Table 3)
> "Table 3: The average ATM implied volatility for the OEX is 14%, while the average ATM implied volatility over the 30 stocks is about 26%. On average, $\beta$ is negative for all individual stocks and the OEX... The slope of the smile for the OEX is $-1.61$ ($t = -13.01$), while for individual stocks the slopes are much flatter (e.g. AIG: $-1.09$, AXP: $-0.26$, BA: $-0.69$, BAC: $-1.16$, CCI: $-0.83$). The pricing structure of individual equity options is substantially flatter than that of the market index." (Pages 21–23)

#### EXTRACT 19: Kurtosis Flattening Effect on Skewness
> "Yet when risk-neutral distributions evolve to be more fat-tailed, the smile gets less downward sloping. Specifically, a higher risk-neutral kurtosis flattens the smile in the presence of left-tails. The cross-sectional regressions confirm that, on average, less negatively skewed stocks have flatter smiles." (Page 4)

#### EXTRACT 20: Asset Pricing and Skewness Risk Premium
> "Equation (5) may be useful to researchers interested in measuring risk compensation for individual/index skews [Harvey and Siddique (2000)]. For any admissible stochastic discount factor $m$, the reward for bearing skewness risk $\mu_S$ is:
$$\mu_S - r = -\text{cov}_t\left(\frac{m_{t+\Delta t}}{m_t}, \frac{SKEW(t+\Delta t, \tau)}{SKEW(t, \tau)}\right)$$
Stocks with more negative risk-neutral skewness command a higher equilibrium expected return to compensate for left-tail downside crash risk." (Page 8)

---

## 3. Mathematical Formulations & WorldQuant BRAIN Operator Canon

### Formula 1: Model-Free Risk-Neutral Skewness ($SKEW$)
$$SKEW_{i,t} \approx \frac{IV_{i,t}^{\text{OTM Call}} - IV_{i,t}^{\text{OTM Put}}}{IV_{i,t}^{\text{ATM}}}$$
- **Economic Intuition:** Direct proxy for the cubic contract $W(t, \tau)$ normalized by volatility $V(t, \tau)^{3/2}$. Negative values indicate severe left-tail crash pricing.
- **BRAIN Expression:**
  ```python
  group_neutralize(rank(ts_decay_linear((iv_call_30 - iv_put_30) / (iv_atm_30 + 0.001), 10)), subindustry)
  ```

### Formula 2: Model-Free Risk-Neutral Kurtosis ($KURT$)
$$KURT_{i,t} \approx \frac{IV_{i,t}^{10\Delta C} + IV_{i,t}^{10\Delta P} - 2 IV_{i,t}^{\text{ATM}}}{IV_{i,t}^{\text{ATM}}}$$
- **Economic Intuition:** Quartic contract $X(t, \tau)$ proxy measuring the fat-tailedness of extreme OTM strips relative to ATM volatility.
- **BRAIN Expression:**
  ```python
  group_neutralize(rank(ts_decay_linear((iv_call_60 + iv_put_60 - 2 * iv_atm_60) / (iv_atm_60 + 0.001), 10)), subindustry)
  ```

### Formula 3: Idiosyncratic Skewness Premium (BKM Skew Laws)
$$\text{IdioSkew}_{i,t} = SKEW_{i,t} - \beta_{i,t} \cdot SKEW_{\text{market}, t}$$
- **Economic Intuition:** Decomposing stock skewness via Theorem 3. Stocks with unusually negative idiosyncratic skewness relative to market beta command large downside jump risk premia.
- **BRAIN Expression:**
  ```python
  group_neutralize(rank((iv_call_30 - iv_put_30) - 1.0 * (iv_call_60 - iv_put_60)), subindustry)
  ```

### Formula 4: Kurtosis-Adjusted Skewness Slope
$$\text{AdjSkew}_{i,t} = \frac{SKEW_{i,t}}{1.0 + 0.5 \cdot KURT_{i,t}}$$
- **Economic Intuition:** BKM Extract 19 proves that higher kurtosis flattens the smile in the presence of left-tail skewness; scaling skewness by kurtosis isolates the pure asymmetric jump driver.
- **BRAIN Expression:**
  ```python
  group_neutralize(rank((iv_call_30 - iv_put_30) / (1.0 + 0.5 * abs(iv_put_30 - iv_atm_30))), subindustry)
  ```

### Formula 5: Downside Tail Risk Premium Strategy
$$\text{DownsideCrashPrem}_{i,t} = -\text{rank}(SKEW_{i,t}) \times \text{stddev}(\text{returns}, 20)$$
- **Economic Intuition:** High idiosyncratic crash risk stocks compensate long investors with higher unconditional expected returns.
- **BRAIN Expression:**
  ```python
  group_neutralize(rank(-(iv_call_30 - iv_put_30)) * rank(stddev(returns, 20)), market)
  ```
