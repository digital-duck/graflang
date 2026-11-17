#!/usr/bin/env bash
# Run `graf prettier` in place on every *.graph.yaml under cookbook/, cookbook_solvers/ and cookbook_pocketflow/:
# code, prompts and expressions become YAML block scalars (no doubled quotes). Only the style changes: graf prettier
# checks that every value reads back the same, and a file that fails the check is left as it was.
#
#   scripts/prettify_recipes.sh            # rewrite the files that would change
#   scripts/prettify_recipes.sh -n         # dry run: list what would change, write nothing
#
# Commit (or stash) first if you want an easy way back: `git diff --stat` shows what changed, `git checkout -- cookbook*` undoes it.
# Needs the `graf` command (conda activate graf). Run folders (output/) are skipped. Exit status 1 if any file failed.

set -u -o pipefail

usage() { sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; }

dry_run=0
case "${1:-}" in
    "") ;;
    -n|--dry-run) dry_run=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
esac

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
dirs=(cookbook cookbook_solvers cookbook_pocketflow)

if ! command -v graf >/dev/null 2>&1; then
    echo "graf not found: activate the environment that has graflang (conda activate graf)" >&2
    exit 2
fi

cd "$root" || exit 2
tmp="$(mktemp)"
err="$(mktemp)"
trap 'rm -f "$tmp" "$err"' EXIT

changed=0 unchanged=0 failed=0
for dir in "${dirs[@]}"; do
    if [ ! -d "$dir" ]; then
        echo "skipping $dir: not a folder" >&2
        continue
    fi
    while IFS= read -r file; do
        if ! graf prettier "$file" -o "$tmp" 2>"$err"; then
            failed=$((failed + 1))
            echo "FAILED     $file: $(tr '\n' ' ' <"$err" | sed 's/  */ /g')"
        elif cmp -s "$file" "$tmp"; then
            unchanged=$((unchanged + 1))
        else
            changed=$((changed + 1))
            count="$(tr '\n' ' ' <"$err" | sed -n 's/.*\([0-9][0-9]*\) attribute(s) rewritten.*/\1/p')"
            if [ "$dry_run" -eq 1 ]; then
                echo "would change  $file (${count:-?} attributes)"
            else
                cat "$tmp" >"$file"                         # overwrite the contents: keeps the file's mode and owner
                echo "changed      $file (${count:-?} attributes)"
            fi
            grep -h "kept as it was" "$err" | sed "s|^|             |"       # an attribute graf prettier could not turn into a block
        fi
    done < <(find "$dir" -name '*.graph.yaml' -not -path '*/output/*' -not -path '*/__pycache__/*' -not -path '*/.git/*' | sort)
done

total=$((changed + unchanged + failed))
if [ "$dry_run" -eq 1 ]; then
    echo "$total graph files: $changed would change, $unchanged already fine, $failed failed (dry run: nothing written)"
else
    echo "$total graph files: $changed changed, $unchanged already fine, $failed failed"
    [ "$changed" -gt 0 ] && echo "see what changed with: git diff --stat"
fi
[ "$failed" -eq 0 ]
