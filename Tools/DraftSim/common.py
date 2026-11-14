"""Card tables shared by the simulation's scripts."""

import gzip
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
COLORS = "WUBRG"
# Variance of one game's result, in win-rate points squared (50% x 50%).
GAME_VARIANCE = 2500.0


def load_app(src, dataset, set_code="", lens=False, lens_off="key,flex", params=()):
    """The app from `src`, through the replay harness's loader."""
    sys.path.insert(0, os.path.abspath(src))
    sys.path.insert(0, os.path.join(HERE, "..", "AdvisorReplay"))
    import replay

    app = replay.App(
        dataset, lens=lens, set_code=set_code, lens_off=lens_off, lens_params=params if lens else ()
    )
    if params and not lens:
        replay.set_lens_params(params)
    return app


def load_json(path):
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as f:
        return json.load(f)


class Table:
    """Per-card arrays, indexed like the dump's card list."""

    MIN_PAIR_GAMES = 50

    def __init__(self, app, names):
        from src.advisor.archetype_lens import PAIRS, castable_pairs

        self.names = names
        self.pairs = list(PAIRS)
        n, c = len(names), app.constants
        self.card = [None] * n
        self.index = {}
        mean, std = app.metrics.get_metrics("All Decks", "gihwr")
        self.mean, self.std = (mean or 54.0), (std or 4.0)
        self.rated = np.zeros(n, bool)
        self.z = np.full(n, -2.0)
        ata = np.full(n, np.nan)
        self.mask = np.zeros(n, np.int64)
        self.is_land = np.zeros(n, bool)
        self.castable = np.zeros((n, len(PAIRS)), bool)
        gain = np.zeros((n, len(PAIRS)))
        games = np.zeros((n, len(PAIRS)))
        for i, name in enumerate(names):
            found = app.cards([name])
            if not found:
                continue
            card = found[0]
            self.card[i] = card
            self.index[card[c.DATA_FIELD_NAME]] = i
            stats = card.get("deck_colors", {})
            overall = float(stats.get("All Decks", {}).get("gihwr") or 0.0)
            if overall > 0:
                self.rated[i] = True
                self.z[i] = (overall - self.mean) / self.std
            a = float(stats.get("All Decks", {}).get("ata") or 0.0)
            if a > 0:
                ata[i] = a
            for col in card.get("colors", []):
                if col in COLORS:
                    self.mask[i] |= 1 << COLORS.index(col)
            self.is_land[i] = "Land" in card.get("types", [])
            can = set(castable_pairs(card))
            for p, pair in enumerate(PAIRS):
                self.castable[i, p] = pair in can
                s = stats.get(pair, {}) or {}
                wr = float(s.get("gihwr") or 0.0)
                g = int(s.get("samples") or s.get("gih") or 0)
                if overall > 0 and wr > 0 and g >= self.MIN_PAIR_GAMES and pair in can:
                    gain[i, p] = wr - overall
                    games[i, p] = g
        ok = ~np.isnan(ata)
        self.ata_z = np.zeros(n)
        if ok.any():
            self.ata_z[ok] = -(ata[ok] - ata[ok].mean()) / (ata[ok].std() or 1.0)
            self.ata_z[~ok] = self.ata_z[ok].min()
        self.colorless = (self.mask == 0) & ~self.is_land
        self.color_bits = np.array([[(m >> k) & 1 for k in range(5)] for m in self.mask], bool)
        self.pair_bits = np.array(
            [[col in pair for col in COLORS] for pair in PAIRS], bool
        )

        # A card's fit in a pair: its gain there less the pair's level (the
        # games-weighted mean gain of the pair's cards), shrunk for sample size
        # by how much true fits vary (empirical Bayes), in SDs of win rate.
        self.pair_games = games
        level = (gain * games).sum(0) / np.maximum(1.0, games.sum(0))
        raw = np.where(games > 0, gain - level, 0.0)
        big = games >= 200
        noise = GAME_VARIANCE / np.maximum(1.0, games)
        self.tau2 = float(max(0.25, (raw[big] ** 2).mean() - noise[big].mean())) if big.any() else 1.0
        self.level = level
        self.fit = raw * self.tau2 / (self.tau2 + noise) / self.std
        self.fit[games == 0] = 0.0

    def deck_pair(self, spells):
        """Index of the pair made by the two colors most of the spells have."""
        counts = self.color_bits[spells].sum(0).astype(float)
        counts += np.arange(5, 0, -1) * 1e-6  # ties: WUBRG order
        a, b = sorted(np.argsort(-counts)[:2])
        return self.pairs.index(COLORS[a] + COLORS[b]) if COLORS[a] + COLORS[b] in self.pairs else 0

    def deck_features(self, spells):
        """(pair index, mean rating, mean fit, share of spells off the pair)."""
        spells = np.asarray(spells, int)
        pair = self.deck_pair(spells)
        rated = self.rated[spells]
        quality = float(self.z[spells][rated].mean()) if rated.any() else -1.0
        can = self.castable[spells, pair]
        fit = float((self.fit[spells, pair] * can).sum() / len(spells))
        return pair, quality, fit, float(1.0 - can.mean())
