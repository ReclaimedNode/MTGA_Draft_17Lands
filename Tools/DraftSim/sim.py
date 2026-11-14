"""Simulate whole drafts with the advisor in one seat.

    python Tools/DraftSim/sim.py --data sim_data.json.gz --dataset dataset.json.gz \
        --pick-model pick_model.json --set FRA --pods 0:500 --label base --out base.json
    python Tools/DraftSim/sim.py ... --lens --label lens --out lens.json

Each pod is eight seats and three rounds of real packs (packs as 17Lands
drafters opened them). Seat 0 always takes the advisor's top card; the other
seven draw their picks from the fitted model of 17Lands drafters. After the
draft the app's quick deck builders build seat 0's deck.

Pods are numbered. Pod k gets the same packs and the same luck for the other
seats in every run with the same --seed, so two advisors can be compared pod
by pod, and a range of pods can be simulated in pieces (--pods 0:500, then
500:1000) and joined.
"""

import argparse
import json
import os
import time

import numpy as np

from common import Table, load_app, load_json
from pickmodel import features, pool_state

SEATS = 8
ROUNDS = 3


class Hero:
    """Seat 0: the app's advisor and deck builders."""

    def __init__(self, app, table):
        self.app, self.table = app, table

    def pick(self, pack, pool, pack_no, pick_no):
        cards = [self.table.card[c] for c in pack if self.table.card[c] is not None]
        if not cards:
            return pack[0]
        scores = self.app.advise(cards, [self.table.card[c] for c in pool if self.table.card[c] is not None], pack_no, pick_no)
        if not scores:
            return pack[0]
        best = max(scores, key=scores.get)
        return self.table.index[best]

    def builds(self, pool):
        """Every quick build of the pool: (app deck score, spells as card indices)."""
        app, cl, t = self.app, self.app.card_logic, self.table
        cards = [t.card[c] for c in pool if t.card[c] is not None]
        made = []
        for pair in cl.identify_top_pairs(cards, app.metrics):
            made.append((cl.build_variant_consistency(cards, pair, app.metrics), pair))
            made.append((cl.build_variant_curve(cards, pair, app.metrics), pair))
            deck, splash = cl.build_variant_greedy(cards, pair, app.metrics)
            made.append((deck, pair + [splash] if splash else pair))
        deck, colors = cl.build_variant_soup(cards, app.metrics)
        made.append((deck, colors[:3] if colors else ["All Decks"]))
        out = []
        for deck, colors in made:
            if not deck:
                continue
            score = cl.calculate_holistic_score(deck, colors, len(cards), app.metrics)[0]
            spells = [
                t.index[c["name"]]
                for c in deck
                if "Land" not in c.get("types", []) and c["name"] in t.index
                for _ in range(int(c.get("count", 1)))
            ]
            if spells:
                out.append([round(score, 3), spells])
        return out


def run_pod(pod, seed, packs, table, weights, hero):
    """Every seat's picks for one pod, in order; seat 0 is the advisor."""
    rng = np.random.default_rng([seed, pod])
    size = len(packs[0])
    dealt = rng.choice(len(packs), SEATS * ROUNDS, replace=False).reshape(ROUNDS, SEATS)
    # One luck value per (seat, pick, card), so the same pack reaching a seat
    # at the same pick gets the same choice whatever seat 0 did elsewhere.
    luck = rng.gumbel(size=(SEATS, ROUNDS * size, len(table.names)))
    pools = [[] for _ in range(SEATS)]
    for rnd in range(ROUNDS):
        current = [list(packs[i]) for i in dealt[rnd]]
        for pick in range(size):
            for seat in range(SEATS):
                pack = current[seat]
                if seat == 0:
                    choice = hero.pick(pack, pools[0], rnd + 1, pick + 1)
                else:
                    arr = np.array(pack, int)
                    share, top2 = pool_state(table, pools[seat])
                    u = features(table, arr, share, top2, len(pools[seat])) @ weights
                    choice = int(arr[np.argmax(u + luck[seat, rnd * size + pick, arr])])
                pack.remove(choice)
                pools[seat].append(choice)
            # Pass left in rounds 1 and 3, right in round 2.
            step = 1 if rnd % 2 == 0 else -1
            current = [current[(seat - step) % SEATS] for seat in range(SEATS)]
    return pools


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--src", default=".")
    p.add_argument("--data", required=True, help="From extract.py")
    p.add_argument("--dataset", required=True)
    p.add_argument("--pick-model", required=True, help="From pickmodel.py")
    p.add_argument("--set", default="")
    p.add_argument("--pods", default="0:200", help="start:stop pod numbers")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--label", required=True)
    p.add_argument("--lens", action="store_true")
    p.add_argument("--lens-off", default="key,flex")
    p.add_argument("--lens-mode", default="", help="With --lens: blend or value (default: the app's)")
    p.add_argument("--param", action="append", default=[], metavar="NAME=VALUE",
                   help="Override a numeric constant on ArchetypeLens, ArchetypeSheet or DraftAdvisor")
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)

    app = load_app(a.src, a.dataset, a.set, lens=a.lens, lens_off=a.lens_off, params=a.param)
    if a.lens and a.lens_mode:
        from src.advisor.archetype_lens import ArchetypeLens

        ArchetypeLens.MODE = a.lens_mode
    data = load_json(a.data)
    table = Table(app, data["cards"])
    weights = np.array(load_json(a.pick_model)["weights"])
    hero = Hero(app, table)
    start, stop = map(int, a.pods.split(":"))
    t0, pods = time.time(), []
    for pod in range(start, stop):
        pool = run_pod(pod, a.seed, data["packs"], table, weights, hero)[0]
        pods.append({"pod": pod, "pool": pool, "builds": hero.builds(pool)})
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump({"set": a.set, "label": a.label, "seed": a.seed, "lens": a.lens,
                   "lens_off": a.lens_off if a.lens else "", "lens_mode": a.lens_mode, "params": a.param,
                   "seconds": round(time.time() - t0), "pods": pods}, f)
    print(f"{a.label}: pods {start}:{stop} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
