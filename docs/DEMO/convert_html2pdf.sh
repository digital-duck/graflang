#!/usr/bin/env bash
# Convert an .html slide deck to .pdf by running `spl3 util html2pdf` (SPL.py; headless Chromium/Chrome).
#
#   ./convert_html2pdf.sh                       # graflang-intro.html -> graflang-intro-YYYYMMDD.pdf
#   ./convert_html2pdf.sh deck.html             # -> deck-YYYYMMDD.pdf next to the html
#   ./convert_html2pdf.sh deck.html out.pdf     # -> out.pdf
#
# Needs `spl3` on PATH (conda activate spl123) and a Chromium or Chrome (or set CHROME=/path/to/browser).
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
html="${1:-$here/graflang-intro.html}"
out="${2:-${html%.html}-$(date +%Y%m%d).pdf}"

command -v spl3 >/dev/null 2>&1 || { echo "spl3 not found: conda activate spl123" >&2; exit 1; }
exec spl3 util html2pdf "$html" -o "$out"
