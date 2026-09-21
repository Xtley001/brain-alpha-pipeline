# Network Graph Clustering & Co-Movement Lead-Lag Momentum Strategy

## 1. Academic & Economic Foundations
Financial markets exhibit complex community clustering architectures where assets in the same industrial or correlation cluster share underlying common risk factors. As formulated by Marcos Lopez de Prado (2018) in Hierarchical Risk Parity (HRP) and network clustering graph literature, asset returns can be decomposed into a cluster centroid component and an idiosyncratic residual component. Assets exhibiting short-term divergence from their cluster centroid provide high-Sharpe mean-reverting alpha, while the cluster centroid itself provides directional momentum.

## 2. Mathematical Formulation
Let $\mathcal{C}_k$ be the peer community cluster (subindustry/industry) for asset $i$:

$$\bar{R}_{\mathcal{C}_k, t} = \frac{1}{|\mathcal{C}_k|} \sum_{j \in \mathcal{C}_k} R_{j, t}$$

The lead-lag catch-up momentum signal is formulated as:
$$\alpha_{\text{ClusterCatchUp}} = \text{group\_rank}\left(\text{ts\_decay\_linear}(R_{i, t}, 20), \mathcal{C}_k\right) - \text{group\_rank}(R_{i, t}, \mathcal{C}_k)$$

When trading the mean-reverting idiosyncratic deviation:
$$\alpha_{\text{DevReversion}} = -\text{group\_neutralize}\left(R_{i, t} - \text{ts\_mean}(\bar{R}_{\mathcal{C}_k}, 20), \mathcal{C}_k\right)$$

## 3. Academic Citations
* **Lopez de Prado, M. (2018)**. *Advances in Financial Machine Learning*. John Wiley & Sons.
* **Lead-Lag Detection Network Clustering Research Papers**. Institutional Quantitative Finance & Network Topology.
* **Tulchinsky, I. (2019)**. *Finding Alphas: A Quantitative Approach to Building Trading Strategies*. WorldQuant.
