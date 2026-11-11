"""Fill missing GIH WR in an early-set 17Lands dataset with estimates.

Usage:  python Tools/estimate_gihwr.py Sets/TRK_PremierDraft_All_Data.json

Writes Sets/TRK_PremierDraft_All_Custom-Est<YYYYMMDD>_Data.json next to it and
leaves the original untouched. Only "All Decks" gihwr is filled; real values are
never changed. Each estimated card gets "gihwr_est": 1.0 in its All Decks stats,
and meta["estimated_gihwr_count"] records how many were filled.

Model: weighted ridge regression, fitted on cards that already have a real
GIH WR, predicting it from ALSA, ATA, game-played win rate (GP WR), play rate
and rarity. Cards without GP WR use a smaller model (ALSA + rarity). Every
prediction is shrunk toward the rarity mean, by how few games the card has.
"""
import json, math, sys, datetime, os

RARITIES = ["common", "uncommon", "rare", "mythic"]


def solve(X, y, w, lam=1.0):
    """Weighted ridge via normal equations (tiny dims, no numpy needed)."""
    k = len(X[0])
    A = [[0.0] * k for _ in range(k)]
    b = [0.0] * k
    for xi, yi, wi in zip(X, y, w):
        for i in range(k):
            b[i] += wi * xi[i] * yi
            for j in range(k):
                A[i][j] += wi * xi[i] * xi[j]
    for i in range(1, k):  # don't penalise intercept
        A[i][i] += lam * sum(w) / len(w)
    # Gaussian elimination
    M = [row[:] + [bi] for row, bi in zip(A, b)]
    for c in range(k):
        p = max(range(c, k), key=lambda r: abs(M[r][c]))
        M[c], M[p] = M[p], M[c]
        if abs(M[c][c]) < 1e-12:
            continue
        for r in range(k):
            if r != c:
                f = M[r][c] / M[c][c]
                for cc in range(c, k + 1):
                    M[r][cc] -= f * M[c][cc]
    return [M[i][k] / M[i][i] if abs(M[i][i]) > 1e-12 else 0.0 for i in range(k)]


def feats(s, rarity, full):
    alsa = s.get("alsa") or 7.0
    ata = s.get("ata") or alsa
    r = [1.0 if rarity == x else 0.0 for x in RARITIES[1:]]
    base = [1.0, alsa, ata] + r
    if full:
        base += [s.get("gpwr", 0.0), s.get("play_rate", 0.0) / 100.0]
    return base


def main(path):
    data = json.load(open(path))
    cards = data["card_ratings"]
    known, missing = [], []
    for cid, c in cards.items():
        s = c["deck_colors"]["All Decks"]
        (known if s.get("gihwr", 0) > 0 else missing).append(cid)
    if len(known) < 12:
        sys.exit(f"Only {len(known)} cards have a real GIH WR; need at least 12 to fit.")

    def fit(full):
        rows = [k for k in known if not full or cards[k]["deck_colors"]["All Decks"].get("gpwr", 0) > 0]
        X = [feats(cards[k]["deck_colors"]["All Decks"], cards[k].get("rarity"), full) for k in rows]
        y = [cards[k]["deck_colors"]["All Decks"]["gihwr"] for k in rows]
        w = [math.sqrt(max(cards[k]["deck_colors"]["All Decks"].get("samples", 1), 1)) for k in rows]
        return solve(X, y, w), len(rows)

    beta_full, n_full = fit(True)
    beta_small, n_small = fit(False)
    rar_mean = {}
    for r in RARITIES:
        v = [cards[k]["deck_colors"]["All Decks"]["gihwr"] for k in known if cards[k].get("rarity") == r]
        rar_mean[r] = sum(v) / len(v) if v else None
    overall = sum(cards[k]["deck_colors"]["All Decks"]["gihwr"] for k in known) / len(known)

    filled = 0
    for cid in missing:
        c = cards[cid]
        s = c["deck_colors"]["All Decks"]
        if not s.get("alsa") and not s.get("gpwr"):
            continue  # no signal at all (e.g. basic lands)
        full = s.get("gpwr", 0) > 0
        beta = beta_full if full else beta_small
        pred = sum(b * x for b, x in zip(beta, feats(s, c.get("rarity"), full)))
        prior = rar_mean.get(c.get("rarity")) or overall
        games = s.get("game_count", 0)
        trust = games / (games + 500.0)          # more games -> trust the model more
        est = trust * pred + (1 - trust) * (0.5 * pred + 0.5 * prior)
        est = max(40.0, min(65.0, est))
        s["gihwr"] = round(est, 2)
        s["gihwr_est"] = 1.0
        filled += 1

    data["meta"]["estimated_gihwr_count"] = filled
    data["meta"]["estimate_model"] = f"ridge n_full={n_full} n_small={n_small} known={len(known)}"
    stamp = datetime.date.today().strftime("%Y%m%d")
    base = os.path.basename(path)
    set_code, event, group = base.split("_")[:3]
    out = os.path.join(os.path.dirname(path), f"{set_code}_{event}_{group}_Custom-Est{stamp}_Data.json")
    json.dump(data, open(out, "w"))
    print(f"known={len(known)} filled={filled} left_blank={len(missing)-filled} -> {out}")


if __name__ == "__main__":
    main(sys.argv[1])
