"""
src/advisor/bot_model.py
A model of what Arena's Quick Draft bots pick, learned from 17Lands dumps.

In an eight-seat draft the pack you see at pick p comes back at pick p + 8.
The cards missing between those two looks are the one you took and one taken
by each of the seven other seats; in Quick Draft those seats are bots. So
17Lands' public Quick Draft dumps show, for thousands of drafts, which cards
bots took from packs and which they passed.

The model gives each card a preference score s. Bots are treated as seven
draws from the pack, each taking card c with probability
pi_c = exp(s_c) / sum(exp(s)) over the cards there, so

    P(c survives the round) = (1 - pi_c) ** 7

Scores are fitted by maximizing that likelihood on the observed rounds.
This ignores that bots may favor colors they've already picked; the
evaluation script measures how well the simple version predicts wheels.
"""

import csv
import gzip
import hashlib
import json
import logging
import math
import os
import sys
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

from src import constants

logger = logging.getLogger(__name__)

OTHER_SEATS = 7
SEATS = 8
MODEL_FOLDER_NAME = "BotModels"


# --- Extracting bot rounds from a dump ----------------------------------------


def _holdout(draft_id: str, salt: str = "bot") -> bool:
    """A fixed 20% of drafts, chosen by hash, kept out of fitting."""
    h = int(hashlib.md5((salt + draft_id).encode("utf-8")).hexdigest()[:8], 16)
    return h % 5 == 0


def rounds_from_draft(picks: Sequence[Tuple[int, int, str, List[str]]]):
    """Bot rounds in one draft.

    picks: (pack 1-based, pick 1-based, card taken, cards in the pack).
    Yields (pack, pick, before, taken_by_bots) where before is the pack after
    your pick and taken_by_bots is what was gone 8 picks later.
    """
    by_key = {(pk, pi): (taken, pack) for pk, pi, taken, pack in picks}
    for (pk, pi), (taken, pack) in sorted(by_key.items()):
        later = by_key.get((pk, pi + SEATS))
        if not later:
            continue
        before = list(pack)
        if taken in before:
            before.remove(taken)
        remaining = list(later[1])
        gone = []
        left = list(remaining)
        for name in before:
            if name in left:
                left.remove(name)
            else:
                gone.append(name)
        # Sanity: exactly one card per other seat, and nothing new appeared.
        if len(gone) != OTHER_SEATS or left:
            continue
        yield pk, pi, before, gone


def read_dump_rounds(path: str, max_drafts: int = 0, salt: str = "bot"):
    """(train_rounds, test_rounds) from a 17Lands draft dump (.csv or .csv.gz).

    Each round is (pack, pick, before, taken_by_bots). Rows must be grouped
    by draft, as 17Lands publishes them.
    """
    opener = gzip.open if path.endswith(".gz") else open
    train, test = [], []
    with opener(path, "rt", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        col = {name: i for i, name in enumerate(header)}
        pack_cols = [
            (i, c[len("pack_card_") :])
            for i, c in enumerate(header)
            if c.startswith("pack_card_")
        ]
        current, picks, n = None, [], 0
        interned = {name: sys.intern(name) for _, name in pack_cols}

        def flush():
            if current is None or not picks:
                return
            target = test if _holdout(current, salt) else train
            target.extend(rounds_from_draft(picks))

        for row in reader:
            draft_id = row[col["draft_id"]]
            if draft_id != current:
                flush()
                n += 1
                if max_drafts and n > max_drafts:
                    current, picks = None, []
                    break
                current, picks = draft_id, []
            pack = [
                interned[name]
                for i, name in pack_cols
                if row[i] not in ("", "0")
                for _ in range(int(float(row[i])))
            ]
            picks.append(
                (
                    int(row[col["pack_number"]]) + 1,
                    int(row[col["pick_number"]]) + 1,
                    row[col["pick"]],
                    pack,
                )
            )
        flush()
    return train, test


# --- The model ----------------------------------------------------------------


class BotModel:
    def __init__(self, scores: Dict[str, float], meta: Optional[Dict] = None):
        self.scores = dict(scores)
        self.meta = meta or {}
        self.default = float(np.median(list(scores.values()))) if scores else 0.0
        self.sightings = (meta or {}).get("sightings", {})

    def score(self, name: str) -> float:
        name = str(name)
        if name in self.scores:
            return self.scores[name]
        front = name.split(" // ")[0]
        return self.scores.get(front, self.default)

    def take_probs(self, before: Sequence[str]) -> List[float]:
        """Each card's chance a single bot draw takes it."""
        s = np.array([self.score(n) for n in before], dtype=float)
        if not len(s):
            return []
        e = np.exp(s - s.max())
        return list(e / e.sum())

    def survival(self, before: Sequence[str], seats: int = OTHER_SEATS) -> List[float]:
        """Each card's chance to still be in the pack after the bots' round."""
        return [(1.0 - p) ** seats for p in self.take_probs(before)]

    def wheel_chance(self, pack: Sequence[str], card: str, you_take: str) -> float:
        """Chance (0-100) that card comes back, if you take you_take now."""
        if len(pack) <= SEATS or card == you_take:
            return 0.0
        before = list(pack)
        if you_take in before:
            before.remove(you_take)
        surv = self.survival(before)
        return 100.0 * surv[before.index(card)]

    # persistence

    def to_json(self) -> Dict:
        return {"meta": self.meta, "scores": self.scores}

    @classmethod
    def from_json(cls, data: Dict) -> "BotModel":
        return cls(data.get("scores", {}), data.get("meta", {}))

    @staticmethod
    def path_for(set_code: str, event: str = "QuickDraft") -> str:
        safe = "".join(ch for ch in set_code.upper() if ch.isalnum())
        return os.path.join(
            constants.SETS_FOLDER, MODEL_FOLDER_NAME, f"{safe}_{event}.json"
        )

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_json(), f, indent=1)

    @classmethod
    def load(cls, set_code: str, event: str = "QuickDraft") -> Optional["BotModel"]:
        path = cls.path_for(set_code, event)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return cls.from_json(json.load(f))
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"Bot model {path} unreadable: {e}")
            return None


