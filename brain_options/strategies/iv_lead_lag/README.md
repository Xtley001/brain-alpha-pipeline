# Cross-Asset Implied Volatility Leading Cash Equity Strategy

## 1. Academic & Economic Foundations
Informed traders with private information or superior analytical speed frequently trade equity options before trading the underlying cash equities due to embedded leverage, defined risk, and absence of short-sale borrow constraints. Bali & Hovakimian (2009) and Pan & Poteshman (2006) demonstrate that innovations in call vs. put implied volatility and option volume imbalances predict underlying cash equity returns over a 10 to 20-day forward window.

## 2. Mathematical Formulation
Let $\Delta \text{IV}_{\text{call}, 30, t}$ and $\Delta \text{IV}_{\text{put}, 30, t}$ be the 5-day changes in ATM call and put implied volatilities:

$$\text{IVSpreadSpread}_t = \Delta \text{IV}_{\text{call}, 30, t} - \Delta \text{IV}_{\text{put}, 30, t}$$

$$\alpha_{\text{IVLead}} = \text{group\_neutralize}\left(\text{IVSpreadSpread}_t, \text{subindustry}\right)$$

Furthermore, interacting with signed option order flow imbalance:
$$\alpha_{\text{OrderFlow}} = \text{group\_rank}\left(\text{ts\_decay\_linear}\left(\frac{\text{CallVol}_t - \text{PutVol}_t}{\text{StockVol}_t + 1}, 10\right), \text{industry}\right)$$

## 3. Academic Citations
* **Bali, T.G., & Hovakimian, A. (2009)**. *Volatility Spreads and Expected Stock Returns*. Management Science, 55(11), 1797-1812.
* **Pan, J., & Poteshman, A.M. (2006)**. *The Information in Option Volume for Future Stock Prices*. The Review of Financial Studies, 19(3), 871-908.
* **Garleanu, N., & Pedersen, L.H. (2011)**. *Margin Requirements and Asset Prices*. The Review of Financial Studies, 24(6), 1980-2010.
