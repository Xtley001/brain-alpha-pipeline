# Accounting Quality, Sloan Cash Flow Divergence & Accruals Anomaly

## 1. Academic & Economic Foundations
The accrual anomaly is one of the most robust and persistent market anomalies in empirical finance. Formulated initially by Richard Sloan (1996), it documents that the accrual component of earnings exhibits much lower persistence than the cash flow component. Investors consistently overprice the accrual component and underprice operating cash flows, leading to predictable subsequent return reversals as lower-quality earnings revert.

## 2. Mathematical Formulation
Total accounting accruals ($TA$) are defined as net income minus operating cash flows, scaled by total assets:

$$TA_t = \frac{\text{NetIncome}_t - \text{OperatingCashFlow}_t}{\text{TotalAssets}_t}$$

The fundamental Sloan Alpha is synthesized as:
$$\alpha_{\text{Sloan}} = \text{rank}\left(\frac{\text{OperatingCashFlow}_t}{\text{TotalAssets}_t}\right) - \text{rank}\left(\frac{\text{NetIncome}_t}{\text{TotalAssets}_t}\right)$$

When normalized across subindustries to control for varying capital structures:
$$\alpha_{\text{AccrualNeutral}} = \text{group\_neutralize}\left(\alpha_{\text{Sloan}}, \text{subindustry}\right)$$

## 3. Academic Citations
* **Sloan, R.G. (1996)**. *Do Stock Prices Fully Reflect Information in Accruals and Cash Flows about Future Earnings?* The Accounting Review, 71(3), 289-315.
* **Fabozzi, F.J. (2007)**. *Quantitative Equity Investing: Techniques and Strategies*. John Wiley & Sons.
* **Grinold, R.C., & Kahn, R.N. (1999)**. *Active Portfolio Management: A Quantitative Approach for Producing Superior Returns and Controlling Risk*. McGraw-Hill.
