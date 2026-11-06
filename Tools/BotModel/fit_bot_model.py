"""Fit and test the Quick Draft bot model for a set.

    python Tools/BotModel/fit_bot_model.py --dump dump.csv.gz --dataset dataset.json.gz --set FRA

Reads a 17Lands draft dump, fits each card's bot preference on 80% of drafts
(chosen by a hash of the draft ID), and tests wheel predictions on the other
20% against:

- gihwr: the same model with scores set by GIH WR ("bots take the best cards")
- app: the app's current wheel estimate (ALSA curve and pack rank)
- flat: every card equally likely to be taken

Writes the model to Sets/BotModels/<SET>_<EVENT>.json, where the app finds it,
and a report to results/bot_model_<SET>_<EVENT>.md.
"""

import argparse
import gzip
import os
import shutil
import sys
import tempfile
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)


def load_dataset(path):
    from src.dataset import Dataset

    ds = Dataset()
    with tempfile.TemporaryDirectory() as tmp:
        plain = path
        if path.endswith(".gz"):
            plain = os.path.join(tmp, "dataset.json")
            with gzip.open(path, "rb") as src, open(plain, "wb") as dst:
                shutil.copyfileobj(src, dst)
        ds.open_file(plain)
    return ds


def app_wheel_predictor(dataset):
    """Survival probabilities from the app's existing _wheel_chance."""
    from src.advisor.engine import DraftAdvisor
    from src.set_metrics import SetMetrics

    advisor = DraftAdvisor(SetMetrics(dataset), [])
    by_name = {}
    for card in dataset.get_card_ratings().values():
        name = card.get("name")
        if name:
            by_name.setdefault(name, card)
            by_name.setdefault(name.split(" // ")[0], card)

    def gih(card):
        return float(card.get("deck_colors", {}).get("All Decks", {}).get("gihwr", 0) or 0)

    def predict(pick, before):
        cards = [by_name.get(n, {"name": n}) for n in before]
        order = sorted(range(len(cards)), key=lambda i: -gih(cards[i]))
        rank = {i: r for r, i in enumerate(order)}
        return [
            advisor._wheel_chance(c, pick, rank[i], pack_size=len(before) + 1) / 100.0
            for i, c in enumerate(cards)
        ]

    return predict


def fmt(metrics):
    return (
        f"| {metrics['log_loss']:.4f} | {metrics['brier']:.4f} | "
        f"{100 * metrics['accuracy']:.1f} | {100 * metrics['wheel_call_precision']:.1f} |"
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dump", required=True, help="17Lands draft dump (.csv or .csv.gz)")
    parser.add_argument("--dataset", default="", help="The app's dataset for the set, for baselines")
    parser.add_argument("--set", required=True, help="Set code, e.g. FRA")
    parser.add_argument("--event", default="QuickDraft", help="QuickDraft (bots) or PremierDraft (people)")
    parser.add_argument("--max-drafts", type=int, default=20000, help="Drafts to read (0 = all)")
    parser.add_argument("--iterations", type=int, default=400)
    parser.add_argument("--out", default="", help="Model path (default Sets/BotModels/<SET>_<EVENT>.json)")
    args = parser.parse_args(argv)

    from src.advisor import bot_model as bm

    t = time.time()
    train, test = bm.read_dump_rounds(args.dump, args.max_drafts)
    print(f"Read {len(train)} training and {len(test)} test rounds in {time.time() - t:.0f}s")
    if not train or not test:
        raise SystemExit("No usable rounds: is this an 8-seat draft dump?")

    dataset = load_dataset(args.dataset) if args.dataset else None
    has_ratings = bool(dataset and dataset.get_card_ratings())
    base = bm.gihwr_baseline(dataset.get_card_ratings(), train) if has_ratings else None
    prior = base.scores if base else None

    t = time.time()
    model = bm.fit(train, iterations=args.iterations, prior=prior)
    model.meta.update({"set": args.set.upper(), "event": args.event})
    print(f"Fitted {model.meta['cards']} cards in {time.time() - t:.0f}s")

    results = [("bot model", bm.evaluate(test, lambda pk, b: model.survival(b)))]
    if has_ratings:
        results.append(("gihwr (bots take the best cards)", bm.evaluate(test, lambda pk, b: base.survival(b))))
        results.append(("app's current wheel %", bm.evaluate(test, app_wheel_predictor(dataset))))
    flat = bm.BotModel({})
    results.append(("flat", bm.evaluate(test, lambda pk, b: flat.survival(b))))

    by_pick = []
    for pick in sorted({r[1] for r in test}):
        sub = [r for r in test if r[1] == pick]
        m = bm.evaluate(sub, lambda pk, b: model.survival(b))
        by_pick.append((pick, len(sub), m))

    out = args.out or bm.BotModel.path_for(args.set, args.event)
    model.save(out)

    lines = [
        f"# Bot model: {args.set.upper()} {args.event}",
        "",
        f"{len(train)} training rounds, {len(test)} test rounds (held-out drafts). "
        "Each test card: did it come back 8 picks later?",
        "",
        "| predictor | log loss (lower better) | Brier (lower better) | accuracy % | precision of 'will wheel' calls % |",
        "|---|---|---|---|---|",
    ]
    lines += [f"| {name} {fmt(m)}" for name, m in results]
    lines += ["", "Bot model by pick (pack seen at this pick vs 8 later):", "",
              "| pick | rounds | log loss | accuracy % |", "|---|---|---|---|"]
    lines += [f"| {p} | {n} | {m['log_loss']:.4f} | {100 * m['accuracy']:.1f} |" for p, n, m in by_pick]
    if dataset and dataset.get_card_ratings():
        under = bm.undervalued(model, dataset.get_card_ratings(), prior=prior)
        lines += ["", "Cards bots take least compared with their GIH WR, among cards bots saw 150+ times (good wheel targets):", "",
                  "| card | GIH WR | bot score |", "|---|---|---|"]
        lines += [f"| {n} | {wr:.1f} | {s:+.2f} |" for n, wr, s in under]
    lines += ["", f"Model saved to {out}"]
    report = "\n".join(lines)
    os.makedirs("results", exist_ok=True)
    path = os.path.join("results", f"bot_model_{args.set.upper()}_{args.event}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(report + "\n")
    print(report)
    print(f"\nReport saved to {path}")


if __name__ == "__main__":
    main()
