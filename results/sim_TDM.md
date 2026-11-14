# Draft simulation: TDM

Seat 0 takes the advisor's top card in every pick of an eight-seat pod of real packs;
the other seats pick like 17Lands drafters. `base` is the plain advisor.

Win model (pair-adjusted), fit to 96,227 real decks: log-odds of a game = +0.81 x mean rating +1.00 x mean fit -0.26 x share off the pair + the pair's own term.
Win model (no pair terms), fit to 96,227 real decks: log-odds of a game = +0.52 x mean rating +0.81 x mean fit -0.38 x share off the pair.

## blend minus base (1000 pods)

Same 42 cards in 12% of pods; 7.1 cards differ on average; same deck colors in 75%.

| measure | base | blend | difference | SE |
|---|---|---|---|---|
| win rate (pair-adjusted) | 58.08 | 57.96 | -0.12 | 0.07 |
| event wins (pair-adjusted) | 3.736 | 3.722 | -0.013 | 0.007 |
| win rate, best build (pair-adjusted) | 59.44 | 59.35 | -0.09 | 0.05 |
| win rate (no pair terms) | 58.78 | 58.61 | -0.18 | 0.05 |
| event wins (no pair terms) | 3.813 | 3.794 | -0.020 | 0.005 |
| win rate, best build (no pair terms) | 59.40 | 59.25 | -0.15 | 0.04 |
| win rate (app deck score) | 58.55 | 58.51 | -0.04 | 0.03 |
| deck: mean rating (SDs) | 0.325 | 0.327 | +0.002 | 0.002 |
| deck: mean fit (SDs) | -0.005 | -0.012 | -0.008 | 0.002 |
| deck: spells off the pair (%) | 2.04 | 2.60 | +0.56 | 0.19 |

## value minus base (1000 pods)

Same 42 cards in 0% of pods; 18.1 cards differ on average; same deck colors in 31%.

| measure | base | value | difference | SE |
|---|---|---|---|---|
| win rate (pair-adjusted) | 58.08 | 59.99 | +1.91 | 0.10 |
| event wins (pair-adjusted) | 3.736 | 3.954 | +0.219 | 0.012 |
| win rate, best build (pair-adjusted) | 59.44 | 60.93 | +1.50 | 0.08 |
| win rate (no pair terms) | 58.78 | 60.16 | +1.38 | 0.08 |
| event wins (no pair terms) | 3.813 | 3.972 | +0.158 | 0.009 |
| win rate, best build (no pair terms) | 59.40 | 60.58 | +1.18 | 0.06 |
| win rate (app deck score) | 58.55 | 59.10 | +0.55 | 0.05 |
| deck: mean rating (SDs) | 0.325 | 0.355 | +0.030 | 0.004 |
| deck: mean fit (SDs) | -0.005 | 0.048 | +0.053 | 0.003 |
| deck: spells off the pair (%) | 2.04 | 2.31 | +0.27 | 0.28 |

