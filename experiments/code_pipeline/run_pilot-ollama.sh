#!/usr/bin/env bash
# Pilot: all four arms (single, spl, graflang, langgraph) on a handful of HumanEval tasks, in one go.
#
#   conda activate graf
#   nohup ./run_pilot.sh > /dev/null 2>&1 &        # submit it and walk away; it keeps going if you close the terminal
#   tail -f logs/pilot-*.log                        # follow it (newest log), or just look at it later
#   ./run_pilot.sh --dry-run                        # only show the plan
#
# Pick the tasks and the model with environment variables (or edit the defaults below):
#   TASKS="98,107,10,24,35" MODEL=claude-sonnet-5-5 ./run_pilot.sh
#   ADAPTER=ollama MODEL=qwen2.5-coder-16k ./run_pilot-ollama.sh   # a local model through ollama (the server must be running)
#
# One-time setup of the model with a 16k context window. Ollama's default context is 2048 tokens and it drops the START of
# a longer prompt without an error, so every prompt past 2048 tokens would reach the model cut short:
#   printf 'FROM qwen2.5-coder:latest\nPARAMETER num_ctx 16384\n' > Modelfile.qwen16k
#   ollama create qwen2.5-coder-16k -f Modelfile.qwen16k
#   TASKS="" N=5 ./run_pilot.sh                     # a fixed random sample of N tasks instead of a list
#
# Adding tasks later: put more numbers in TASKS (TASKS="98,107,10,24,35,41,55" ./run_pilot.sh). The tasks already in
# results/pilot.db for this model are reported and skipped, so only the new ones run. EXISTING=append runs the listed
# tasks again as one more repetition each, keeping the stored rows.
#
# Where things go (all inside this folder, git-ignored except results/):
#   logs/pilot-<time>.log          everything this script prints
#   output/<adapter>/<model>/<task>/<arm>-rep0/   per run: code.py, the arm's logs, prompts and artifacts (see arms.py)
#   results/pilot.db               one row per run (query it, or read results/pilot-report-<time>.txt)
#
# A run whose arm crashes, times out or whose model call fails is stored as an error and the batch goes on; running the
# script again retries exactly those. A wrong answer is a result and is not retried.
# It is resumable: if it stops (Ctrl-C, a crash, a reboot), run the same command and it continues with the runs
# that are not in results/pilot.db yet. Delete results/pilot.db to start over.
set -euo pipefail
cd "$(dirname "$0")"

ADAPTER="${ADAPTER:-ollama}"          # claude_cli (default), or ollama for a local model: ADAPTER=ollama MODEL=gemma4
MODEL="${MODEL:-qwen2.5-coder-16k}"      # qwen2.5-coder with a 16k context window: created once with the Modelfile below
export TASKS="${TASKS-98,107,10,24,35,41,55,64,66,72,77,91,103,122,124,129,130,136,149,154}"   # 20 tasks; the ones already in pilot-ollama.db are skipped    # the exact list of tasks (exported, so run.py reads it too); TASKS="" uses N random tasks
EXISTING="${EXISTING:-skip}"                # a task already in the database: skip it, or append new repetitions (EXISTING=append)
N="${N:-5}"
DB="${DB:-results/pilot-ollama.db}"     # its own database: a claude_cli pilot writes results/pilot.db, so the two never share a file
EXTRA=("$@")                                # e.g. --dry-run

mkdir -p logs results output
STAMP="$(date +%Y%m%d-%H%M%S)"
LOG="logs/pilot-$STAMP.log"
exec > >(tee -a "$LOG") 2>&1

# one pilot per model at a time (a claude_cli and an ollama pilot may run together; each writes its own database,
# the graflang arm serialises itself with a lock of its own)
LOCK="logs/.pilot-${ADAPTER}-$(echo "$MODEL" | tr -c 'A-Za-z0-9' '_').lock"
exec 9> "$LOCK"
flock -n 9 || { echo "another pilot for $ADAPTER/$MODEL is already running ($LOCK); stop it or wait"; exit 1; }

echo "pilot $STAMP on $(hostname): adapter=$ADAPTER model=$MODEL tasks=${TASKS:-N=$N} existing=$EXISTING db=$DB"
for tool in python spl3; do
    command -v "$tool" > /dev/null || { echo "missing '$tool' on PATH (conda activate graf?)"; exit 1; }
done
[ "$ADAPTER" = claude_cli ] && { command -v claude > /dev/null || { echo "missing 'claude' on PATH"; exit 1; }; }

python -c "import click, langgraph, graphlang, spl3" 2> /dev/null \
    || { echo "the python on PATH ($(command -v python)) cannot import click, langgraph, graphlang and spl3 (conda activate graf?)"; exit 1; }

if [ "$ADAPTER" = ollama ]; then
    echo "--- context check: a prompt of about 6,000 tokens must be read in full (ollama silently drops the start of a longer one)"
    python -c "
import json, sys, urllib.request
host = __import__('os').environ.get('OLLAMA_HOST', 'http://localhost:11434')
prompt = 'Remember this word: BANANA-7731.\\n' + 'The quick brown fox jumps over the lazy dog. ' * 2500
req = urllib.request.Request(host + '/api/generate', headers={'Content-Type': 'application/json'},
    data=json.dumps({'model': sys.argv[1], 'prompt': prompt, 'stream': False, 'options': {'num_predict': 1}}).encode())
read = json.load(urllib.request.urlopen(req, timeout=900))['prompt_eval_count']
print(f'model read {read} tokens of about 8,000 sent')
sys.exit(0 if read > 7000 else 1)
" "$MODEL" || { echo "the model reads too little of a long prompt (context too small): see the Modelfile in the comments above"; exit 1; }
fi

echo "--- one tiny call to the model ($ADAPTER), so a wrong model id, a stopped ollama server or a logged-out CLI stops here and not after an hour"
python -c "import sys; from graphlang.grafr.adapters import make_llm; r = make_llm(sys.argv[1], sys.argv[2]).generate('Reply with the single word: ok', model=sys.argv[2]); print(r.strip()[:80]); sys.exit(0 if r.strip() else 1)" \
    "$ADAPTER" "$MODEL" || { echo "the model call failed (adapter=$ADAPTER model=$MODEL); fix it and run again"; exit 1; }

echo "--- checking the scorer (no LLM)"
python run.py --verify-oracle

if [ -n "$TASKS" ]; then SELECT=(--tasks "$TASKS"); else SELECT=(--n "$N"); fi

echo "--- running the four arms"
python run.py "${SELECT[@]}" --existing "$EXISTING" --reps 1 --adapter "$ADAPTER" --model "$MODEL" --db "$DB" --run-dir output "${EXTRA[@]}"

case " ${EXTRA[*]:-} " in
    *" --dry-run "*) exit 0 ;;
esac

REPORT="results/pilot-report-$STAMP.txt"
echo "--- analysis -> $REPORT"
python analyze.py "$DB" --adapter "$ADAPTER" --model "$MODEL" | tee "$REPORT"
echo "done $(date +%H:%M:%S). log: $LOG   report: $REPORT   runs: output/$ADAPTER/$MODEL/"
