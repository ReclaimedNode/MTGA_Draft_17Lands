"""Tests for the Archetype Lens (src/advisor/archetype_lens.py)."""

import json
import os

import pytest

from src import constants
from src.advisor import archetype_lens as al
from src.advisor.archetype_lens import (
    PAIRS,
    ArchetypeLens,
    ArchetypeSheet,
    castable_pairs,
    make_lens_factory,
)
from src.advisor.engine import DraftAdvisor
from src.dataset import Dataset
from src.set_metrics import SetMetrics

DATA = os.path.join(os.path.dirname(__file__), "data", "MKM_PremierDraft_Data_2024_5_3.json")


def card(name, colors, overall, pair_rates=None, samples=2000, mana_cost=None, types=None, tags=None):
    deck_colors = {constants.FILTER_OPTION_ALL_DECKS: {"gihwr": overall, "gih": samples * 5}}
    for pair, wr in (pair_rates or {}).items():
        deck_colors[pair] = {"gihwr": wr, "gih": samples}
    if mana_cost is None:
        mana_cost = "{2}" + "".join("{" + c + "}" for c in colors)
    return {
        "name": name,
        "colors": colors,
        "mana_cost": mana_cost,
        "types": types or ["Creature"],
        "cmc": 3,
        "deck_colors": deck_colors,
        "tags": tags or [],
    }


class FakeMetrics:
    def get_metrics(self, color, field):
        return 55.0, 3.0


@pytest.fixture(scope="module")
def mkm():
    ds = Dataset()
    ds.open_file(DATA)
    return ds, SetMetrics(ds)


def test_pairs_are_the_ten_two_color_pairs():
    assert len(PAIRS) == 10 and len(set(PAIRS)) == 10
    assert "UB" in PAIRS and "WG" in PAIRS


def test_castable_pairs():
    assert set(castable_pairs(card("u", ["U"], 55))) == {"WU", "UB", "UR", "UG"}
    assert castable_pairs(card("ub", ["U", "B"], 55)) == ["UB"]
    assert len(castable_pairs(card("rock", [], 55, mana_cost="{3}", types=["Artifact"]))) == 10


def test_shrunk_delta_pulls_small_samples_toward_zero():
    big = card("big", ["U"], 55.0, {"UB": 59.0}, samples=4000)
    small = card("small", ["U"], 55.0, {"UB": 59.0}, samples=100)
    assert ArchetypeSheet.shrunk_delta(big, "UB") == pytest.approx(4.0 * 4000 / 4400)
    assert ArchetypeSheet.shrunk_delta(small, "UB") == pytest.approx(4.0 * 100 / 500)
    assert ArchetypeSheet.shrunk_delta(card("none", ["U"], 55.0), "UB") == 0.0


def test_lanes_start_flat_and_follow_the_pool():
    empty = ArchetypeLens(FakeMetrics(), [])
    assert max(empty.lane_probs.values()) == pytest.approx(0.1)
    pool = [card(f"u{i}", ["U"], 57) for i in range(6)] + [card(f"b{i}", ["B"], 57) for i in range(6)]
    lens = ArchetypeLens(FakeMetrics(), pool)
    assert lens.top_lanes(1)[0][0] == "UB"
    assert sum(lens.lane_probs.values()) == pytest.approx(1.0)


def test_expected_delta_credits_overperformers_in_likely_lanes():
    pool = [card(f"u{i}", ["U"], 57) for i in range(6)] + [card(f"b{i}", ["B"], 57) for i in range(6)]
    lens = ArchetypeLens(FakeMetrics(), pool)
    gem = card("gem", ["B"], 54.0, {"UB": 59.0, "BR": 54.0, "WB": 54.0, "BG": 54.0})
    flop = card("flop", ["B"], 54.0, {"UB": 50.0, "BR": 54.0, "WB": 54.0, "BG": 54.0})
    gain, lane = lens.expected_delta(gem)
    assert gain > 2.0 and lane == "UB"
    assert lens.expected_delta(flop)[0] < -2.0


def test_off_lane_gold_card_gets_reduced_credit():
    pool = [card(f"u{i}", ["U"], 57) for i in range(6)] + [card(f"b{i}", ["B"], 57) for i in range(6)]
    lens = ArchetypeLens(FakeMetrics(), pool)
    gold = card("rw", ["R", "W"], 54.0, {"WR": 60.0})
    gain, _ = lens.expected_delta(gold)
    assert 0 <= gain < ArchetypeSheet.shrunk_delta(gold, "WR") * 0.5


