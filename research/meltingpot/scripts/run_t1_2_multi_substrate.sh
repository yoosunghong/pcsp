#!/usr/bin/env bash
# T1.2 — Tier 1 paper-revision experiment: extend Layer 2 from a single substrate
# to a multi-substrate benchmark. Runs the existing PCSP trainer
# (research/meltingpot/scripts/run_pcsp_meltingpot_clean.py) on two new
# Melting Pot substrates with both the full objective and the InfoNCE-off
# ablation, three seeds each. Mirrors the cog_clean layout used for
# commons_harvest__open.
#
# Outputs land under research/meltingpot/runs/t1_2/<substrate>/...
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
RESEARCH="$REPO/research"
RUNS="$RESEARCH/meltingpot/runs/t1_2"
SCRIPT="$RESEARCH/meltingpot/scripts/run_pcsp_meltingpot_clean.py"
mkdir -p "$RUNS"

SEEDS=(1 2 3)
STEPS=1000000

run_one() {
  local sub="$1" seed="$2" mode="$3"
  local name="${mode}_seed${seed}_1M"
  local out="$RUNS/$sub/$name"
  if [[ -f "$out/policy.pt" ]]; then
    echo "[skip] $sub/$name already complete"
    return 0
  fi
  mkdir -p "$out"
  local extra=()
  if [[ "$mode" == "no_infonce" ]]; then
    extra+=(--ablation-no-infonce)
  fi
  echo "[start] $sub/$name"
  python "$SCRIPT" \
    --substrate "$sub" \
    --seed "$seed" \
    --total-env-steps "$STEPS" \
    --run-dir "$out" \
    "${extra[@]}" \
    > "$out/stdout.log" 2>&1
  echo "[done]  $sub/$name"
}

for sub in clean_up prisoners_dilemma_in_the_matrix__repeated; do
  for seed in "${SEEDS[@]}"; do
    run_one "$sub" "$seed" "full"
    run_one "$sub" "$seed" "no_infonce"
  done
done

echo "[all-done] T1.2 multi-substrate training complete."
