# Archetype Lens

Color-pair-aware scoring for the Draft Advisor. It's on by default and can be
turned off in **File → Preferences → Archetype Lens (color-pair aware picks)**.
With it off, the advisor scores exactly as upstream does.

Code: `src/advisor/archetype_lens.py`, wired into `src/advisor/engine.py`
through `DraftAdvisor(..., lens_factory=...)`.

## Deck value: how the lens and the advisor combine (Nov 13, 2026)

The lens used to hand the advisor one part of its score: the archetype blend
(#1 below), plus two optional multipliers (#2, #3). The advisor then applied
its own on-lane bonus and castability multiplier from a separate, hard guess
at the lane. Two lane models, multiplied together.

Now the lens answers one question for each card: **how much does taking it
raise the deck this pool is heading for?** That number replaces the archetype
blend, the on-lane bonus and the castability multiplier.

- Each of the ten color pairs has a deck in the making: the pool's best 23
  cards castable there.
- A card is worth, in a pair, its overall win rate plus 1.3 times its **fit**
  there. Fit is how much better the card does in the pair than the pair's
  cards do on average. A card's raw gain in a pair is partly the pair's level
  (every card of a strong pair wins more there); upstream's whole-deck test
  found the level doesn't go with winning and the fit does, at 1.29 times the
  weight of overall rating. Fit is shrunk for sample size.
- The card adds to a pair's deck what it is worth there above the card it
  would push out (above a replacement-level card while the deck isn't full),
  and nothing where it can't be cast.
- Your deck is a soft maximum over the ten pairs' decks. Early, every lane
  counts, so a card castable in more lanes is worth more, which is what #3
  tried to add by hand. As the pool commits, only lanes still in reach count,
  which is what the on-lane bonus and castability multiplier did by rule.
- The advisor's composition needs (creatures, removal, 2-drops, fixing) scale
  what the card adds, so a card the deck can't use isn't lifted by them. The
  pack-relative power bonus is dropped: applied without the castability
  multiplier it pulled the pool across colors.

Scores stay on the app's scale. A card that goes straight into a settled
lane's deck scores its own worth there; a card that adds nothing scores about
42 (replacement level), with a small tiebreak by win rate. Off-lane cards show
`Off-Lane`, and `Better in UB (+6.2)` now reports fit.

Code: `ArchetypeLens.deck_value`, `ArchetypeSheet.fit`, and the `value_mode`
branch in `DraftAdvisor.evaluate_pack`. `ArchetypeLens.MODE = "blend"` restores
the previous behavior; turning the lens off in Preferences still gives the
plain advisor.

### Does it win more? (draft simulation)

`Tools/DraftSim` simulates whole drafts with the advisor making every pick
and estimates the win rate of the deck it ends with (see its README for how,
and for what it can't show). Value minus the plain advisor, in game win-rate
points, on the same pods:

| set | pods | win model | win model, no pair terms | app deck score | event wins |
|---|---|---|---|---|---|
| FRA | 2,000 | +2.68 (0.09) | +2.02 (0.06) | +0.06 (0.04) | +0.30 |
| TDM | 1,000 | +1.91 (0.10) | +1.38 (0.08) | +0.55 (0.05) | +0.22 |
| FIN | 1,000 | +2.48 (0.12) | +2.38 (0.11) | +0.21 (0.07) | +0.28 |
| TLA | 1,000 | +1.74 (0.09) | +1.33 (0.08) | +0.11 (0.06) | +0.20 |
| SOS | 1,000 | +1.72 (0.12) | +1.51 (0.11) | +0.27 (0.06) | +0.20 |

The previous lens ("blend") against the plain advisor, same pods, win model:
FRA -0.19 (0.06), TDM -0.12 (0.07), FIN -0.04 (0.07), TLA -0.03 (0.05),
SOS -0.02 (0.07). It was about even in the simulation too.

How to read it:

- Most of the gain is fit. The decks' mean rating barely moves (+0.00 to +0.03
  SDs) while mean fit rises by 0.045 to 0.07 SDs. So the size of the gain
  depends on what fit is worth. If fit were worth half what the win model
  gives it, the gain would be about half; if it were worth nothing, the gain
  would be the app deck score's column, which ignores fit.
- The settings were chosen on FRA with seed 1 (1,000 pods). The FRA row is a
  fresh seed and the other four sets weren't used for any choice. The fit
  weight wasn't tuned: 1.3 is upstream's held-out estimate.
- On imitation, value mode is level with the plain advisor: replaying 2,000
  FRA drafts (salt merge432), top-1 +0.2 (SE 0.2) and regret -0.005 (SE 0.042) against it. It
  agrees with drafters about as often while taking different cards: 18 of 42
  differ from the plain advisor's in a typical simulated draft.

Rerun with `Tools/DraftSim/draft_sim.sh FRA 2000`.

## The earlier pieces ("blend" mode)

The rest of this page describes the lens before deck-value scoring. It still
runs with `ArchetypeLens.MODE = "blend"`. In "value" mode, #1 is replaced by
fit, and #2 and #3 still apply if switched on (they are off by default).

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