def test_key_card_bonus_shrinks_as_you_collect_key_cards():
    sheet = ArchetypeSheet({p: {"key_cards": {}, "themes": []} for p in PAIRS})
    sheet.pairs["UB"]["key_cards"] = {f"k{i}": 3.0 for i in range(6)}
    base = [card(f"u{i}", ["U"], 57) for i in range(6)] + [card(f"b{i}", ["B"], 57) for i in range(6)]
    candidate = card("k5", ["B"], 55)
    fresh = ArchetypeLens(FakeMetrics(), base, sheet).key_card_bonus(candidate)
    stocked_pool = base + [card(f"k{i}", ["B"], 55) for i in range(4)]
    stocked = ArchetypeLens(FakeMetrics(), stocked_pool, sheet).key_card_bonus(candidate)
    assert fresh[0] > 1.0 and "key card" in fresh[1]
    assert stocked[0] == pytest.approx(1.0)


def test_flexibility_only_in_early_pack_one():
    lens = ArchetypeLens(FakeMetrics(), [card("u", ["U"], 57)])
    mono = card("m", ["G"], 55)
    gold = card("g", ["R", "W"], 55)
    mean_mass = (lens.castable_mass(mono) + lens.castable_mass(gold)) / 2
    assert lens.flexibility_mult(mono, 1, 2, mean_mass) > 1.0 > lens.flexibility_mult(gold, 1, 2, mean_mass)
    assert lens.flexibility_mult(mono, 2, 2, mean_mass) == 1.0
    assert lens.flexibility_mult(mono, 1, 12, mean_mass) == 1.0


def test_sheet_build_on_real_data(mkm):
    ds, _ = mkm
    sheet = ArchetypeSheet.build(ds.get_card_ratings())
    assert set(sheet.pairs) == set(PAIRS)
    assert sum(len(e["key_cards"]) for e in sheet.pairs.values()) > 30
    for pair, entry in sheet.pairs.items():
        for name, delta in entry["key_cards"].items():
            assert delta >= ArchetypeSheet.MIN_DELTA


def test_user_overrides(tmp_path, monkeypatch):
    monkeypatch.setattr(constants, "SETS_FOLDER", str(tmp_path))
    folder = tmp_path / al.SHEET_FOLDER_NAME
    folder.mkdir()
    (folder / "TST.json").write_text(
        json.dumps({"BU": {"name": "Self-mill", "key_cards": ["Mine"], "themes": ["synergy_graveyard"]},
                    "RG": {"replace": True, "key_cards": ["Only"]}})
    )
    sheet = ArchetypeSheet({p: {"key_cards": {"Auto": 1.5}, "themes": []} for p in PAIRS})
    assert sheet.apply_overrides("TST")
    assert sheet.key_delta("UB", "Mine") == 2.0 and sheet.key_delta("UB", "Auto") == 1.5
    assert sheet.pairs["UB"]["name"] == "Self-mill"
    assert sheet.themes("UB") == ["synergy_graveyard"]
    assert sheet.pairs["RG"]["key_cards"] == {"Only": 2.0}
    path = sheet.write_sheet_template("TST")
    assert os.path.exists(path) and path.endswith("TST.auto.json")


def test_advisor_without_lens_is_unchanged(mkm):
    ds, metrics = mkm
    cards = [c for c in {c["name"]: c for c in ds.get_card_ratings().values()}.values()
             if c["deck_colors"]["All Decks"]["gihwr"] > 0]
    pool, pack = cards[:12], cards[40:54]
    a = DraftAdvisor(metrics, pool).evaluate_pack(pack, 3, 2)
    b = DraftAdvisor(metrics, pool, lens_factory=None).evaluate_pack(pack, 3, 2)
    assert [(r.card_name, r.contextual_score) for r in a] == [(r.card_name, r.contextual_score) for r in b]


def test_advisor_with_lens_runs_on_real_data(mkm):
    ds, metrics = mkm
    factory = make_lens_factory(ds, "MKM")
    cards = [c for c in {c["name"]: c for c in ds.get_card_ratings().values()}.values()
             if c["deck_colors"]["All Decks"]["gihwr"] > 0]
    for n_pool, pick, pack_no in [(0, 1, 1), (5, 6, 1), (20, 6, 2), (35, 7, 3)]:
        recs = DraftAdvisor(metrics, cards[:n_pool], lens_factory=factory).evaluate_pack(
            cards[60:74], pick, pack_no
        )
        assert len(recs) == 14
        assert all(r.contextual_score >= 0 for r in recs)


def test_make_lens_factory_without_data():
    assert make_lens_factory(Dataset(), "X") is None
