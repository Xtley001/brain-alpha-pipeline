# Category: Options Derivatives & Volatility Surface (`option8` / `option9`)

**WorldQuant BRAIN Category ID:** `option`  
**Platform Value Score:** **`6.0 / 10`**  
**Platform User Count:** **40,512 Users**  
**Total Platform Alphas:** **370,149 Alphas**

---

## 1. Strategy Archetypes & Theoretical Foundations

### Archetype O1: Put Breakeven Asymmetric Floors
* **Citation:** Bali & Hovakimian; Sinclair (2010) — *Volatility Trading*
* **Core Fields:** `put_breakeven_60`, `forward_price_60`, `implied_volatility_mean_skew_60`
* **Economic Thesis:** Deep downside put breakeven levels act as institutional support floors. Contraction of put distance relative to spot predicts durable upward price drift.
* **Base Formula:**
  $$\alpha = \text{group\_neutralize}\left(\text{rank}\left(\text{ts\_decay\_linear}\left(\frac{\text{forward\_price}_{60} - \text{put\_breakeven}_{60}}{\text{close}}, 12\right)\right), \text{subindustry}\right)$$

---

### Archetype O2: Volatility Smirk & Skew Slope
* **Citation:** Xing, Zhang, & Zhao (2010) — *What Does the Volatility Smile Tell Us About Future Stock Returns?*
* **Core Fields:** `implied_volatility_put_60`, `implied_volatility_call_60`, `implied_volatility_mean_60`
* **Economic Thesis:** Steepness of the out-of-the-money put volatility smirk reflects institutional demand for crash insurance. Fading overextended smirk monetizes tail risk premia.
* **Base Formula:**
  $$\alpha = \text{group\_neutralize}\left(\text{rank}\left(-\text{ts\_decay\_linear}\left(\frac{\text{implied\_volatility\_put}_{60} - \text{implied\_volatility\_call}_{60}}{\text{implied\_volatility\_mean}_{60} + 0.001} \cdot \sqrt{\frac{60}{252}}, 10\right)\right), \text{subindustry}\right)$$

---

### Archetype O3: Variance Risk Premium (VRP) & Term Structure
* **Citation:** Bollerslev, Tauchen, & Zhou (2009); Carr & Wu (2009)
* **Core Fields:** `implied_volatility_mean_180`, `implied_volatility_mean_30`, `returns`
* **Economic Thesis:** The spread between implied volatility and realized volatility (or long vs. short tenor IV) compensates for unhedgeable variance risk.
* **Base Formula:**
  $$\alpha = \text{group\_neutralize}\left(\text{rank}\left(\text{ts\_decay\_linear}(\text{implied\_volatility\_mean}_{180} - \text{implied\_volatility\_mean}_{30}, 15)\right), \text{subindustry}\right)$$

---

## 2. Implementation Rules
1. **Double Decay Smoothing:** Always wrap in `ts_decay_linear(..., 10-15)` to maintain turnover $< 15\%$.
2. **Neutralization:** Strictly `subindustry` to guarantee zero `LOW_SUB_UNIVERSE_SHARPE` fails.
3. **Universes:** Primary execution on `TOP3000` and `TOP2000`.
