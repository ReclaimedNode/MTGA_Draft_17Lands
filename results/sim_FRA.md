# Draft simulation: FRA

Seat 0 takes the advisor's top card in every pick of an eight-seat pod of real packs;
the other seats pick like 17Lands drafters. `base` is the plain advisor.

Win model (pair-adjusted), fit to 53,744 real decks: log-odds of a game = +0.95 x mean rating +1.62 x mean fit -0.77 x share off the pair + the pair's own term.
Win model (no pair terms), fit to 53,744 real decks: log-odds of a game = +0.57 x mean rating +1.33 x mean fit -0.66 x share off the pair.

## blend minus base (2000 pods)

Same 42 cards in 18% of pods; 6.8 cards differ on average; same deck colors in 74%.

| measure | base | blend | difference | SE |
|---|---|---|---|---|
| win rate (pair-adjusted) | 57.25 | 57.07 | -0.19 | 0.06 |
| event wins (pair-adjusted) | 3.646 | 3.626 | -0.020 | 0.006 |
| win rate, best build (pair-adjusted) | 57.98 | 57.87 | -0.11 | 0.05 |
| win rate (no pair terms) | 57.49 | 57.39 | -0.10 | 0.04 |
| event wins (no pair terms) | 3.669 | 3.658 | -0.011 | 0.005 |
| win rate, best build (no pair terms) | 57.95 | 57.88 | -0.07 | 0.03 |
| win rate (app deck score) | 59.85 | 59.95 | +0.10 | 0.02 |
| deck: mean rating (SDs) | 0.410 | 0.416 | +0.006 | 0.002 |
| deck: mean fit (SDs) | -0.020 | -0.026 | -0.006 | 0.001 |
| deck: spells off the pair (%) | 0.62 | 0.57 | -0.05 | 0.09 |

## value minus base (2000 pods)

Same 42 cards in 0% of pods; 18.3 cards differ on average; same deck colors in 38%.

| measure | base | value | difference | SE |
|---|---|---|---|---|
| win rate (pair-adjusted) | 57.25 | 59.93 | +2.68 | 0.09 |
| event wins (pair-adjusted) | 3.646 | 3.949 | +0.303 | 0.010 |
| win rate, best build (pair-adjusted) | 57.98 | 60.23 | +2.25 | 0.07 |
| win rate (no pair terms) | 57.49 | 59.52 | +2.02 | 0.06 |
| event wins (no pair terms) | 3.669 | 3.897 | +0.228 | 0.007 |
| win rate, best build (no pair terms) | 57.95 | 59.69 | +1.74 | 0.05 |
| win rate (app deck score) | 59.85 | 59.91 | +0.06 | 0.04 |
| deck: mean rating (SDs) | 0.410 | 0.412 | +0.002 | 0.003 |
| deck: mean fit (SDs) | -0.020 | 0.041 | +0.061 | 0.002 |
| deck: spells off the pair (%) | 0.62 | 0.41 | -0.21 | 0.11 |

