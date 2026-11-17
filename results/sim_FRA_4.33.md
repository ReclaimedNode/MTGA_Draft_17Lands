# Draft simulation: FRA

Seat 0 takes the advisor's top card in every pick of an eight-seat pod of real packs;
the other seats pick like 17Lands drafters. `base` is the plain advisor.

Win model (pair-adjusted), fit to 53,744 real decks: log-odds of a game = +0.95 x mean rating +1.62 x mean fit -0.77 x share off the pair + the pair's own term.
Win model (no pair terms), fit to 53,744 real decks: log-odds of a game = +0.57 x mean rating +1.33 x mean fit -0.66 x share off the pair.

## value minus base (2000 pods)

Same 42 cards in 0% of pods; 18.6 cards differ on average; same deck colors in 37%.

| measure | base | value | difference | SE |
|---|---|---|---|---|
| win rate (pair-adjusted) | 56.77 | 59.93 | +3.17 | 0.09 |
| event wins (pair-adjusted) | 3.593 | 3.949 | +0.356 | 0.010 |
| win rate, best build (pair-adjusted) | 57.65 | 60.23 | +2.58 | 0.07 |
| win rate (no pair terms) | 57.23 | 59.52 | +2.28 | 0.06 |
| event wins (no pair terms) | 3.640 | 3.897 | +0.257 | 0.007 |
| win rate, best build (no pair terms) | 57.73 | 59.69 | +1.96 | 0.05 |
| win rate (app deck score) | 59.61 | 59.91 | +0.30 | 0.04 |
| deck: mean rating (SDs) | 0.401 | 0.412 | +0.011 | 0.003 |
| deck: mean fit (SDs) | -0.020 | 0.041 | +0.061 | 0.001 |
| deck: spells off the pair (%) | 1.33 | 0.41 | -0.92 | 0.15 |

## plain advisor 4.32 minus base (2000 pods)

Same 42 cards in 13% of pods; 9.4 cards differ on average; same deck colors in 66%.

| measure | base | plain advisor 4.32 | difference | SE |
|---|---|---|---|---|
| win rate (pair-adjusted) | 56.77 | 57.25 | +0.48 | 0.06 |
| event wins (pair-adjusted) | 3.593 | 3.646 | +0.053 | 0.007 |
| win rate, best build (pair-adjusted) | 57.65 | 57.98 | +0.34 | 0.05 |
| win rate (no pair terms) | 57.23 | 57.49 | +0.26 | 0.05 |
| event wins (no pair terms) | 3.640 | 3.669 | +0.029 | 0.005 |
| win rate, best build (no pair terms) | 57.73 | 57.95 | +0.22 | 0.04 |
| win rate (app deck score) | 59.61 | 59.85 | +0.24 | 0.03 |
| deck: mean rating (SDs) | 0.401 | 0.410 | +0.009 | 0.002 |
| deck: mean fit (SDs) | -0.020 | -0.020 | +0.001 | 0.001 |
| deck: spells off the pair (%) | 1.33 | 0.62 | -0.71 | 0.13 |

