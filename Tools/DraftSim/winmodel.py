"""Fit the simulation's win model: what a deck's cards say about its results.

    python Tools/DraftSim/winmodel.py --data sim_data.json.gz \
        --dataset dataset.json.gz --set FRA --out win_model.json

A logistic regression of real drafters' event records on their decks (the cards
they usually had in the main deck): the spells' mean overall win rate, their
mean fit in the deck's color pair, the share of spells outside that pair, the
pair itself, and the drafter's 17Lands buckets. The simulation applies it to
the decks the advisor ends up with, for an average drafter.
"""

import argparse
import json

import numpy as np

from common import Table, load_app, load_json

MIN_SPELLS, MAX_SPELLS = 20, 26


def design(table, drafts):
    rows, wins, games, skills, played = [], [], [], [], []
    for d in drafts:
        if d["wins"] is None or d["losses"] is None or d["wins"] + d["losses"] <= 0:
            continue
        spells = [c for c in d["main"] if not table.is_land[c] and table.card[c] is not None]
        if not MIN_SPELLS <= len(spells) <= MAX_SPELLS:
            continue
        rows.append(table.deck_features(spells))
        wins.append(d["wins"])
        games.append(d["wins"] + d["losses"])
        skills.append(d["skill"])
        played.append(d["games"])
    return rows, np.array(wins, float), np.array(games, float), skills, played


def logistic(X, wins, games, ridge=1e-6, iters=50):
    w = np.zeros(X.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-(X @ w)))
        grad = X.T @ (wins - games * p) - ridge * w
        H = (X * (games * p * (1 - p))[:, None]).T @ X + ridge * np.eye(len(w))
        step = np.linalg.solve(H, grad)
        w += step
        if np.abs(step).max() < 1e-9:
            break
    return w, np.sqrt(np.diag(np.linalg.inv(H)))


def fit(table, drafts, pair_terms=True):
    rows, wins, games, skills, played = design(table, drafts)
    n_pairs = len(table.pairs)
    skill_levels = sorted({s for s in skills if s is not None})
    game_levels = sorted({g for g in played if g is not None})
    names = ["intercept", "quality", "fit", "off_pair"]
    names += [f"pair:{p}" for p in table.pairs[1:]]
    names += [f"skill:{s}" for s in skill_levels[1:]] + [f"games:{g}" for g in game_levels[1:]]
    X = np.zeros((len(rows), len(names)))
    X[:, 0] = 1
    for i, (pair, q, f, off) in enumerate(rows):
        X[i, 1:4] = q, f, off
        if pair > 0 and pair_terms:
            X[i, 3 + pair] = 1
        if skills[i] in skill_levels[1:]:
            X[i, 3 + n_pairs + skill_levels[1:].index(skills[i])] = 1
        if played[i] in game_levels[1:]:
            X[i, 3 + n_pairs + len(skill_levels) - 1 + game_levels[1:].index(played[i])] = 1
    if not pair_terms:
        used = [k for k, n in enumerate(names) if not n.startswith("pair:")]
        X, names = X[:, used], [names[k] for k in used]
        n_pairs = 1
    w, se = logistic(X, wins, games)
    first_player = 3 + n_pairs
    # The average drafter: the mean of the bucket terms over the fitted decks.
    player = float((X[:, first_player:] @ w[first_player:]).mean())
    return {
        "names": names,
        "weights": list(map(float, w)),
        "se": list(map(float, se)),
        "player": player,
        "decks": len(rows),
        "games": float(games.sum()),
        "win_rate": float(wins.sum() / games.sum()),
        "tau2": table.tau2,
        "quality_sd": float(X[:, 1].std()),
        "fit_sd": float(X[:, 2].std()),
    }


def win_rate(model, table, spells):
    """The model's game win rate for a deck with these spells, average drafter."""
    w = dict(zip(model["names"], model["weights"]))
    pair, q, f, off = table.deck_features(spells)
    x = w["intercept"] + model["player"] + w["quality"] * q + w["fit"] * f + w["off_pair"] * off
    x += w.get(f"pair:{table.pairs[pair]}", 0.0)
    return 1 / (1 + np.exp(-x))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--src", default=".")
    p.add_argument("--data", required=True)
    p.add_argument("--dataset", required=True)
    p.add_argument("--set", default="")
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)
    app = load_app(a.src, a.dataset, a.set)
    data = load_json(a.data)
    table = Table(app, data["cards"])
    models = {
        "pair-adjusted": fit(table, data["drafts"], pair_terms=True),
        "no pair terms": fit(table, data["drafts"], pair_terms=False),
    }
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump({"set": a.set, "models": models}, f, indent=1)
    for label, model in models.items():
        print(label)
        for n, w, s in zip(model["names"], model["weights"], model["se"]):
            if not n.startswith(("skill", "games")):
                print(f"  {n:12s} {w:+.4f} (SE {s:.4f})")
    print({k: model[k] for k in ("decks", "games", "win_rate", "tau2", "quality_sd", "fit_sd")})


if __name__ == "__main__":
    main()
