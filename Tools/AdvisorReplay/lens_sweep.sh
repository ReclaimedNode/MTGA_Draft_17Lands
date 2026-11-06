#!/usr/bin/env bash
# Tune and stress-test the Archetype Lens across sets and weight settings.
#
#   Tools/AdvisorReplay/lens_sweep.sh                 # default sets, 2000 drafts, salt "sweep"
#   SETS="FRA TDM" DRAFTS=1000 SALT=tune1 Tools/AdvisorReplay/lens_sweep.sh
#   EVENT=QuickDraft SETS="FRA" Tools/AdvisorReplay/lens_sweep.sh
#
# For each set it replays the app's default lens and, unless QUICK=1, one
# change at a time to each tunable weight. Every run is compared with the plain
# advisor on the same drafts. The summary goes to results/sweep_<EVENT>_<SALT>.md.
# Pick a winner on one salt, then confirm it on another (SALT=confirm1) before
# changing the defaults: the best of many settings looks better than it is.
set -euo pipefail

SETS="${SETS:-FRA TDM FIN TLA SOS}"
DRAFTS="${DRAFTS:-2000}"
SALT="${SALT:-sweep}"
EVENT="${EVENT:-PremierDraft}"
SUMMARY="results/sweep_${EVENT}_${SALT}.md"
mkdir -p results

# One-at-a-time variations around the defaults (DELTA_TIP 0.25, MASS_FULL_CREDIT
# 0.3, SHRINK_K 400, TEMP_START 2.5, ARCH_WEIGHT_RAMP 0.7).
SETTINGS=(
  ""
  "DELTA_TIP=0" "DELTA_TIP=0.5"
  "MASS_FULL_CREDIT=0.15" "MASS_FULL_CREDIT=0.6"
  "SHRINK_K=200" "SHRINK_K=800"
  "TEMP_START=1.5" "TEMP_START=4"
  "ARCH_WEIGHT_RAMP=0.5" "ARCH_WEIGHT_RAMP=1.0"
)
if [ "${QUICK:-0}" = "1" ]; then SETTINGS=(""); fi

{
  echo "# Archetype Lens sweep ($EVENT, $DRAFTS drafts/set, salt $SALT)"
  echo
  echo "Top-1 and regret are head (lens) minus base (plain advisor). Top-1: higher is better. Regret: more negative is better. SE in parentheses."
  echo
  echo "| set | setting | top-1 | regret |"
  echo "|---|---|---|---|"
} > "$SUMMARY"

for SET in $SETS; do
  for S in "${SETTINGS[@]}"; do
    LABEL="${S:-default}"
    echo "=== $SET: $LABEL ==="
    if ! PARAMS="$S" EVENT="$EVENT" Tools/AdvisorReplay/lens_backtest.sh "$SET" "$DRAFTS" "$SALT" > /tmp/lens_sweep.log 2>&1; then
      echo "  failed (see /tmp/lens_sweep.log); skipping $SET"
      tail -3 /tmp/lens_sweep.log
      echo "| $SET | $LABEL | failed | |" >> "$SUMMARY"
      break
    fi
    REPORT="results/lens_${SET}_${EVENT}_${SALT}_default.md"
    TOP1=$(grep -E "^Top-1, head minus base" "$REPORT" | sed -E 's/.*\*\*(.*) points\*\* \(paired bootstrap SE (.*)\)\./\1 (\2)/')
    REG=$(grep -E "regret:" "$REPORT" | awk -F'|' '{print $5}' | sed -E 's/\*//g; s/^ +| +$//g')
    echo "  top-1 $TOP1, regret $REG"
    echo "| $SET | $LABEL | $TOP1 | $REG |" >> "$SUMMARY"
    # Keep each setting's report (the default's is already in place).
    if [ "$LABEL" != "default" ]; then
      cp "$REPORT" "results/lens_${SET}_${EVENT}_${SALT}_${LABEL//[^A-Za-z0-9_.=]/_}.md"
    fi
  done
done

echo
cat "$SUMMARY"
echo
echo "Saved $SUMMARY"
