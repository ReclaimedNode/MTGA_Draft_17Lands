"""A model of how 17Lands drafters pick, for the other seven seats.

    python Tools/DraftSim/pickmodel.py --data sim_data.json.gz \
        --dataset dataset.json.gz --set FRA --out pick_model.json

A conditional logit fit to real picks: each card in the pack gets a utility
from its win rate, how early drafters usually take it, and how well its colors
match the pool so far, each allowed to change through the draft. The
simulation's other seats draw their picks from it.
"""

import argparse
import json

import numpy as np
from scipy.optimize import minimize

from common import Table, load_app, load_json

FEATURES = ["rating", "rating*t", "taken_early", "taken_early*t", "color_share",
            "color_share*t", "in_top2", "in_top2*t", "colorless", "colorless*t"]
TOTAL_PICKS = 42.0
MAX_PICKS = 150000  # picks used for the fit; more adds time, not accuracy


def pool_state(table, pool):
    """(share of the pool's colored cards having each color, top-two mask or None)."""
    pool = [c for c in pool if not table.is_land[c] and table.mask[c]]
    if not pool:
        return np.zeros(5), None
    counts = table.color_bits[pool].sum(0).astype(float)
    share = counts / len(pool)
    top2 = None
    if len(pool) >= 3:
        order = np.argsort(-(counts + np.arange(5, 0, -1) * 1e-6))[:2]
        top2 = np.zeros(5, bool)
        top2[order] = True
    return share, top2


def features(table, pack, share, top2, n_taken):
    """Feature rows for the cards of a pack (array of card indices)."""
    t = n_taken / TOTAL_PICKS
    bits = table.color_bits[pack]
    colored = bits.any(1)
    # A card needs all of its colors: take the weakest.
    aff = np.where(bits, share[None, :], 1.0).min(1) * colored
    in2 = np.zeros(len(pack))
    if top2 is not None:
        in2 = (~(bits & ~top2[None, :]).any(1) & colored).astype(float)
    cl = table.colorless[pack].astype(float)
    z, e = table.z[pack], table.ata_z[pack]
    return np.column_stack([z, z * t, e, e * t, aff, aff * t, in2, in2 * t, cl, cl * t])


def fit(table, picks, max_pack=16):
    n = len(picks)
    X = np.zeros((n, max_pack, len(FEATURES)))
    valid = np.zeros((n, max_pack), bool)
    chosen = np.zeros(n, int)
    keep = np.zeros(n, bool)
    for k, (pack_no, pick_no, taken, pack, pool) in enumerate(picks):
        pack = np.array(sorted(set(pack)), int)
        if len(pack) < 2 or len(pack) > max_pack or taken not in pack:
            continue
        share, top2 = pool_state(table, pool)
        X[k, : len(pack)] = features(table, pack, share, top2, len(pool))
        valid[k, : len(pack)] = True
        chosen[k] = int(np.where(pack == taken)[0][0])
        keep[k] = True
    X, valid, chosen = X[keep], valid[keep], chosen[keep]
    rows = np.arange(len(X))

    def loss(w):
        u = X @ w
        u = np.where(valid, u, -1e9)
        m = u.max(1, keepdims=True)
        e = np.exp(u - m) * valid
        s = e.sum(1, keepdims=True)
        p = e / s
        ll = (u[rows, chosen] - m[:, 0] - np.log(s[:, 0])).mean()
        g = (X[rows, chosen] - (p[:, :, None] * X).sum(1)).mean(0)
        return -ll, -g

    res = minimize(loss, np.zeros(len(FEATURES)), jac=True, method="L-BFGS-B")
    w = res.x
    u = np.where(valid, X @ w, -1e9)
    top1 = float((u.argmax(1) == chosen).mean())
    by_rating = float((np.where(valid, X[:, :, 0], -1e9).argmax(1) == chosen).mean())
    return w, {"picks": int(len(X)), "log_loss": float(res.fun), "top1": top1,
               "top1_by_rating_alone": by_rating}


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
    w, info = fit(table, data["picks"][:MAX_PICKS])
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump({"set": a.set, "features": FEATURES, "weights": list(map(float, w)), **info}, f, indent=1)
    print(json.dumps(info), dict(zip(FEATURES, np.round(w, 3))))


if __name__ == "__main__":
    main()