# --- Fitting ------------------------------------------------------------------


def _pad(rounds, index):
    width = max(len(b) for _, _, b, _ in rounds)
    idx = np.zeros((len(rounds), width), dtype=np.int64)
    mask = np.zeros((len(rounds), width), dtype=bool)
    y = np.zeros((len(rounds), width), dtype=float)
    for r, (_, _, before, gone) in enumerate(rounds):
        gone_left = list(gone)
        for j, name in enumerate(before):
            idx[r, j] = index[name]
            mask[r, j] = True
            if name in gone_left:
                y[r, j] = 1.0
                gone_left.remove(name)
    return idx, mask, y


def round_loglik(scores: np.ndarray, idx, mask, y, seats=OTHER_SEATS):
    """Mean Bernoulli log-likelihood of taken/survived under the model."""
    s = np.where(mask, scores[idx], -np.inf)
    s = s - s.max(axis=1, keepdims=True)
    e = np.where(mask, np.exp(s), 0.0)
    pi = e / e.sum(axis=1, keepdims=True)
    surv = np.clip((1.0 - pi) ** seats, 1e-9, 1 - 1e-9)
    ll = np.where(mask, y * np.log(1 - surv) + (1 - y) * np.log(surv), 0.0)
    return ll.sum() / mask.sum(), pi, surv


def fit(
    rounds: List,
    iterations: int = 400,
    lr: float = 0.05,
    prior: Optional[Dict[str, float]] = None,
    prior_strength: float = 30.0,
    seats: int = OTHER_SEATS,
) -> BotModel:
    """Fit per-card scores by Adam on the round likelihood.

    Each card starts at its prior score (e.g. from GIH WR) and is pulled back
    toward it as strongly as prior_strength observations would. Cards the bots
    rarely see -- strong cards drafters usually take first -- therefore keep a
    sensible score instead of drifting to average.
    """
    prior = prior or {}
    names = sorted({n for _, _, before, _ in rounds for n in before})
    index = {n: i for i, n in enumerate(names)}
    idx, mask, y = _pad(rounds, index)
    target = np.array([prior.get(n, prior.get(n.split(" // ")[0], 0.0)) for n in names], dtype=float)
    scores = target.copy()
    counts = np.bincount(idx[mask], minlength=len(names))
    m = np.zeros_like(scores)
    v = np.zeros_like(scores)
    b1, b2, eps = 0.9, 0.999, 1e-8
    n_obs = mask.sum()
    for t in range(1, iterations + 1):
        _, pi, surv = round_loglik(scores, idx, mask, y, seats)
        # d ll / d pi_c for the card's own term
        dsurv_dpi = -seats * (1.0 - pi) ** (seats - 1)
        dll_dsurv = np.where(mask, -y / (1 - surv) + (1 - y) / surv, 0.0)
        g_pi = dll_dsurv * dsurv_dpi  # per (round, slot)
        # softmax Jacobian: d pi_j / d s_k = pi_j (1[j=k] - pi_k)
        inner = (g_pi * pi).sum(axis=1, keepdims=True)
        g_s = np.where(mask, pi * (g_pi - inner), 0.0)
        grad = np.zeros_like(scores)
        np.add.at(grad, idx[mask], g_s[mask])
        # Per observation: a card's prior counts like prior_strength sightings.
        grad = (grad - (prior_strength / 13.0) * (scores - target) * 0.25) / n_obs
        m = b1 * m + (1 - b1) * grad
        v = b2 * v + (1 - b2) * grad * grad
        mh, vh = m / (1 - b1**t), v / (1 - b2**t)
        scores += lr * mh / (np.sqrt(vh) + eps)  # ascent
    ll, _, _ = round_loglik(scores, idx, mask, y, seats)
    out = {n: float(v) for n, v in prior.items()}
    out.update({n: float(scores[i]) for n, i in index.items()})
    shift = float(np.mean(list(out.values()))) if out else 0.0
    out = {n: round(v - shift, 4) for n, v in out.items()}
    meta = {
        "rounds": len(rounds),
        "cards": len(names),
        "train_loglik": round(float(ll), 4),
        "prior_strength": prior_strength,
        "sightings": {n: int(counts[i]) for n, i in index.items()},
    }
    return BotModel(out, meta)


