"""Tests for the draft simulation's scripts."""

import numpy as np

import extract
import report
import sim
import winmodel
from pickmodel import FEATURES, features, pool_state

HEADER = (
    "expansion,event_type,draft_id,draft_time,rank,event_match_wins,event_match_losses,"
    "pack_number,pick_number,pick,pick_2,pick_maindeck_rate,pick_sideboard_in_rate,"
    'pack_card_A,"pack_card_B, the Second",pack_card_C,pool_A,"pool_B, the Second",pool_C,'
    "user_n_games_bucket,user_game_win_rate_bucket"
)


def _row(draft, pack, pick, taken, main, pack_counts, pool_counts):
    name = f'"{taken}"' if "," in taken else taken
    return (
        f"X,PremierDraft,{draft},t,gold,3,2,{pack},{pick},{name},,{main},0,"
        + ",".join(map(str, pack_counts + pool_counts))
        + ",50,0.56"
    )


def _lines():
    return [
        HEADER,
        _row("d1", 0, 0, "A", 1.0, [1, 1, 1], [0, 0, 0]),
        _row("d1", 0, 1, "B, the Second", 0.2, [0, 1, 1], [1, 0, 0]),
        _row("d2", 0, 0, "C", 0.9, [2, 0, 1], [0, 0, 0]),
    ]


def test_extract_keeps_opened_packs_decks_and_sampled_picks():
    data = extract.extract(_lines(), pick_share=1.0)
    assert data["cards"] == ["A", "B, the Second", "C"]
    assert data["packs"] == [[0, 1, 2], [0, 0, 2]]  # first picks only
    d1, d2 = data["drafts"]
    assert (d1["wins"], d1["losses"], d1["skill"], d1["games"]) == (3.0, 2.0, 0.56, 50.0)
    assert d1["taken"] == [0, 1] and d1["main"] == [0]
    assert d2["main"] == [2]
    assert data["picks"][1] == [1, 2, 1, [1, 2], [0]]


def test_extract_parts_cover_every_draft_once():
    whole = extract.extract(_lines(), pick_share=0.0)
    parts = [extract.extract(_lines(), pick_share=0.0, part=k, parts=3) for k in range(3)]
    ids = sorted(d["id"] for p in parts for d in p["drafts"])
    assert ids == sorted(d["id"] for d in whole["drafts"])
    assert sum(len(p["packs"]) for p in parts) == len(whole["packs"])
    assert extract.extract(_lines(), pick_share=0.0)["picks"] == []


class FakeTable:
    """Six cards: 0-1 white, 2-3 blue, 4 colorless, 5 a land."""

    def __init__(self):
        self.names = list("abcdef")
        self.z = np.array([1.0, 0.0, 0.5, -1.0, 0.2, 0.0])
        self.ata_z = np.zeros(6)
        self.is_land = np.array([0, 0, 0, 0, 0, 1], bool)
        self.mask = np.array([1, 1, 2, 2, 0, 0])
        self.color_bits = np.array([[(m >> k) & 1 for k in range(5)] for m in self.mask], bool)
        self.colorless = (self.mask == 0) & ~self.is_land


def test_pick_features_follow_the_pool():
    t = FakeTable()
    share, top2 = pool_state(t, [0, 1, 0, 5])
    assert share[0] == 1.0 and share[1] == 0.0 and top2[0]
    rows = features(t, np.array([1, 2, 4]), share, top2, 21)
    f = dict(zip(FEATURES, rows.T))
    assert list(f["color_share"]) == [1.0, 0.0, 0.0]
    assert list(f["colorless"]) == [0.0, 0.0, 1.0]
    assert list(f["rating*t"]) == [0.0, 0.25, 0.1]
    empty_share, none = pool_state(t, [])
    assert none is None and not empty_share.any()


class TakeFirst:
    def pick(self, pack, pool, pack_no, pick_no):
        return pack[0]


class TakeLast:
    def pick(self, pack, pool, pack_no, pick_no):
        return pack[-1]


def test_pods_repeat_and_deal_whole_packs():
    t = FakeTable()
    rng = np.random.default_rng(0)
    packs = [list(rng.integers(0, 6, 4)) for _ in range(40)]
    w = np.zeros(len(FEATURES))
    w[0] = 1.0
    pools = sim.run_pod(7, 1, packs, t, w, TakeFirst())
    a = pools[0]
    assert pools == sim.run_pod(7, 1, packs, t, w, TakeFirst())
    assert len(pools) == sim.SEATS and all(len(p) == sim.ROUNDS * 4 for p in pools)
    assert a != sim.run_pod(8, 1, packs, t, w, TakeFirst())[0]
    # Another advisor in seat 0 opens the same first pack.
    b = sim.run_pod(7, 1, packs, t, w, TakeLast())[0]
    dealt = np.random.default_rng([1, 7]).choice(len(packs), 24, replace=False)[0]
    assert a[0] == packs[dealt][0] and b[0] == packs[dealt][-1]


def test_logistic_recovers_a_known_slope():
    rng = np.random.default_rng(1)
    x = rng.normal(size=4000)
    games = np.full(4000, 6.0)
    wins = rng.binomial(6, 1 / (1 + np.exp(-(0.2 + 0.8 * x)))).astype(float)
    w, se = winmodel.logistic(np.column_stack([np.ones(4000), x]), wins, games)
    assert abs(w[0] - 0.2) < 4 * se[0] and abs(w[1] - 0.8) < 4 * se[1]


def test_compare_pairs_pods():
    mean_base, mean_arm, diff, se, n = report.compare({1: 50.0, 2: 52.0, 3: 99.0}, {1: 51.0, 2: 54.0})
    assert (mean_base, mean_arm, diff, n) == (51.0, 52.5, 1.5, 2)
    assert se > 0
