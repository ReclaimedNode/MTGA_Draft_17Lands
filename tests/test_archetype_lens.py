"""Tests for the Archetype Lens (src/advisor/archetype_lens.py)."""

import json
import os

import pytest


@pytest.fixture(autouse=True)
def all_pieces_on():
    """Most tests exercise every piece; the app's default switches some off."""
    saved = ArchetypeLens.DISABLED
    ArchetypeLens.DISABLED = frozenset()
    yield
    ArchetypeLens.DISABLED = saved

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


def test_defaults_switch_off_key_and_flex():
    assert ArchetypeLens.DEFAULT_DISABLED == frozenset({"key", "flex"})


# --- Fit and deck value ("value" mode) -------------------------------------


def _sheet(cards):
    return ArchetypeSheet.build({str(i): c for i, c in enumerate(cards)})


def test_fit_is_the_gain_less_the_pairs_level():
    # Every UB card does 3 points better in UB: that's the pair's level, not fit.
    cards = [card(f"c{i}", ["U"], 55.0, {"UB": 58.0}, samples=50000) for i in range(6)]
    star = card("star", ["U"], 55.0, {"UB": 62.0}, samples=50000)
    sheet = _sheet(cards + [star])
    assert sheet.levels["UB"] == pytest.approx(3.0 + 4.0 / 7)
    assert sheet.fit(cards[0], "UB") < 0 < sheet.fit(star, "UB")
    assert sheet.fit(star, "UB") < 62.0 - 55.0 - sheet.levels["UB"]  # shrunk
    assert sheet.fit(star, "WU") == 0.0  # no rate there


def test_fit_shrinks_small_samples_harder():
    filler = [card(f"c{i}", ["U"], 55.0, {"UB": 55.0}, samples=50000) for i in range(8)]
    big = card("big", ["U"], 55.0, {"UB": 60.0}, samples=20000)
    small = card("small", ["U"], 55.0, {"UB": 60.0}, samples=100)
    sheet = _sheet(filler + [big, small])
    assert 0 < sheet.fit(small, "UB") < sheet.fit(big, "UB")
    assert sheet.fit(card("tiny", ["U"], 55.0, {"UB": 70.0}, samples=10), "UB") == 0.0


def test_deck_value_first_pick_prefers_the_card_that_fits_more_lanes():
    lens = ArchetypeLens(FakeMetrics(), [])
    mono = lens.deck_value(card("mono", ["U"], 58.0))[0]
    gold = lens.deck_value(card("gold", ["U", "B"], 58.0))[0]
    rock = lens.deck_value(card("rock", [], 58.0, mana_cost="{3}", types=["Artifact"]))[0]
    assert rock > mono > gold
    # A card that goes into every lane's deck scores its own worth: +1 SD.
    assert rock == pytest.approx(1.0 + ArchetypeLens.VALUE_TIEBREAK, abs=1e-6)


def test_deck_value_follows_the_pool():
    pool = [card(f"u{i}", ["U"], 58.0) for i in range(6)] + [
        card(f"b{i}", ["B"], 58.0) for i in range(6)
    ]
    lens = ArchetypeLens(FakeMetrics(), pool)
    on = lens.deck_value(card("on", ["B"], 57.0))
    off = lens.deck_value(card("off", ["R"], 61.0))
    assert on[0] > off[0]
    assert on[1] == "UB"
    # Off-lane cards still rank by win rate among themselves.
    assert off[0] > lens.deck_value(card("off2", ["R"], 56.0))[0]


def test_deck_value_counts_fit_in_the_lane():
    filler = [card(f"c{i}", ["U"], 55.0, {"UB": 55.0}, samples=50000) for i in range(8)]
    fits = card("fits", ["B"], 56.0, {"UB": 60.0}, samples=20000)
    plain = card("plain", ["B"], 56.5, {"UB": 56.5}, samples=20000)
    sheet = _sheet(filler + [fits, plain])
    pool = [card(f"u{i}", ["U"], 58.0) for i in range(6)] + [
        card(f"b{i}", ["B"], 58.0) for i in range(6)
    ]
    lens = ArchetypeLens(FakeMetrics(), pool, sheet=sheet)
    points, lane, fit = lens.deck_value(fits)
    assert lane == "UB" and fit > 0
    assert points > lens.deck_value(plain)[0]


def test_deck_value_measures_a_card_against_the_one_it_pushes_out():
    pool = [card(f"u{i}", ["U"], 58.0) for i in range(ArchetypeLens.DECK_SPELLS)]
    lens = ArchetypeLens(FakeMetrics(), pool)
    worse = lens.deck_value(card("worse", ["U"], 57.0))[0]
    better = lens.deck_value(card("better", ["U"], 61.0))[0]
    # 57 doesn't make a deck of 58s; 61 replaces one, for a gain of 1 SD.
    assert worse == pytest.approx(ArchetypeLens.REPLACEMENT, abs=0.1)
    assert better == pytest.approx(ArchetypeLens.REPLACEMENT + 1.0, abs=0.1)
    boosted = lens.deck_value(card("better", ["U"], 61.0), boost=1.25)[0]
    assert boosted > better
    assert lens.deck_value(card("worse", ["U"], 57.0), boost=1.5)[0] == pytest.approx(worse)


def test_unrated_cards_score_below_rated_ones():
    lens = ArchetypeLens(FakeMetrics(), [])
    assert lens.deck_value(card("unrated", ["U"], 0.0))[0] < lens.deck_value(card("bad", ["U"], 45.0))[0]


def test_advisor_value_mode_keeps_the_lane_and_blend_mode_is_still_there(mkm, monkeypatch):
    ds, metrics = mkm
    factory = make_lens_factory(ds, "MKM")
    cards = list(ds.get_card_ratings().values())
    rated = [c for c in cards if c["deck_colors"]["All Decks"].get("gihwr", 0) > 0]
    blue = [c for c in rated if c.get("colors") == ["U"]][:8]
    black = [c for c in rated if c.get("colors") == ["B"]][:8]
    red = sorted(
        (c for c in rated if c.get("colors") == ["R"]),
        key=lambda c: -c["deck_colors"]["All Decks"]["gihwr"],
    )[:3]
    pack = red + [c for c in rated if c.get("colors") in (["U"], ["B"])][16:22]

    monkeypatch.setattr(ArchetypeLens, "MODE", "value")
    value = DraftAdvisor(metrics, blue + black, lens_factory=factory).evaluate_pack(pack, 3, 2)
    assert len(value) == len(pack)
    top = next(c for c in pack if c["name"] == value[0].card_name)
    assert top.get("colors") in (["U"], ["B"])

    monkeypatch.setattr(ArchetypeLens, "MODE", "blend")
    blend = DraftAdvisor(metrics, blue + black, lens_factory=factory).evaluate_pack(pack, 3, 2)
    assert len(blend) == len(pack)
    assert [r.contextual_score for r in blend] != [r.contextual_score for r in value]
