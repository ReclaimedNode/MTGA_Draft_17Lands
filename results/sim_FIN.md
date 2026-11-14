# Draft simulation: FIN

Seat 0 takes the advisor's top card in every pick of an eight-seat pod of real packs;
the other seats pick like 17Lands drafters. `base` is the plain advisor.

Win model (pair-adjusted), fit to 133,764 real decks: log-odds of a game = +0.87 x mean rating +1.27 x mean fit -0.80 x share off the pair + the pair's own term.
Win model (no pair terms), fit to 133,764 real decks: log-odds of a game = +0.73 x mean rating +1.28 x mean fit -0.84 x share off the pair.

## blend minus base (1000 pods)

Same 42 cards in 20% of pods; 7.7 cards differ on average; same deck colors in 73%.

| measure | base | blend | difference | SE |
|---|---|---|---|---|
| win rate (pair-adjusted) | 57.78 | 57.74 | -0.04 | 0.07 |
| event wins (pair-adjusted) | 3.704 | 3.699 | -0.005 | 0.008 |
| win rate, best build (pair-adjusted) | 58.43 | 58.42 | -0.01 | 0.07 |
| win rate (no pair terms) | 57.59 | 57.58 | -0.01 | 0.07 |
| event wins (no pair terms) | 3.681 | 3.680 | -0.001 | 0.008 |
| win rate, best build (no pair terms) | 58.12 | 58.15 | +0.02 | 0.06 |
| win rate (app deck score) | 60.48 | 60.51 | +0.03 | 0.04 |
| deck: mean rating (SDs) | 0.463 | 0.466 | +0.003 | 0.003 |
| deck: mean fit (SDs) | -0.031 | -0.032 | -0.001 | 0.002 |
| deck: spells off the pair (%) | 1.47 | 1.58 | +0.11 | 0.20 |

## value minus base (1000 pods)

Same 42 cards in 0% of pods; 21.1 cards differ on average; same deck colors in 26%.

| measure | base | value | difference | SE |
|---|---|---|---|---|
| win rate (pair-adjusted) | 57.78 | 60.26 | +2.48 | 0.12 |
| event wins (pair-adjusted) | 3.704 | 3.986 | +0.282 | 0.013 |
| win rate, best build (pair-adjusted) | 58.43 | 60.82 | +2.39 | 0.11 |
| win rate (no pair terms) | 57.59 | 59.97 | +2.38 | 0.11 |
| event wins (no pair terms) | 3.681 | 3.951 | +0.270 | 0.012 |
| win rate, best build (no pair terms) | 58.12 | 60.43 | +2.30 | 0.09 |
| win rate (app deck score) | 60.48 | 60.68 | +0.21 | 0.07 |
| deck: mean rating (SDs) | 0.463 | 0.477 | +0.014 | 0.004 |
| deck: mean fit (SDs) | -0.031 | 0.040 | +0.071 | 0.002 |
| deck: spells off the pair (%) | 1.47 | 1.78 | +0.31 | 0.30 |

