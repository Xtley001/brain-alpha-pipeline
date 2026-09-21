# Strategy Module: Put-Call Ratio & Order Flow Imbalances

## Theoretical Edge
Institutional option market participants possess superior private information and trade aggressively in out-of-the-money put and call options prior to major corporate announcements and macro shifts. Unusual spikes in trading volume relative to existing open interest stocks extract liquidity concessions from dealers, providing high-conviction directional price discovery.

## Key Formulation: Pan-Poteshman Flow Velocity
$$\text{InformedFlow}_t = \text{ts\_decay\_linear}\left( -\frac{\text{pcr\_vol}_t}{\text{pcr\_oi}_t + 0.001}, 5 \right)$$
Conditioned on underlying equity liquidity: $\text{volume} > \text{adv20}$.

## Optimal Execution Parameters
* **Universes:** `TOP2000`, `TOP3000`, `TOP1000`
* **Holding Decays:** 18 to 25 Days
* **Neutralizations:** `SUBINDUSTRY`, `SECTOR`, `MARKET`
