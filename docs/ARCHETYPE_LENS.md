# Archetype Lens

Color-pair-aware scoring for the Draft Advisor. It's on by default and can be
turned off in **File → Preferences → Archetype Lens (color-pair aware picks)**.
With it off, the advisor scores exactly as upstream does.

Code: `src/advisor/archetype_lens.py`, wired into `src/advisor/engine.py`
through `DraftAdvisor(..., lens_factory=...)`.

## Backtest results (FRA, Nov 2026)

Replaying 2,000 17Lands Premier drafts (salt `check2`), top-1 agreement with
drafters vs the plain advisor, and the regret/event-wins slope (more negative
is better):

| variant | top-1 | regret change |
|---|---|---|
| all three pieces | +0.2 (SE 0.1) | -0.007 (SE 0.006) |
| #1 only (the default) | +0.2 | -0.008 |
| no #1 | -0.7 | +0.002 |
| #3 only | -0.9 | +0.004 |

So #1 carries the gain and #2/#3 add nothing measurable; they are off by
default (`ArchetypeLens.DEFAULT_DISABLED`) and the code stays for further
experiments. The same +0.2 replicated on an independent 1,000-draft sample.

## What it adds

### 1. Lane probabilities and archetype overperformers

Upstream blends in a card's win rate for one archetype, and only after the
pool has settled on two colors. The lens keeps a probability for each of the
ten color pairs from the first pick:

- every non-land card in your pool adds strength to each pair it's castable in
  (more for stronger cards), tipped slightly by how much better it does in
  that pair;
- each pair's overall deck win rate from 17Lands adds a small prior;
- a softmax turns strengths into probabilities, flat early and sharp by
  about pick 15.

A card's archetype credit is its GIH WR gain in each pair it can be cast in,
weighted by those probabilities. Gains are shrunk toward zero by sample size
(a gain measured over 400 games counts half), and credit is reduced for cards
whose castable pairs are unlikely, so an off-lane gold card isn't inflated.
The reason column shows `Better in UB (+6.2)` when this moves a card by 5+
points.

### 2. Archetype sheet (key cards and themes) — off by default

For each pair, the sheet lists the cards that overperform there most (at least
200 games and +1.0 shrunk win-rate points) and the card tags most
over-represented among them. A key card for one of your three likeliest lanes
gets up to +12% (scaled by lane probability and how big its gain is), shrinking
to nothing once you hold four key cards for that lane. A card carrying one of
the lane's themes gets up to +5% once your pool has two or more cards with that
tag.

The sheet is built automatically when a set loads. To see or edit it:

```sh
python Tools/archetype_sheet.py --dataset Sets/<your dataset>.json --set FRA
```

That writes `Sets/Archetypes/FRA.auto.json`. Copy it to `Sets/Archetypes/FRA.json`
and edit it: give pairs a `name`, add `key_cards` or `themes`, or set
`"replace": true` to use only your list for a pair. The app reads it the next
time the set loads.

Themes come from the Scryfall tags the app harvests (`removal`,
`token_maker`, `synergy_graveyard`, ...). If tags haven't been harvested for a
set, themes will be empty and only key cards apply.

### 3. Pack-1 lane flexibility — off by default

Through the first nine picks of pack 1, a card's score is nudged by how likely
it is to be castable in the lane you end up in, compared with the rest of the
pack: up to about ±10% at pick 1, fading to nothing by pick 10. Mono-color and
colorless cards that fit your likely lanes go up; gold cards outside them go
down. Cards nudged up by 3%+ show `Keeps Lanes Open`.

## Checking it helps

All the weights above are starting guesses. Before trusting them, replay real
drafts:

```sh
Tools/AdvisorReplay/lens_backtest.sh FRA 1000
```

This downloads 17Lands' public Premier Draft dump and the app's dataset for
the set, replays the same 1,000 drafts through the plain advisor (`base`) and
the lens (`head`), and writes `results/lens_FRA.md`. See
`Tools/AdvisorReplay/README.md` for what the numbers mean. In short:

- **top-1 / top-3**: how often the advisor's best pick matched what drafters
  took. Higher is better, especially for strong drafters.
- **regret vs event wins**: more negative means drafters who ignored the
  advisor won less, so the advisor knows something.

Treat a head-minus-base difference under about two standard errors as no
difference. `ABLATE=1 Tools/AdvisorReplay/lens_backtest.sh FRA 2000 check2` also replays
the lens with each piece switched off. To turn #2 or #3 back on in the app, edit
`DEFAULT_DISABLED` on `ArchetypeLens`. If a feature doesn't help, its weight is a class constant on
`ArchetypeLens` (`DELTA_TIP`, `MASS_FULL_CREDIT`, `KEY_BONUS_MAX`,
`THEME_BONUS_MAX`, `FLEX_WEIGHT`); set it to 0 to switch that piece off and
rerun. Confirm any tuning on a second sample with a new salt:
`Tools/AdvisorReplay/lens_backtest.sh FRA 1000 check2`.
