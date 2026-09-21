# Informed Short Demand vs. Loan Supply Friction Strategy

## 1. Academic & Economic Foundations
Traditional short interest metrics frequently conflate outward shifts in short seller demand with contractions in institutional share supply (e.g., custodian recall or float restrictions). Engelberg, Reed, & Ringgenberg (2012) and Cohen, Diether, & Malloy (2007) demonstrate that separating demand shifts from supply shifts generates significantly stronger, more persistent alpha: when borrow demand spikes concurrent with high utilization, stocks experience pronounced negative drift.

## 2. Mathematical Formulation
Let borrow demand shock $\Delta D_t$ be proxied by short rate of change, and supply friction $S_t$ be proxied by loan utilization and lendable inventory:

$$\Delta D_t = \text{ts\_delta}(\text{BorrowFee}_t, \Delta t) \times \text{ts\_decay\_linear}(\text{LoanUtilization}_t, 10)$$

$$\alpha_{\text{ShortDemand}} = -\text{group\_neutralize}\left(\Delta D_t, \text{subindustry}\right)$$

Stocks with maximum short demand acceleration under constrained lending pools exhibit the lowest forward return distributions.

## 3. Academic Citations
* **Engelberg, J.E., Reed, A.V., & Ringgenberg, M.C. (2012)**. *How are Shorts Informed? Short Sellers, News, and Information Processing*. Journal of Financial Economics, 105(2), 260-278.
* **Cohen, L., Diether, K.B., & Malloy, C.J. (2007)**. *Supply and Demand Shifts in the Shorting Market*. The Journal of Finance, 62(5), 2061-2096.
* **Rapach, D.E., Ringgenberg, M.C., & Zhou, G. (2016)**. *Short Interest and Aggregate Stock Returns*. Journal of Financial Economics, 121(1), 46-65.
