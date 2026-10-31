"""Turns the `document` input into text: a literal string is used as it is, a path to a file is replaced by the file's text.

stdin   one JSON object: {"document": a text, or the path of a text file (relative paths start in the recipe's folder)}
stdout  one line of JSON: the text (a JSON string)
exit    0 when it worked; 1 when the document looks like a file name but no such file exists (so a typo is never audited
        as if it were the document), or the file is not UTF-8 text, with the reason on stderr.
"""
import json
import re
import sys
from pathlib import Path

LOOKS_LIKE_A_FILE = re.compile(r"^[\w./~-]+\.(txt|md|text|csv|json|log)$")      # one token that ends in a text-file extension


def parse(stdout: str) -> str:
    """The graph's parser (`parse: {tool: ...}`): the built-in ones read a line or a JSON object, not a whole text."""
    return json.loads(stdout)


def main() -> int:
    try:
        document = json.load(sys.stdin).get("document", "")
    except ValueError as e:
        print(f"could not load the document: stdin is not JSON: {e}", file=sys.stderr)
        return 1
    document = document if isinstance(document, str) else str(document)
    candidate = document.strip()
    if "\n" not in candidate and len(candidate) < 1024:
        path = Path(candidate).expanduser()
        if path.is_file():
            try:
                document = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as e:
                print(f"could not read the document file {path}: {e}", file=sys.stderr)
                return 1
        elif LOOKS_LIKE_A_FILE.match(candidate):
            print(f"could not load the document: no such file {candidate!r} (a relative path starts in {Path.cwd()})", file=sys.stderr)
            return 1
    print(json.dumps(document))
    return 0


if __name__ == "__main__":
    sys.exit(main())
