# Quick Draft bot model

Arena's Quick Draft bots pick consistently, so what they take can be learned.
This fork fits a per-set model of bot picks from 17Lands' public Quick Draft
dumps. In Quick Draft the advisor uses it instead of the ALSA curve to show
each card's wheel chance.

Code: `src/advisor/bot_model.py`. Fitting tool: `Tools/BotModel/`.

## How it learns

In an eight-seat draft, the pack you see at pick *p* comes back at pick *p* + 8.
The cards missing between those two looks are the one you took plus one taken
by each of the seven other seats, which are bots in Quick Draft. 17Lands
records every pack each drafter saw, so each draft gives up to 18 of these
bot rounds (picks 1–6 of each pack, for 14-card packs).

Each card gets a bot preference score. Each of the seven bots is modeled as a
draw from the pack weighted by those scores, so a card's chance to come back is
`(1 - its share of the pack's weight) ^ 7`. The scores are fitted to the
observed rounds. Every card starts from a score based on its GIH WR, and bot
data moves it only as far as the evidence supports. Without that starting
point, strong cards that drafters usually take before the bots see them would
drift toward average and look likely to wheel.

The model doesn't yet account for bots favoring colors they've already picked.
The test report shows how much that matters: accuracy by pick should stay
level if it doesn't.

## Fitting and testing a set

From the repository root, with the app's environment active:

```sh
Tools/BotModel/bot_model.sh FRA
```

This downloads the set's Quick Draft dump, reads 20,000 drafts, fits on 80%
(chosen by a hash of each draft's ID), and tests on the other 20%. It writes:

- `Sets/BotModels/FRA_QuickDraft.json`, which the app picks up automatically
  in FRA Quick Drafts;
- `results/bot_model_FRA_QuickDraft.md`, which compares wheel predictions with
  "bots take the highest-GIH WR card", the app's previous wheel estimate, and a
  flat guess, and lists the cards bots take least compared with their win
  rate.

Use `Tools/BotModel/bot_model.sh FRA 0` to read every draft in the dump.

## In the app

In a Quick Draft for a set with a fitted model, the wheel % column comes from
the bot model, assuming you take the pack's highest-GIH WR card (or the second
highest, for that card itself). A card with a 60%+ wheel chance and an
above-average win rate shows "Bots likely pass it". Scoring is unchanged; as
upstream does, wheel chance is shown but not scored. Premier Draft, Pick-Two
and sets without a model use the original estimate.
