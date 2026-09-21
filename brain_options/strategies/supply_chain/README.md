# Supply Chain Shock Propagation & Customer-Supplier Lead-Lag Strategy

## 1. Academic & Economic Foundations
Modern industrial firms operate within tightly coupled input-output production networks. Idiosyncratic shocks (disruptions, natural disasters, input price spikes, or earnings surprises) originating in upstream supplier firms propagate downstream to customer firms with measurable time delays (5 to 20 trading days), primarily due to investor inattention and delayed customer supply renegotiations.

## 2. Mathematical Formulation
Let firm $i$ belong to supplier industry $I_{sup}$ and firm $j$ belong to customer industry $I_{cust}$. The cross-industry delayed momentum signal is formalized as:

$$\alpha_{j,t} = \text{ts\_delay}\left(\frac{1}{|I_{sup}|} \sum_{k \in I_{sup}} R_{k,t}, \Delta t\right) - R_{j,t}$$

When combined with inventory flow bottlenecks:
$$\alpha_{\text{bottleneck}} = -\text{rank}\left(\text{ts\_decay\_linear}(\text{InventoryTurnover}_t - \text{ts\_delay}(\text{InventoryTurnover}_t, 20), 10)\right)$$

## 3. Academic Citations
* **Barrot, J.N., & Sauvagnat, J. (2016)**. *Input Specificity and the Propagation of Idiosyncratic Shocks in Production Networks*. Quarterly Journal of Economics, 131(3), 1543-1585.
* **Cohen, L., & Frazzini, A. (2008)**. *Economic Links and Predictable Returns*. The Journal of Finance, 63(4), 1977-2011.
* **Menzies et al. (2020)**. *Economically Linked Firms and Cross-Industry Lead-Lag Predictability*. Institutional Quantitative Working Paper Series.
