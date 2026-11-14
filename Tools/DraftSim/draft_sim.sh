#!/usr/bin/env bash
# Simulate whole drafts: does following the Archetype Lens build decks that win more?
#
#   Tools/DraftSim/draft_sim.sh FRA 2000
#
# Seats the plain advisor ("base"), the lens as it was ("blend") and the lens
# scoring by deck value ("value", the app's setting) in the same simulated
# pods, and writes the comparison to results/sim_<SET>.md. Run from the
# repository root with the app's Python environment active. It reuses the
# draft dump lens_backtest.sh downloads (.cache/backtest/), and keeps its own
# files in .cache/draftsim/.
set -euo pipefail

SET="${1:-FRA}"
PODS="${2:-2000}"
SEED="${3:-1}"
JOBS="${JOBS:-4}"
ARMS="${ARMS:-blend value}"
EVENT="PremierDraft"
if [ -n "${PYTHON:-}" ]; then
  PY="$PYTHON"
elif command -v poetry >/dev/null 2>&1 && poetry env info -p >/dev/null 2>&1; then
  PY="poetry run python"
else
  PY="python3"
fi
HERE="Tools/DraftSim"
export PYTHONPATH="$HERE${PYTHONPATH:+:$PYTHONPATH}"
SRC=".cache/backtest/$SET/$EVENT"
D=".cache/draftsim"
mkdir -p "$SRC" "$D/runs" results
DUMP="$SRC/dump.csv.gz"
DATASET="$SRC/dataset.json.gz"

if [ ! -s "$DUMP" ]; then
  echo "Downloading 17Lands draft dump for $SET..."
  curl -fSLo "$DUMP" "https://17lands-public.s3.amazonaws.com/analysis_data/draft_data/draft_data_public.$SET.$EVENT.csv.gz"
fi
if [ ! -s "$DATASET" ]; then
  echo "Downloading app dataset for $SET..."
  curl -fSLo "$DATASET" "https://unrealities.github.io/MTGA_Draft_17Lands/${SET}_${EVENT}_All_Data.json.gz"
fi

DATA="$D/$SET.json.gz"
if [ ! -s "$DATA" ]; then
  echo "Reading the dump..."
  for k in $(seq 0 $((JOBS - 1))); do
    $PY $HERE/extract.py --dump "$DUMP" --part "$k/$JOBS" --out "$D/$SET.part$k.json.gz" &
  done
  wait
  $PY $HERE/extract.py --merge "$D/$SET".part*.json.gz --out "$DATA"
fi
[ -s "$D/$SET.win.json" ] || { echo "Fitting the win model..."; $PY $HERE/winmodel.py --data "$DATA" --dataset "$DATASET" --set "$SET" --out "$D/$SET.win.json"; }
[ -s "$D/$SET.pick.json" ] || { echo "Fitting the pick model..."; $PY $HERE/pickmodel.py --data "$DATA" --dataset "$DATASET" --set "$SET" --out "$D/$SET.pick.json"; }

STEP=$(( (PODS + JOBS - 1) / JOBS ))
run_arm() {  # name, then sim.py arguments
  local name="$1"; shift
  for k in $(seq 0 $((JOBS - 1))); do
    local a=$((k * STEP)) b=$(( (k + 1) * STEP ))
    [ "$b" -gt "$PODS" ] && b="$PODS"
    local out="$D/runs/$SET.s$SEED.$name.$a.json"
    [ "$a" -ge "$PODS" ] || [ -s "$out" ] || $PY $HERE/sim.py --data "$DATA" --dataset "$DATASET" \
      --pick-model "$D/$SET.pick.json" --set "$SET" --seed "$SEED" --pods "$a:$b" \
      --label "$name" --out "$out" "$@" &
  done
  wait
}
echo "Simulating $PODS pods: base..."
run_arm base
ARM_ARGS=()
for arm in $ARMS; do
  echo "Simulating $PODS pods: $arm..."
  run_arm "$arm" --lens --lens-mode "$arm"
  ARM_ARGS+=(--arm "$arm=$D/runs/$SET.s$SEED.$arm.*.json")
done

REPORT="results/sim_${SET}.md"
$PY $HERE/report.py --data "$DATA" --dataset "$DATASET" --win-model "$D/$SET.win.json" --set "$SET" \
  --base "$D/runs/$SET.s$SEED.base.*.json" "${ARM_ARGS[@]}" > "$REPORT"
grep -E "^## |win rate \((pair-adjusted|app deck score)\) " "$REPORT"
echo
echo "Full report: $REPORT"
