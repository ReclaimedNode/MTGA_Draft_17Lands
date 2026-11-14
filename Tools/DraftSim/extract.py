"""Read a 17Lands public draft dump once and keep what the simulation needs.

    python Tools/DraftSim/extract.py --dump dump.csv.gz --out sim_data.json.gz

Keeps, with cards as indices into "cards":

- "packs": every pack as it was opened (the first pick of each round), so the
  simulation deals real packs;
- "drafts": for each finished draft, the drafter's buckets, event record, the
  cards they took and which of them they usually had in the main deck (the
  dump's pick_maindeck_rate), for fitting the win model;
- "picks": every pick of a hashed sample of drafts (pack, pool, card taken),
  for fitting the model of how other drafters pick.
"""

import argparse
import csv
import gzip
import hashlib
import json


def sampled(draft_id, share, salt=""):
    h = int(hashlib.md5((salt + draft_id).encode("utf-8")).hexdigest()[:8], 16)
    return h / 0xFFFFFFFF < share


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def extract(lines, pick_share=0.08, salt="", part=0, parts=1):
    """Read the dump. With parts > 1, keep only the drafts whose hash falls in
    this part, so several processes can share one dump."""
    lines = iter(lines)
    header = next(csv.reader([next(lines)]))
    col = {n: i for i, n in enumerate(header)}
    pack_cols = [(i, c[10:]) for i, c in enumerate(header) if c.startswith("pack_card_")]
    pool_cols = [(i, c[5:]) for i, c in enumerate(header) if c.startswith("pool_")]
    cards = [n for _, n in pack_cols]
    index = {n: k for k, n in enumerate(cards)}
    pack_idx = [(i, index[n]) for i, n in pack_cols]
    pool_idx = [(i, index[n]) for i, n in pool_cols if n in index]

    def counts(row, columns):
        return [k for i, k in columns if row[i] not in ("", "0") for _ in range(int(row[i]))]

    c_id, c_pack, c_pick, c_card = col["draft_id"], col["pack_number"], col["pick_number"], col["pick"]
    c_main = col["pick_maindeck_rate"]
    packs, drafts, picks = [], [], []
    current, draft, keep = None, None, False
    mine = True
    for line in lines:
        # The draft's ID is the third field, before any quoted card name.
        draft_id = line.split(",", 3)[2]
        if draft_id != current and parts > 1:
            mine = int(hashlib.md5(draft_id.encode("utf-8")).hexdigest()[8:16], 16) % parts == part
        if not mine:
            current = draft_id if draft_id != current else current
            continue
        # Most rows need only their first fields; the pack and pool columns
        # are read for first picks and sampled drafts.
        if draft_id == current and not keep and line.split(",", 9)[8] != "0":
            row = next(csv.reader([line[:400]]))
        else:
            row = next(csv.reader([line]))
        if row[c_id] != current or draft is None or draft["id"] != row[c_id]:
            current = row[c_id]
            keep = sampled(current, pick_share, salt)
            draft = {
                "id": current,
                "skill": _num(row[col["user_game_win_rate_bucket"]]),
                "games": _num(row[col["user_n_games_bucket"]]),
                "wins": _num(row[col["event_match_wins"]]),
                "losses": _num(row[col["event_match_losses"]]),
                "taken": [],
                "main": [],
            }
            drafts.append(draft)
        card = index.get(row[c_card])
        if card is None:
            continue
        draft["taken"].append(card)
        rate = _num(row[c_main])
        if rate is not None and rate >= 0.5:
            draft["main"].append(card)
        first = row[c_pick] == "0"
        if first or keep:
            pack = counts(row, pack_idx)
            if first:
                packs.append(pack)
            if keep:
                picks.append(
                    [int(row[c_pack]) + 1, int(row[c_pick]) + 1, card, pack, counts(row, pool_idx)]
                )
    return {"cards": cards, "packs": packs, "drafts": drafts, "picks": picks}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--dump", help="17Lands draft dump (.csv or .csv.gz)")
    p.add_argument("--out", required=True)
    p.add_argument("--pick-share", type=float, default=0.08,
                   help="Share of drafts whose every pick is kept (default 0.08)")
    p.add_argument("--salt", default="")
    p.add_argument("--part", default="0/1", help="k/n: read the k-th of n shares of the drafts")
    p.add_argument("--merge", nargs="+", metavar="PART", help="Join these --part outputs into --out instead")
    a = p.parse_args(argv)
    if a.merge:
        data = merge(a.merge, a.out)
        print(f"{len(data['packs'])} packs, {len(data['drafts'])} drafts, {len(data['picks'])} sampled picks")
        return
    opener = gzip.open if a.dump.endswith(".gz") else open
    with opener(a.dump, "rt", newline="", encoding="utf-8") as f:
        part, parts = map(int, a.part.split("/"))
        data = extract(f, a.pick_share, a.salt, part, parts)
    with gzip.open(a.out, "wt", encoding="utf-8") as f:
        json.dump(data, f)
    print(f"{len(data['packs'])} packs, {len(data['drafts'])} drafts, {len(data['picks'])} sampled picks")




def merge(paths, out):
    """Join the outputs of --part runs."""
    merged = None
    for path in paths:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            data = json.load(f)
        if merged is None:
            merged = data
        else:
            assert merged["cards"] == data["cards"]
            for key in ("packs", "drafts", "picks"):
                merged[key].extend(data[key])
    with gzip.open(out, "wt", encoding="utf-8") as f:
        json.dump(merged, f)
    return merged


if __name__ == "__main__":
    main()
