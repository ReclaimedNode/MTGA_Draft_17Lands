"""Compare simulated advisors pod by pod.

    python Tools/DraftSim/report.py --data sim_data.json.gz --dataset dataset.json.gz \
        --win-model win_model.json --base base.*.json --arm lens=lens.*.json

For each pod, seat 0's deck is the app's best-scoring quick build. Its game win
rate comes from the win model (winmodel.py), and from the app's own deck score
as a second opinion. Differences are arm minus base on the same pods, with a
standard error; under about two standard errors is no difference.
"""

import argparse
import glob
import json

import numpy as np

from common import Table, load_app, load_json
from winmodel import win_rate


def load_arm(patterns):
    pods, meta = {}, None
    for pattern in patterns.split(","):
        for path in sorted(glob.glob(pattern)):
            d = load_json(path)
            meta = meta or {k: d.get(k) for k in ("label", "lens", "lens_off", "params")}
            for pod in d["pods"]:
                pods[pod["pod"]] = pod
    return pods, meta


def score_arm(pods, table, models, scorer):
    """{measure: {pod: value}} for one arm."""
    out = {}
    for n, pod in pods.items():
        if not pod["builds"]:
            continue
        app_score, spells = max(pod["builds"], key=lambda b: b[0])
        row = {}
        for label, model in models.items():
            p = float(win_rate(model, table, spells))
            row[f"win rate ({label})"] = 100 * p
            row[f"event wins ({label})"] = scorer.expected_wins(p, 7, 3)
            best = max(float(win_rate(model, table, b[1])) for b in pod["builds"])
            row[f"win rate, best build ({label})"] = 100 * best
        log_odds = scorer.WIN_LOG_ODDS_AT_BASE + scorer.WIN_LOG_ODDS_PER_POINT * (app_score - scorer.BASE_SCORE)
        row["win rate (app deck score)"] = 100 / (1 + np.exp(-log_odds))
        pair, q, f, off = table.deck_features(spells)
        row["deck: mean rating (SDs)"] = q
        row["deck: mean fit (SDs)"] = f
        row["deck: spells off the pair (%)"] = 100 * off
        for k, v in row.items():
            out.setdefault(k, {})[n] = v
        out.setdefault("_pair", {})[n] = pair
    return out


def compare(base, arm):
    """(mean base, mean arm, mean difference, SE, pods) over shared pods."""
    shared = sorted(set(base) & set(arm))
    b = np.array([base[k] for k in shared])
    a = np.array([arm[k] for k in shared])
    d = a - b
    se = d.std(ddof=1) / np.sqrt(len(d)) if len(d) > 1 else float("nan")
    return b.mean(), a.mean(), d.mean(), se, len(d)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--src", default=".")
    p.add_argument("--data", required=True)
    p.add_argument("--dataset", required=True)
    p.add_argument("--win-model", required=True)
    p.add_argument("--set", default="")
    p.add_argument("--base", required=True, help="Glob(s) of the base arm's sim.py outputs")
    p.add_argument("--arm", action="append", default=[], metavar="NAME=GLOB")
    p.add_argument("--json", help="Also write the numbers here")
    a = p.parse_args(argv)

    app = load_app(a.src, a.dataset, a.set)
    from src.advisor import deck_scorer

    table = Table(app, load_json(a.data)["cards"])
    models = load_json(a.win_model)["models"]
    base_pods, _ = load_arm(a.base)
    base = score_arm(base_pods, table, models, deck_scorer)
    measures = [m for m in base if not m.startswith("_")]
    numbers = {}
    print(f"# Draft simulation: {a.set}\n")
    print("Seat 0 takes the advisor's top card in every pick of an eight-seat pod of real packs;")
    print("the other seats pick like 17Lands drafters. `base` is the plain advisor.\n")
    for label, model in models.items():
        w = dict(zip(model["names"], model["weights"]))
        print(f"Win model ({label}), fit to {model['decks']:,} real decks: log-odds of a game = "
              f"{w['quality']:+.2f} x mean rating {w['fit']:+.2f} x mean fit {w['off_pair']:+.2f} x share off the pair"
              + (" + the pair's own term" if label == "pair-adjusted" else "") + ".")
    print()
    for spec in a.arm:
        name, _, pattern = spec.partition("=")
        pods, meta = load_arm(pattern)
        arm = score_arm(pods, table, models, deck_scorer)
        shared = sorted(set(base_pods) & set(pods))
        same = np.mean([base_pods[k]["pool"] == pods[k]["pool"] for k in shared])
        n_cards = len(table.names)
        differ = np.mean([
            42 - np.minimum(np.bincount(base_pods[k]["pool"], minlength=n_cards),
                            np.bincount(pods[k]["pool"], minlength=n_cards)).sum()
            for k in shared
        ])
        pairs = np.mean([base["_pair"].get(k) == arm["_pair"].get(k) for k in shared])
        print(f"## {name} minus base ({len(shared)} pods)\n")
        print(f"Same 42 cards in {100 * same:.0f}% of pods; {differ:.1f} cards differ on average; "
              f"same deck colors in {100 * pairs:.0f}%.\n")
        print("| measure | base | " + name + " | difference | SE |\n|---|---|---|---|---|")
        numbers[name] = {}
        for m in measures:
            b, v, d, se, n = compare(base[m], arm[m])
            digits = 3 if "SDs" in m or "event" in m else 2
            print(f"| {m} | {b:.{digits}f} | {v:.{digits}f} | {d:+.{digits}f} | {se:.{digits}f} |")
            numbers[name][m] = {"base": b, "arm": v, "diff": d, "se": se, "pods": n}
        print()
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(numbers, f, indent=1)


if __name__ == "__main__":
    main()
