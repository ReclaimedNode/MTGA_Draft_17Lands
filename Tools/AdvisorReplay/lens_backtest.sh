#!/usr/bin/env bash
# Backtest the Archetype Lens against the plain advisor on real 17Lands drafts.
#
#   Tools/AdvisorReplay/lens_backtest.sh FRA 1000
#
# Downloads 17Lands' public Premier Draft dump and the app's dataset for the
# set, samples drafts, replays them through this copy of the app twice (plain
# = "base", --lens = "head"), and writes the comparison to
# results/lens_<SET>.md. Run from the repository root with the app's Python
# environment active. The dump is a few hundred MB; it's cached in .cache/.
set -euo pipefail

SET="${1:-FRA}"
DRAFTS="${2:-1000}"
SALT="${3:-lens}"
# Use the app's Poetry environment when there is one, so numpy etc. are found.
if [ -n "${PYTHON:-}" ]; then
  PY="$PYTHON"
elif command -v poetry >/dev/null 2>&1 && poetry env info -p >/dev/null 2>&1; then
  PY="poetry run python"
else
  PY="python3"
fi
if ! $PY -c "import numpy, pydantic" >/dev/null 2>&1; then
  echo "The app's dependencies aren't installed for: $PY"
  echo "Run 'poetry install' in this folder first (see the README's Mac setup), then rerun."
  exit 1
fi
CACHE=".cache/backtest/$SET"
OUT="results"
mkdir -p "$CACHE" "$OUT"

DUMP="$CACHE/dump.csv.gz"
DATASET="$CACHE/dataset.json.gz"
SAMPLE="$CACHE/drafts_${DRAFTS}_${SALT}.json.gz"

if [ ! -s "$DUMP" ]; then
  echo "Downloading 17Lands draft dump for $SET..."
  curl -fSLo "$DUMP" "https://17lands-public.s3.amazonaws.com/analysis_data/draft_data/draft_data_public.$SET.PremierDraft.csv.gz"
fi
if [ ! -s "$DATASET" ]; then
  echo "Downloading app dataset for $SET..."
  curl -fSLo "$DATASET" "https://unrealities.github.io/MTGA_Draft_17Lands/${SET}_PremierDraft_All_Data.json.gz"
fi
if [ ! -s "$SAMPLE" ]; then
  echo "Sampling $DRAFTS drafts..."
  $PY Tools/AdvisorReplay/sample.py --dump "$DUMP" --drafts "$DRAFTS" --salt "$SALT" --out "$SAMPLE"
fi

BASE="$OUT/$SET.base.$SALT.json"
if [ ! -s "$BASE" ]; then
  echo "Replaying without the lens..."
  $PY Tools/AdvisorReplay/replay.py --src . --drafts "$SAMPLE" --dataset "$DATASET" \
    --set "$SET" --label base --out "$BASE"
fi

# ABLATE=1 also tests the lens with each piece switched off, one at a time.
VARIANTS="full"
if [ "${ABLATE:-0}" = "1" ]; then
  VARIANTS="full no-delta no-key no-flex only-flex"
fi
for V in $VARIANTS; do
  case "$V" in
    full) OFF="" ;;
    no-delta) OFF="delta" ;;
    no-key) OFF="key" ;;
    no-flex) OFF="flex" ;;
    only-flex) OFF="delta,key" ;;
  esac
  echo "Replaying with the lens ($V)..."
  HEAD="$OUT/$SET.head.$V.$SALT.json"
  $PY Tools/AdvisorReplay/replay.py --src . --drafts "$SAMPLE" --dataset "$DATASET" \
    --set "$SET" --label head --lens --lens-off "$OFF" --out "$HEAD"
  $PY Tools/AdvisorReplay/report.py "$BASE" "$HEAD" > "$OUT/lens_${SET}_${V}_${SALT}.md"
  echo "== $V =="
  grep -E "^Top-1, head minus base|regret:" "$OUT/lens_${SET}_${V}_${SALT}.md" || true
done
echo
echo "Full reports: $OUT/lens_${SET}_<variant>_${SALT}.md ('head' is the lens; 'base' is the plain advisor)."
