#!/usr/bin/env bash
# Download a set's 17Lands Quick Draft dump, fit the bot model, and test it.
#
#   Tools/BotModel/bot_model.sh FRA            # 20,000 drafts
#   Tools/BotModel/bot_model.sh FRA 0          # every draft in the dump
#
# Run from the repository root with the app's Python environment active.
set -euo pipefail
SET="${1:-FRA}"
MAX="${2:-20000}"
EVENT="${EVENT:-QuickDraft}"
PY="${PYTHON:-python3}"
CACHE=".cache/backtest/$SET/$EVENT"
mkdir -p "$CACHE"
if [ ! -s "$CACHE/dump.csv.gz" ]; then
  echo "Downloading 17Lands $EVENT dump for $SET..."
  curl -fSLo "$CACHE/dump.csv.gz" "https://17lands-public.s3.amazonaws.com/analysis_data/draft_data/draft_data_public.$SET.$EVENT.csv.gz"
fi
if [ ! -s "$CACHE/dataset.json.gz" ]; then
  curl -fSLo "$CACHE/dataset.json.gz" "https://unrealities.github.io/MTGA_Draft_17Lands/${SET}_${EVENT}_All_Data.json.gz" \
    || curl -fSLo "$CACHE/dataset.json.gz" "https://unrealities.github.io/MTGA_Draft_17Lands/${SET}_PremierDraft_All_Data.json.gz"
fi
$PY Tools/BotModel/fit_bot_model.py --dump "$CACHE/dump.csv.gz" --dataset "$CACHE/dataset.json.gz" \
  --set "$SET" --event "$EVENT" --max-drafts "$MAX"
