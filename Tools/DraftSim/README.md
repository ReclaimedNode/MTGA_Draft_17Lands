# Draft simulation

Answers the question the replay can't: **does following the advisor end in a
deck that wins more?** The replay (`Tools/AdvisorReplay`) checks the advisor's
picks against what drafters took. This simulates whole drafts with the advisor
making every pick, builds the deck it ends up with, and estimates that deck's
win rate.

It is separate from the app: nothing in `src/` imports it.

```sh
Tools/DraftSim/draft_sim.sh FRA 2000
```

That seats three advisors in the same 2,000 simulated pods and writes
`results/sim_FRA.md`: the plain advisor (`base`), the lens as it was before
deck-value scoring (`blend`), and the lens scoring by deck value (`value`, the
app's setting). About ten minutes on the Mac Studio. `ARMS="value"` runs fewer
arms, `JOBS=8` uses more cores, and a third argument changes the seed, for an
independent set of pods.

## How a draft is simulated

- **Packs** are real: every pack a 17Lands drafter opened (the first pick of
  each round in the public draft dump). A pod deals 24 of them at random.
- **Seat 0** is the advisor under test. It takes its top-scored card at every
  pick, seeing only its pack and its pool, as in the app.
- **The other seven seats** pick like 17Lands drafters. `pickmodel.py` fits a
  model to real picks: a card's pull depends on its win rate, how early
  drafters usually take it, and how well its colors match the seat's pool, each
  changing through the draft. Seats draw their picks from it, so they are as
  varied as real drafters. The model's first choice is the drafter's actual
  pick 51-56% of the time, depending on the set.
- Packs pass left, right, left. Every pick of every seat changes what the
  others see, including what wheels.
- **The deck** is the app's best-scoring quick build of seat 0's 42 cards, the
  same builders the replay uses.

Pod *k* gets the same packs and the same luck for the other seats in every
run, so advisors are compared pod by pod. That is why 1,000 pods separate
advisors 0.1 win-rate points apart.

## How a deck is scored

`winmodel.py` fits a win model on the same dump: each real drafter's event
record against the deck they played (the cards they usually had in the main
deck). The deck is summarized by

- **mean rating**: its spells' overall GIH WR, in standard deviations;
- **mean fit**: how much better its spells do in the deck's color pair than
  that pair's cards do on average (see `ArchetypeSheet.fit`);
- the share of spells outside the pair, the pair itself, and the drafter's
  17Lands win-rate and experience buckets.

The simulation applies that model to seat 0's deck for an average drafter. The
report gives the result three ways, because each has a different blind spot:

| measure | what it is |
|---|---|
| win rate (pair-adjusted) | the win model above. The main measure |
| win rate (no pair terms) | the same without a term for each color pair, in case those terms reward landing in particular pairs |
| win rate (app deck score) | the app's own deck score, fit by upstream to 915,000 decks. It doesn't count fit at all |

It also shows the best the win model finds among the app's candidate builds,
and the decks' mean rating and fit, which say where a difference comes from.

## What it can and can't show

- **The win model is a model.** No games are played. It was fit to real results,
  and upstream's held-out test found the same thing it relies on (within a
  pair, fit goes with winning, at about 1.3 times the weight of overall rating),
  but a deck is more than these averages. It can't see curve, creature count or
  synergy beyond pair fit. Upstream's rule tests found the "needs creatures /
  removal / 2-drops" rules are supported by real results, and this simulation
  can't credit them.
- **Ratings and results come from the same games.** Fit is shrunk for sample
  size so that picking the best-looking fits doesn't pick the luckiest
  samples, but the ratings aren't held out. Only 17Lands' game data would allow
  that.
- **An advisor that scores cards the way the win model does is graded on its
  own terms.** The `value` lens scores cards by overall rating plus fit, which
  is what the win model counts. The app's deck score is the check on that: it
  ignores fit, so a gain there comes from card quality alone.
- **The other seats don't react like people.** They pick like the average
  17Lands drafter and take cards about as early as real drafters do (within
  0.6 picks on average), but they commit to two colors less firmly: 66% of a
  simulated drafter's colored cards are in their two main colors, against 75%
  for real drafters.

## Files

| file | does |
|---|---|
| `draft_sim.sh` | Everything, in order, with the results cached in `.cache/draftsim/` |
| `extract.py` | Reads the draft dump once: opened packs, each drafter's deck and record, a sample of picks |
| `pickmodel.py` | Fits the model of how the other seats pick |
| `winmodel.py` | Fits the win model |
| `sim.py` | Simulates pods for one advisor |
| `report.py` | Pairs the pods and writes the Markdown report |
| `tests/` | `poetry run pytest Tools/DraftSim/tests` |
