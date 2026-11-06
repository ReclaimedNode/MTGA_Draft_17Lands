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

echo "Replaying without the lens..."
$PY Tools/AdvisorReplay/replay.py --src . --drafts "$SAMPLE" --dataset "$DATASET" \
  --set "$SET" --label base --out "$OUT/$SET.base.json"
echo "Replaying with the lens..."
$PY Tools/AdvisorReplay/replay.py --src . --drafts "$SAMPLE" --dataset "$DATASET" \
  --set "$SET" --label head --lens --out "$OUT/$SET.head.json"

$PY Tools/AdvisorReplay/report.py "$OUT/$SET.base.json" "$OUT/$SET.head.json" | tee "$OUT/lens_$SET.md"
echo
echo "Report saved to $OUT/lens_$SET.md ('head' is the lens; 'base' is the plain advisor)."
