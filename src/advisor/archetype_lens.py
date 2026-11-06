"""
src/advisor/archetype_lens.py
The Archetype Lens: color-pair awareness for the draft advisor.

Three pieces, all built from the 17Lands data the app already downloads:

1. Lane probabilities and archetype overperformers.
   The base advisor blends in a card's win rate for one archetype once a
   two-color lane is identified. The lens instead keeps a probability for
   each of the ten color pairs from the first pick on, and credits a card
   with its sample-shrunk win-rate gain in each pair it can be cast in,
   weighted by how likely you are to end up there.

2. The archetype sheet.
   For each pair, the cards that overperform there the most ("key cards")
   and the card tags most over-represented among them ("themes"). Built
   automatically per set; a JSON file in Sets/Archetypes/<SET>.json
   overrides or extends it (see write_sheet_template). A key card for a
   likely lane gets a bonus that shrinks as you collect more of them.

3. Lane flexibility.
   In pack 1, cards that stay playable across the lanes you're likely to
   end up in score slightly higher than cards that commit you early.

Everything here is optional: DraftAdvisor behaves exactly as before when
no lens is passed in.
"""

import json
import logging
import math
import os
from collections import Counter
from typing import Dict, List, Optional, Tuple

from src import constants
from src.mana_cost import off_color_requirements
from src.utils import normalize_color_string

logger = logging.getLogger(__name__)

PAIRS = [
    normalize_color_string(a + b)
    for i, a in enumerate(constants.CARD_COLORS)
    for b in constants.CARD_COLORS[i + 1 :]
]

ALL_DECKS = constants.FILTER_OPTION_ALL_DECKS
SHEET_FOLDER_NAME = "Archetypes"


def _stats(card: Dict, deck: str) -> Dict:
    return card.get(constants.DATA_FIELD_DECK_COLORS, {}).get(deck, {}) or {}


