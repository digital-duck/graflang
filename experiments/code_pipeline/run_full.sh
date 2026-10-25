#!/usr/bin/env bash
# Full run for the GraphLang paper: 3 arms (single, graflang, langgraph) on a stratified sample of HumanEval tasks,
# 20 from each complexity group (low, medium, high), one repetition. The spl arm is not in this run (it belongs to the
# TMLR revision, not to this comparison).
#
#   conda activate graf
#   nohup ./run_full.sh > /dev/null 2>&1 &      # submit and walk away
#   tail -f logs/full-*.log                      # follow it
#   ./run_full.sh --dry-run                      # only the plan
#
# Settings (environment variables):
#   MODEL=claude-sonnet-5-5   the model (claude_cli); ADAPTER=claude_cli
#   PER_GROUP=20              tasks per complexity group (60 in all)
#   SEED=0                    the seed of the stratified sample (fixed: every arm sees the same tasks)
#   DB=results/full-<model>.db  its own database, so models never share a file
#
# Output: output/<adapter>/<model>/<task>/<arm>-rep0/ (git-ignored), results in $DB, the analysis in results/paper/.
# Resumable: the same command continues with the runs not yet in $DB. Error runs are retried.
set -euo pipefail
cd "$(dirname "$0")"

ADAPTER="${ADAPTER:-claude_cli}"
MODEL="${MODEL:-claude-sonnet-5-5}"
PER_GROUP="${PER_GROUP:-20}"
SEED="${SEED:-0}"
SAFE="${MODEL//[^A-Za-z0-9]/-}"              # a file-name-safe form of the model id (no trailing newline, unlike echo | tr)
DB="${DB:-results/full-$SAFE.db}"
ARMS="single,graflang,langgraph"
EXTRA=("$@")

mkdir -p logs results output results/paper
STAMP="$(date +%Y%m%d-%H%M%S)"
LOG="logs/full-$STAMP.log"
exec > >(tee -a "$LOG") 2>&1

LOCK="logs/.full-${ADAPTER}-${MODEL//[^A-Za-z0-9]/_}.lock"
exec 9> "$LOCK"
flock -n 9 || { echo "another full run for $ADAPTER/$MODEL is already running ($LOCK)"; exit 1; }

echo "full run $STAMP on $(hostname): adapter=$ADAPTER model=$MODEL per_group=$PER_GROUP seed=$SEED arms=$ARMS db=$DB"
for tool in python spl3; do
    command -v "$tool" > /dev/null || { echo "missing '$tool' on PATH (conda activate graf?)"; exit 1; }
done
if [ "$ADAPTER" = claude_cli ]; then
    command -v claude > /dev/null || { echo "missing 'claude' on PATH"; exit 1; }
fi

echo "--- one tiny call to the model ($ADAPTER/$MODEL)"
python -c "import sys; from graphlang.grafr.adapters import make_llm; r = make_llm(sys.argv[1], sys.argv[2]).generate('Reply with the single word: ok', model=sys.argv[2]); print(r.strip()[:80]); sys.exit(0 if r.strip() else 1)" \
    "$ADAPTER" "$MODEL" || { echo "the model call failed; fix it and run again"; exit 1; }

echo "--- checking the scorer (no LLM)"
python run.py --verify-oracle

echo "--- the plan"
python run.py --per-group "$PER_GROUP" --seed "$SEED" --arms "$ARMS" --adapter "$ADAPTER" --model "$MODEL" --db "$DB" --run-dir output --dry-run

case " ${EXTRA[*]:-} " in
    *" --dry-run "*) exit 0 ;;
esac

echo "--- running"
python run.py --per-group "$PER_GROUP" --seed "$SEED" --arms "$ARMS" --existing skip --reps 1 --adapter "$ADAPTER" --model "$MODEL" --db "$DB" --run-dir output "${EXTRA[@]}"

REPORT="results/paper/full-$SAFE-$STAMP.txt"
echo "--- analysis -> $REPORT"
python analyze.py "$DB" --adapter "$ADAPTER" --model "$MODEL" | tee "$REPORT"
echo "done $(date +%H:%M:%S). log: $LOG   report: $REPORT"
