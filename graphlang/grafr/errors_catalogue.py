"""The error-code catalogue `graflang.errors.yaml` (design: graflang-semantics.md 3d).

One shipped file (beside this package) and, optionally, one beside the top graph. Together they define every code a graph's parts may use;
a code is defined once. Nothing here runs a graph: `parts.py` asks it whether a code is known, the runtime logs its text.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Optional

from ruamel.yaml import YAML

FILE_NAME = "graflang.errors.yaml"
SHIPPED = Path(__file__).resolve().parent.parent / FILE_NAME
CODE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*$")
FIELDS = ("code", "description", "cause", "remedy")


class CatalogueError(ValueError):
    pass


def load(path: Path) -> Dict[str, Dict[str, str]]:
    """The entries of one catalogue file by code. Refuses a malformed entry or a code defined twice in the file."""
    try:
        data = YAML(typ="safe").load(Path(path).read_text(encoding="utf-8")) or {}
    except Exception as e:                                                  # noqa: BLE001 - YAML and OS errors alike
        raise CatalogueError(f"{path}: cannot read the catalogue: {e}") from None
    if not isinstance(data, dict) or "errors" not in data or not isinstance(data["errors"] or [], list):
        raise CatalogueError(f"{path}: needs a top-level `errors:` list")
    out: Dict[str, Dict[str, str]] = {}
    for i, item in enumerate(data.get("errors") or [], 1):
        if not isinstance(item, dict) or not isinstance(item.get("code"), str) or not CODE_RE.match(item["code"]):
            raise CatalogueError(f"{path}: entry {i} needs a `code` of letters, digits, _ . - starting with a letter")
        if not isinstance(item.get("description"), str) or not item["description"].strip():
            raise CatalogueError(f"{path}: {item['code']} needs a one-line `description`")
        unknown = sorted(set(item) - set(FIELDS))
        if unknown:
            raise CatalogueError(f"{path}: {item['code']} has unknown keys {unknown} (the keys are {list(FIELDS)})")
        if item["code"] in out:
            raise CatalogueError(f"{path}: code {item['code']} is defined twice; a code names exactly one cause")
        out[item["code"]] = {k: str(item[k]).strip() for k in FIELDS if item.get(k) is not None}
    return out


def local_file(base_dir: Optional[Path]) -> Optional[Path]:
    f = Path(base_dir) / FILE_NAME if base_dir else None
    return f if f is not None and f.is_file() and f.resolve() != SHIPPED.resolve() else None


def catalogue_for(base_dir: Optional[Path]) -> Dict[str, Dict[str, str]]:
    """The shipped catalogue plus the one beside the graph (`base_dir`), if any. A code defined in both is refused."""
    entries = load(SHIPPED) if SHIPPED.is_file() else {}
    local = local_file(base_dir)
    if local is not None:
        for code, entry in load(local).items():
            if code in entries:
                raise CatalogueError(f"{local}: code {code} is also defined in the shipped catalogue; a code names exactly one cause")
            entries[code] = entry
    return entries