# --- Evaluation ---------------------------------------------------------------


def evaluate(
    rounds: List,
    predict,
) -> Dict[str, float]:
    """Score survival predictions on held-out rounds.

    predict(pick, before) -> list of survival probabilities. Returns log loss,
    Brier score, and accuracy/precision of "will wheel" calls at 50%.
    """
    ll = brier = 0.0
    n = called = called_right = right = 0
    for _, pick, before, gone in rounds:
        surv = predict(pick, before)
        gone_left = list(gone)
        for name, p in zip(before, surv):
            survived = 1.0
            if name in gone_left:
                survived = 0.0
                gone_left.remove(name)
            p = min(max(p, 1e-6), 1 - 1e-6)
            ll += -(survived * math.log(p) + (1 - survived) * math.log(1 - p))
            brier += (p - survived) ** 2
            n += 1
            right += int((p >= 0.5) == bool(survived))
            if p >= 0.5:
                called += 1
                called_right += int(survived)
    return {
        "cards": n,
        "log_loss": ll / max(1, n),
        "brier": brier / max(1, n),
        "accuracy": right / max(1, n),
        "wheel_calls": called,
        "wheel_call_precision": called_right / max(1, called),
    }


def gihwr_prior(card_ratings: Dict, rounds: List) -> Dict[str, float]:
    """Per-card scores from GIH WR, scaled to fit the bot rounds as well as possible."""
    return gihwr_baseline(card_ratings, rounds).scores


def gihwr_baseline(card_ratings: Dict, rounds: List) -> BotModel:
    """The same model but every card's score is a fitted multiple of its GIH WR z-score.

    This is what "bots take the best cards" predicts, so the bot model has to
    beat it to show bots behave differently from the win rates.
    """
    rates = {}
    for card in (card_ratings or {}).values():
        name = card.get(constants.DATA_FIELD_NAME)
        wr = (
            card.get(constants.DATA_FIELD_DECK_COLORS, {})
            .get(constants.FILTER_OPTION_ALL_DECKS, {})
            .get(constants.DATA_FIELD_GIHWR, 0.0)
        )
        if name and wr:
            rates[name] = float(wr)
            rates.setdefault(name.split(" // ")[0], float(wr))
    if not rates:
        return BotModel({})
    mean = float(np.mean(list(rates.values())))
    std = float(np.std(list(rates.values()))) or 1.0
    z = {n: (wr - mean) / std for n, wr in rates.items()}
    names = sorted({n for _, _, b, _ in rounds for n in b})
    for n in names:
        z.setdefault(n, -1.0)
    index = {n: i for i, n in enumerate(names)}
    idx, mask, y = _pad(rounds, index)
    base = np.array([z[n] for n in names])
    best_beta, best_ll = 0.0, -np.inf
    for beta in np.linspace(0, 6, 61):
        ll, _, _ = round_loglik(base * beta, idx, mask, y)
        if ll > best_ll:
            best_beta, best_ll = beta, ll
    return BotModel({n: float(z[n] * best_beta) for n in z}, {"beta": best_beta})


def undervalued(
    model: BotModel, card_ratings: Dict, top: int = 15, prior: Optional[Dict[str, float]] = None,
    min_sightings: int = 150,
) -> List[Tuple[str, float, float]]:
    """Cards bots take much less than their win rate suggests: (name, gihwr, bot score).

    Compares each card's fitted score with its GIH WR-based prior, for cards
    the bots saw at least min_sightings times.
    """
    if prior is not None:
        rows = []
        for name, s in model.scores.items():
            if model.sightings.get(name, 0) < min_sightings or name not in prior:
                continue
            wr = 0.0
            for card in card_ratings.values():
                if card.get("name") == name:
                    wr = float(card.get("deck_colors", {}).get("All Decks", {}).get("gihwr", 0) or 0)
                    break
            rows.append((prior[name] - s, name, wr, s))
        rows.sort(reverse=True)
        return [(n, wr, s) for gap, n, wr, s in rows[:top] if gap > 0]
    out = []
    seen = set()
    scores = np.array(list(model.scores.values()))
    s_mean, s_std = float(scores.mean()), float(scores.std()) or 1.0
    rates = []
    for card in card_ratings.values():
        wr = card.get("deck_colors", {}).get("All Decks", {}).get("gihwr", 0.0)
        if wr:
            rates.append(float(wr))
    if not rates:
        return []
    r_mean, r_std = float(np.mean(rates)), float(np.std(rates)) or 1.0
    for card in card_ratings.values():
        name = card.get("name")
        wr = float(card.get("deck_colors", {}).get("All Decks", {}).get("gihwr", 0.0) or 0)
        if not name or name in seen or not wr or name not in model.scores and name.split(" // ")[0] not in model.scores:
            continue
        seen.add(name)
        gap = (wr - r_mean) / r_std - (model.score(name) - s_mean) / s_std
        out.append((gap, name, wr, model.score(name)))
    out.sort(reverse=True)
    return [(n, wr, s) for _, n, wr, s in out[:top]]
