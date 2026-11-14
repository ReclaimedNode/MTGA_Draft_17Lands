# Draft simulation: TLA

Seat 0 takes the advisor's top card in every pick of an eight-seat pod of real packs;
the other seats pick like 17Lands drafters. `base` is the plain advisor.

Win model (pair-adjusted), fit to 97,446 real decks: log-odds of a game = +0.87 x mean rating +1.27 x mean fit -0.57 x share off the pair + the pair's own term.
Win model (no pair terms), fit to 97,446 real decks: log-odds of a game = +0.70 x mean rating +1.14 x mean fit -0.61 x share off the pair.

## blend minus base (1000 pods)

Same 42 cards in 23% of pods; 6.3 cards differ on average; same deck colors in 78%.

| measure | base | blend | difference | SE |
|---|---|---|---|---|
| win rate (pair-adjusted) | 59.63 | 59.61 | -0.03 | 0.05 |
| event wins (pair-adjusted) | 3.913 | 3.910 | -0.003 | 0.006 |
| win rate, best build (pair-adjusted) | 60.19 | 60.19 | -0.00 | 0.05 |
| win rate (no pair terms) | 59.44 | 59.46 | +0.01 | 0.05 |
| event wins (no pair terms) | 3.890 | 3.891 | +0.001 | 0.005 |
| win rate, best build (no pair terms) | 59.87 | 59.89 | +0.02 | 0.04 |
| win rate (app deck score) | 58.16 | 58.23 | +0.07 | 0.03 |
| deck: mean rating (SDs) | 0.294 | 0.298 | +0.004 | 0.002 |
| deck: mean fit (SDs) | 0.018 | 0.016 | -0.002 | 0.001 |
| deck: spells off the pair (%) | 0.33 | 0.31 | -0.02 | 0.08 |

## value minus base (1000 pods)

Same 42 cards in 0% of pods; 19.3 cards differ on average; same deck colors in 32%.

| measure | base | value | difference | SE |
|---|---|---|---|---|
| win rate (pair-adjusted) | 59.63 | 61.37 | +1.74 | 0.09 |
| event wins (pair-adjusted) | 3.913 | 4.113 | +0.200 | 0.010 |
| win rate, best build (pair-adjusted) | 60.19 | 61.70 | +1.50 | 0.08 |
| win rate (no pair terms) | 59.44 | 60.77 | +1.33 | 0.08 |
| event wins (no pair terms) | 3.890 | 4.043 | +0.153 | 0.009 |
| win rate, best build (no pair terms) | 59.87 | 61.05 | +1.17 | 0.07 |
| win rate (app deck score) | 58.16 | 58.27 | +0.11 | 0.06 |
| deck: mean rating (SDs) | 0.294 | 0.303 | +0.010 | 0.004 |
| deck: mean fit (SDs) | 0.018 | 0.063 | +0.045 | 0.002 |
| deck: spells off the pair (%) | 0.33 | 0.65 | +0.31 | 0.16 |

