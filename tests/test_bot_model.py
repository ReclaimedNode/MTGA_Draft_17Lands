"""Tests for the Quick Draft bot model (src/advisor/bot_model.py)."""

import csv
import gzip
import os
import random

import numpy as np
import pytest

from src import constants
from src.advisor import bot_model as bm
from src.advisor.bot_model import BotModel, evaluate, fit, rounds_from_draft
from src.advisor.engine import DraftAdvisor
from src.dataset import Dataset
from src.set_metrics import SetMetrics

DATA = os.path.join(os.path.dirname(__file__), "data", "MKM_PremierDraft_Data_2024_5_3.json")


def simulate_rounds(true, n, rng, pack_size=13):
    cards = list(true)
    rounds = []
    for _ in range(n):
        pack = rng.sample(cards, pack_size)
        left, gone = list(pack), []
        for _ in range(bm.OTHER_SEATS):
            w = np.exp([true[c] for c in left])
            w /= w.sum()
            pick = left[rng.choices(range(len(left)), weights=w)[0]]
            left.remove(pick)
            gone.append(pick)
        rounds.append((1, 1, pack, gone))
    return rounds


def test_rounds_from_draft_finds_what_the_bots_took():
    picks = [(1, 1, "a", list("abcdefghijklmn")), (1, 9, "x", list("bdfhjl"))]
    [(pack, pick, before, gone)] = list(rounds_from_draft(picks))
    assert (pack, pick) == (1, 1)
    assert "a" not in before and len(before) == 13
    assert sorted(gone) == list("cegikmn")


def test_rounds_from_draft_skips_inconsistent_packs():
    # 9 picks later should leave 6 cards; a mismatch means the data is off.
    picks = [(1, 1, "a", list("abcdefghijklmn")), (1, 9, "x", list("bdfhjlz"))]
    assert list(rounds_from_draft(picks)) == []


def test_fit_recovers_simulated_bot_preferences():
    rng = random.Random(0)
    np.random.seed(0)
    true = {f"c{i}": float(np.random.normal(0, 1.2)) for i in range(120)}
    model = fit(simulate_rounds(true, 6000, rng), iterations=300)
    est = [model.score(c) for c in true]
    assert np.corrcoef(est, list(true.values()))[0, 1] > 0.95


def test_prior_keeps_rarely_seen_cards_sensible():
    rng = random.Random(1)
    np.random.seed(1)
    true = {f"c{i}": float(np.random.normal(0, 1.0)) for i in range(60)}
    true["bomb"] = 4.0  # never seen by the bots
    seen = {k: v for k, v in true.items() if k != "bomb"}
    rounds = simulate_rounds(seen, 2000, rng)
    without = fit(rounds, iterations=200)
    with_prior = fit(rounds, iterations=200, prior={"bomb": 3.0})
    assert with_prior.score("bomb") > without.score("bomb") + 2.0


def test_model_beats_flat_on_held_out_rounds():
    rng = random.Random(2)
    np.random.seed(2)
    true = {f"c{i}": float(np.random.normal(0, 1.5)) for i in range(100)}
    model = fit(simulate_rounds(true, 4000, rng), iterations=300)
    test = simulate_rounds(true, 800, rng)
    ours = evaluate(test, lambda pk, b: model.survival(b))
    flat = evaluate(test, lambda pk, b: BotModel({}).survival(b))
    assert ours["log_loss"] < flat["log_loss"] - 0.05
    assert ours["accuracy"] > flat["accuracy"]


def test_wheel_chance_and_persistence(tmp_path, monkeypatch):
    model = BotModel({"good": 2.0, "bad": -2.0, "mid": 0.0}, {"set": "TST"})
    pack = ["good", "bad", "mid"] + [f"x{i}" for i in range(8)]
    assert model.wheel_chance(pack, "bad", "good") > model.wheel_chance(pack, "mid", "good")
    assert model.wheel_chance(pack, "good", "good") == 0.0
    assert model.wheel_chance(pack[:8], "bad", "good") == 0.0  # too small to come back
    monkeypatch.setattr(constants, "SETS_FOLDER", str(tmp_path))
    path = BotModel.path_for("tst")
    model.save(path)
    loaded = BotModel.load("TST")
    assert loaded.scores == model.scores and loaded.meta["set"] == "TST"
    assert BotModel.load("NONE") is None


def test_read_dump_rounds(tmp_path):
    names = list("abcdefghijklmnop")
    path = tmp_path / "dump.csv.gz"
    header = ["draft_id", "pack_number", "pick_number", "pick"] + [f"pack_card_{n}" for n in names]
    rng = random.Random(3)
    with gzip.open(path, "wt", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        for d in range(30):
            pack = rng.sample(names, 14)
            first = list(pack)
            you = first[0]
            w.writerow([f"d{d}", 0, 0, you] + [first.count(n) for n in names])
            later = list(first)
            later.remove(you)
            for _ in range(7):
                later.remove(rng.choice(later))
            w.writerow([f"d{d}", 0, 8, later[0]] + [later.count(n) for n in names])
    train, test = bm.read_dump_rounds(str(path))
    assert len(train) + len(test) == 30
    assert all(len(g) == 7 for _, _, _, g in train + test)


def test_advisor_uses_bot_model_for_wheel_chance():
    ds = Dataset()
    ds.open_file(DATA)
    metrics = SetMetrics(ds)
    cards = [c for c in {c["name"]: c for c in ds.get_card_ratings().values()}.values()
             if c["deck_colors"]["All Decks"]["gihwr"] > 0][:14]
    scores = {c["name"]: 0.0 for c in cards}
    sleeper = cards[-1]["name"]
    scores[sleeper] = -5.0
    recs = DraftAdvisor(metrics, [], bot_model=BotModel(scores)).evaluate_pack(cards, 1, 1)
    wheel = {r.card_name: r.wheel_chance for r in recs}
    assert wheel[sleeper] > 85
    assert max(v for k, v in wheel.items() if k != sleeper) < 60
    # Without a model, the ALSA curve is used as before.
    plain = DraftAdvisor(metrics, []).evaluate_pack(cards, 1, 1)
    assert {r.card_name for r in plain} == set(wheel)