def _gihwr(card: Dict, deck: str = ALL_DECKS) -> float:
    try:
        return float(_stats(card, deck).get(constants.DATA_FIELD_GIHWR, 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _samples(card: Dict, deck: str) -> int:
    """Games behind a card's GIH WR in a deck: 'samples' if the dataset has it, else 'gih'."""
    s = _stats(card, deck)
    try:
        return int(s.get("samples") or s.get(constants.DATA_FIELD_GIH) or 0)
    except (TypeError, ValueError):
        return 0


def castable_pairs(card: Dict) -> List[str]:
    """The color pairs whose two colors can pay every colored symbol of the card."""
    if "Land" in card.get(constants.DATA_FIELD_TYPES, []) and not card.get(
        constants.DATA_FIELD_COLORS
    ):
        return list(PAIRS)
    return [p for p in PAIRS if not off_color_requirements(card, list(p))]


class ArchetypeSheet:
    """Per-pair key cards and themes for one set."""

    MIN_SAMPLES = 200
    MIN_DELTA = 1.0  # win-rate points
    KEY_CARDS_PER_PAIR = 10
    THEMES_PER_PAIR = 3
    SHRINK_K = 400  # games; a delta from K games counts half

    def __init__(self, pairs: Optional[Dict[str, Dict]] = None):
        self.pairs: Dict[str, Dict] = pairs or {p: {} for p in PAIRS}

    @classmethod
    def shrunk_delta(cls, card: Dict, pair: str) -> float:
        """Pair GIH WR minus overall GIH WR, pulled toward 0 for small samples."""
        overall, in_pair = _gihwr(card), _gihwr(card, pair)
        n = _samples(card, pair)
        if overall <= 0 or in_pair <= 0 or n <= 0:
            return 0.0
        return (in_pair - overall) * n / (n + cls.SHRINK_K)

    @classmethod
    def build(cls, card_ratings: Dict, set_code: str = "") -> "ArchetypeSheet":
        unique = {}
        for card in (card_ratings or {}).values():
            name = card.get(constants.DATA_FIELD_NAME)
            if name and name not in unique:
                unique[name] = card

        overall_tags = Counter()
        for card in unique.values():
            overall_tags.update(set(card.get("tags", [])))
        total = max(1, len(unique))

        pairs = {}
        for pair in PAIRS:
            scored = []
            for name, card in unique.items():
                if _samples(card, pair) < cls.MIN_SAMPLES:
                    continue
                if pair not in castable_pairs(card):
                    continue
                d = cls.shrunk_delta(card, pair)
                if d >= cls.MIN_DELTA:
                    scored.append((d, name, card))
            scored.sort(key=lambda t: -t[0])
            key = scored[: cls.KEY_CARDS_PER_PAIR]

            key_tags = Counter()
            for _, _, card in key:
                key_tags.update(set(card.get("tags", [])))
            themes = []
            if key:
                lifts = []
                for tag, count in key_tags.items():
                    share_key = count / len(key)
                    share_all = overall_tags[tag] / total
                    if count >= 2 and share_all > 0:
                        lifts.append((share_key / share_all, tag))
                lifts.sort(reverse=True)
                themes = [t for lift, t in lifts[: cls.THEMES_PER_PAIR] if lift > 1.2]

            pairs[pair] = {
                "key_cards": {name: round(d, 2) for d, name, _ in key},
                "themes": themes,
                "source": "auto",
            }

        sheet = cls(pairs)
        if set_code:
            sheet.apply_overrides(set_code)
        return sheet

    # --- User overrides -------------------------------------------------

    @staticmethod
    def sheet_path(set_code: str) -> str:
        safe = "".join(ch for ch in set_code.upper() if ch.isalnum())
        return os.path.join(constants.SETS_FOLDER, SHEET_FOLDER_NAME, f"{safe}.json")

    def apply_overrides(self, set_code: str) -> bool:
        """Merge Sets/Archetypes/<SET>.json into the sheet. Returns True if one was found.

        Format (every field optional):
        {
          "UB": {"name": "Self-mill", "key_cards": ["Card A", "Card B"],
                 "themes": ["synergy_graveyard"], "replace": false},
          ...
        }
        Listed key cards get a +2.0 delta unless the auto sheet already rates
        them higher. "replace": true drops the auto key cards for that pair.
        """
        path = self.sheet_path(set_code)
        if not os.path.exists(path):
            return False
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"Archetype sheet {path} unreadable: {e}")
            return False
        for raw_pair, entry in (data or {}).items():
            pair = normalize_color_string(raw_pair)
            if pair not in PAIRS or not isinstance(entry, dict):
                continue
            current = self.pairs.setdefault(pair, {"key_cards": {}, "themes": []})
            if entry.get("replace"):
                current["key_cards"] = {}
                current["themes"] = []
            for name in entry.get("key_cards", []):
                current["key_cards"][name] = max(
                    2.0, current["key_cards"].get(name, 0.0)
                )
            for theme in entry.get("themes", []):
                if theme not in current["themes"]:
                    current["themes"].append(theme)
            if entry.get("name"):
                current["name"] = entry["name"]
            current["source"] = "user" if entry.get("replace") else "auto+user"
        return True

    def write_sheet_template(self, set_code: str) -> str:
        """Write the auto sheet to Sets/Archetypes/<SET>.auto.json for the user to edit."""
        path = self.sheet_path(set_code).replace(".json", ".auto.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        out = {
            pair: {
                "name": entry.get("name", ""),
                "key_cards": list(entry.get("key_cards", {})),
                "themes": entry.get("themes", []),
                "replace": False,
            }
            for pair, entry in self.pairs.items()
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
        return path

    def key_delta(self, pair: str, name: str) -> float:
        return float(self.pairs.get(pair, {}).get("key_cards", {}).get(name, 0.0))

    def themes(self, pair: str) -> List[str]:
        return list(self.pairs.get(pair, {}).get("themes", []))


class ArchetypeLens:
    """Lane probabilities for one pool, and the card adjustments built on them."""

    # Pieces that can be switched off: "delta" (#1), "key" (#2), "flex" (#3).
    # Off by default: key and flex. Replaying 2,000 FRA drafts (Nov 2026),
    # #1 alone matched drafters' picks as well as all three (+0.2 top-1 vs
    # the plain advisor) with the best regret; #2 and #3 added nothing.
    DEFAULT_DISABLED: frozenset = frozenset({"key", "flex"})
    DISABLED: frozenset = DEFAULT_DISABLED
    # Lane model
    PRIOR_WEIGHT = 0.15
    DELTA_TIP = 0.25  # how much the pair's overall deck win rate matters
    TEMP_START = 2.5  # softmax temperature with an empty pool (flat)
    TEMP_END = 0.6  # by ~pick 15 the lane is mostly decided
    TEMP_PICKS = 15
    # A card's archetype credit is its gain in the lanes it can be cast in,
    # scaled down when those lanes are unlikely (mass below this).
    MASS_FULL_CREDIT = 0.3
    # Key cards (#2)
    KEY_TARGET = 4  # after this many key cards for a lane, no more bonus
    KEY_BONUS_MAX = 0.12
    THEME_BONUS_MAX = 0.05
    THEME_MIN_IN_POOL = 2
    # Flexibility (#3)
    FLEX_WEIGHT = 0.15
    FLEX_LAST_PICK = 10  # pack 1 only, fading to nothing by this pick

    def __init__(
        self,
        set_metrics,
        pool: List[Dict],
        sheet: Optional[ArchetypeSheet] = None,
        color_ratings: Optional[Dict] = None,
    ):
        self.metrics = set_metrics
        self.pool = pool or []
        self.sheet = sheet or ArchetypeSheet()
        self.global_mean, self.global_std = set_metrics.get_metrics(ALL_DECKS, "gihwr")
        if self.global_mean <= 0:
            self.global_mean = 54.0
        if self.global_std <= 0:
            self.global_std = 4.0
        self.color_ratings = {
            normalize_color_string(k): float(v)
            for k, v in (color_ratings or {}).items()
            if v
        }
        self._pairs_cache: Dict[str, List[str]] = {}
        self.lane_probs = self._lane_probabilities()
        self._pool_names = Counter(
            str(c.get(constants.DATA_FIELD_NAME, "")) for c in self.pool
        )
        self._pool_tags = Counter()
        for c in self.pool:
            self._pool_tags.update(set(c.get("tags", [])))

    # --- Lanes ----------------------------------------------------------

    def _lane_probabilities(self) -> Dict[str, float]:
        strength = {p: 0.0 for p in PAIRS}
        for card in self.pool:
            if "Land" in card.get(constants.DATA_FIELD_TYPES, []):
                continue
            pairs = self._pairs(card)
            if len(pairs) == len(PAIRS):
                continue  # colorless cards don't point anywhere
            overall = _gihwr(card)
            if overall <= 0:
                continue
            base = max(0.0, 1.0 + (overall - self.global_mean) / self.global_std)
            for pair in pairs:
                # A card points at every pair it's castable in; its pair-specific
                # gain tips the balance but must not outweigh actual commitment
                # to a second color.
                tip = self.DELTA_TIP * ArchetypeSheet.shrunk_delta(card, pair) / self.global_std
                strength[pair] += max(0.0, base + tip)

        if self.color_ratings:
            mean_deck = sum(self.color_ratings.get(p, 0) for p in PAIRS) / len(PAIRS)
            for p in PAIRS:
                if p in self.color_ratings:
                    strength[p] += self.PRIOR_WEIGHT * (self.color_ratings[p] - mean_deck)

        progress = min(1.0, len(self.pool) / self.TEMP_PICKS)
        temp = self.TEMP_START + (self.TEMP_END - self.TEMP_START) * progress
        top = max(strength.values())
        exps = {p: math.exp((s - top) / temp) for p, s in strength.items()}
        total = sum(exps.values())
        return {p: v / total for p, v in exps.items()}

    def top_lanes(self, n: int = 2) -> List[Tuple[str, float]]:
        return sorted(self.lane_probs.items(), key=lambda kv: -kv[1])[:n]

    def _pairs(self, card: Dict) -> List[str]:
        key = str(card.get(constants.DATA_FIELD_NAME, "")) or str(id(card))
        if key not in self._pairs_cache:
            self._pairs_cache[key] = castable_pairs(card)
        return self._pairs_cache[key]

    def castable_mass(self, card: Dict) -> float:
        """Probability that the card is castable in the lane you end up in."""
        return sum(self.lane_probs[p] for p in self._pairs(card))

    # --- #1: archetype overperformance ------------------------------------

    def expected_delta(self, card: Dict) -> Tuple[float, str]:
        """(expected shrunk delta over castable lanes, the lane contributing most)."""
        if "delta" in self.DISABLED:
            return 0.0, ""
        pairs = self._pairs(card)
        mass = sum(self.lane_probs[p] for p in pairs)
        if mass <= 0:
            return 0.0, ""
        best_pair, best_contrib, total = "", 0.0, 0.0
        for p in pairs:
            contrib = self.lane_probs[p] * ArchetypeSheet.shrunk_delta(card, p)
            total += contrib
            if abs(contrib) > abs(best_contrib):
                best_pair, best_contrib = p, contrib
        credit = min(1.0, mass / self.MASS_FULL_CREDIT)
        return (total / mass) * credit, best_pair

    # --- #2: key cards and themes ---------------------------------------

    def key_card_bonus(self, card: Dict) -> Tuple[float, str]:
        if "key" in self.DISABLED:
            return 1.0, ""
        name = str(card.get(constants.DATA_FIELD_NAME, ""))
        best_mult, best_reason = 1.0, ""
        for pair, prob in self.top_lanes(3):
            if pair not in self._pairs(card):
                continue
            delta = self.sheet.key_delta(pair, name)
            mult = 1.0
            reason = ""
            if delta > 0:
                have = sum(
                    1
                    for pool_name in self._pool_names
                    if self.sheet.key_delta(pair, pool_name) > 0
                )
                need = max(0.0, 1.0 - have / self.KEY_TARGET)
                strength = min(1.0, delta / 4.0)
                mult += self.KEY_BONUS_MAX * prob * need * (0.5 + 0.5 * strength)
                label = self.sheet.pairs.get(pair, {}).get("name") or pair
                reason = f"{label} key card"
            themes = set(self.sheet.themes(pair)) & set(card.get("tags", []))
            if themes:
                in_pool = max(self._pool_tags[t] for t in themes)
                if in_pool >= self.THEME_MIN_IN_POOL:
                    mult += self.THEME_BONUS_MAX * prob
                    reason = reason or f"Fits {pair} theme"
            if mult > best_mult:
                best_mult, best_reason = mult, reason
        return best_mult, best_reason

    # --- #3: flexibility --------------------------------------------------

    def flexibility_mult(
        self, card: Dict, pack: int, effective_pick: int, pack_mean_mass: float
    ) -> float:
        if "flex" in self.DISABLED or pack != 1 or effective_pick >= self.FLEX_LAST_PICK:
            return 1.0
        fade = 1.0 - (effective_pick - 1) / (self.FLEX_LAST_PICK - 1)
        mult = 1.0 + self.FLEX_WEIGHT * fade * (self.castable_mass(card) - pack_mean_mass)
        return max(0.9, min(1.1, mult))


_SHEET_CACHE: Dict[Tuple[int, int, str], ArchetypeSheet] = {}


def sheet_for(card_ratings: Dict, set_code: str = "") -> ArchetypeSheet:
    """Build (once per loaded dataset) the archetype sheet."""
    key = (id(card_ratings), len(card_ratings or {}), set_code.upper())
    if key not in _SHEET_CACHE:
        if len(_SHEET_CACHE) > 8:
            _SHEET_CACHE.clear()
        _SHEET_CACHE[key] = ArchetypeSheet.build(card_ratings, set_code)
    return _SHEET_CACHE[key]


def make_lens_factory(dataset, set_code: str = ""):
    """A DraftAdvisor lens_factory for a loaded Dataset (None if it has no ratings)."""
    card_ratings = dataset.get_card_ratings() if dataset else {}
    if not card_ratings:
        return None
    sheet = sheet_for(card_ratings, set_code)
    color_ratings = dataset.get_color_ratings()

    def factory(set_metrics, pool):
        return ArchetypeLens(set_metrics, pool, sheet=sheet, color_ratings=color_ratings)

    return factory
