# Draft simulation: SOS

Seat 0 takes the advisor's top card in every pick of an eight-seat pod of real packs;
the other seats pick like 17Lands drafters. `base` is the plain advisor.

Win model (pair-adjusted), fit to 101,848 real decks: log-odds of a game = +0.85 x mean rating +1.33 x mean fit -0.89 x share off the pair + the pair's own term.
Win model (no pair terms), fit to 101,848 real decks: log-odds of a game = +0.68 x mean rating +1.33 x mean fit -0.72 x share off the pair.

## blend minus base (1000 pods)

Same 42 cards in 29% of pods; 6.4 cards differ on average; same deck colors in 78%.

| measure | base | blend | difference | SE |
|---|---|---|---|---|
| win rate (pair-adjusted) | 57.19 | 57.17 | -0.02 | 0.07 |
| event wins (pair-adjusted) | 3.638 | 3.636 | -0.003 | 0.007 |
| win rate, best build (pair-adjusted) | 58.08 | 58.10 | +0.01 | 0.07 |
| win rate (no pair terms) | 57.09 | 57.08 | -0.01 | 0.07 |
| event wins (no pair terms) | 3.626 | 3.625 | -0.001 | 0.007 |
| win rate, best build (no pair terms) | 57.93 | 57.96 | +0.02 | 0.06 |
| win rate (app deck score) | 59.61 | 59.63 | +0.03 | 0.04 |
| deck: mean rating (SDs) | 0.416 | 0.418 | +0.002 | 0.003 |
| deck: mean fit (SDs) | -0.023 | -0.024 | -0.001 | 0.001 |
| deck: spells off the pair (%) | 2.91 | 3.03 | +0.11 | 0.23 |

## value minus base (1000 pods)

Same 42 cards in 0% of pods; 20.0 cards differ on average; same deck colors in 34%.

| measure | base | value | difference | SE |
|---|---|---|---|---|
| win rate (pair-adjusted) | 57.19 | 58.91 | +1.72 | 0.12 |
| event wins (pair-adjusted) | 3.638 | 3.833 | +0.195 | 0.014 |
| win rate, best build (pair-adjusted) | 58.08 | 59.91 | +1.83 | 0.11 |
| win rate (no pair terms) | 57.09 | 58.60 | +1.51 | 0.11 |
| event wins (no pair terms) | 3.626 | 3.796 | +0.170 | 0.012 |
| win rate, best build (no pair terms) | 57.93 | 59.42 | +1.49 | 0.09 |
| win rate (app deck score) | 59.61 | 59.87 | +0.27 | 0.06 |
| deck: mean rating (SDs) | 0.416 | 0.446 | +0.031 | 0.005 |
| deck: mean fit (SDs) | -0.023 | 0.022 | +0.045 | 0.002 |
| deck: spells off the pair (%) | 2.91 | 5.49 | +2.57 | 0.49 |

