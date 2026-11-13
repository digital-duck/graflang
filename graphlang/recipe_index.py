"""Search over the recipes of the work area: what each one does, which nodes and inputs it has, what it costs to run.

This is the GraphLang counterpart of SPL.py's `spl3 code-rag`: a description-to-source index that finds existing recipes for a request,
so a person can browse them and `graf create` can show the best matches to the model as examples. One entry is one *recipe* (a folder:
its main graph, sub-graphs and prompts together), never one file.

Two signals are combined. **Meaning**: the request and each recipe's description are embedded (`graphlang.embedding`, dd-embed: a local
Ollama model or sentence-transformers) and compared by cosine, so "coding" finds a recipe that writes, reviews and tests code. **Words**:
BM25 over the recipe's name, description, readme, node types, inputs and prompts, with a light stemmer ("coding" and "code" agree), so
an exact term such as an input name still counts. With no embedding model the search falls back to words alone and says so. Only the
recipes close to the best one are returned, not a long tail.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import yaml

import numpy as np

from .embedding import Embedder, VectorCache
from .workspace import GRAPH_SUFFIX, Recipe, Workspace, graphs_in, scan_for_code

WORD = re.compile(r"[a-z0-9]+")
STOP = frozenset("a an and are as at be by for from has have in into is it its of on or that the this to with you your use uses using "
                 "then than but not no yes can will each per via".split())
FIELD_WEIGHT = {"title": 4, "tags": 3, "description": 3, "readme": 1, "prompts": 1}
K1, B = 1.4, 0.75
MAX_README_CHARS, MAX_PROMPT_CHARS = 6000, 6000
BORING_NODES = {"INPUT", "OUTPUT"}


def stem(w: str) -> str:
    """A light stemmer, enough that "coding", "codes" and "code" agree: strip a common ending, then a final e."""
    for suffix in ("ing", "ed", "ly", "es", "s"):
        if w.endswith(suffix) and not (suffix == "s" and w.endswith("ss")) and len(w) - len(suffix) >= 3:
            w = w[:-len(suffix)]
            break
    return w[:-1] if w.endswith("e") and len(w) > 3 else w


def words(text: str) -> List[str]:
    """Lower-case stems; `snake_case` and `camelCase` are split so `self_refine` finds "refine"."""
    out: List[str] = []
    for raw in re.split(r"[^A-Za-z0-9]+", re.sub(r"([a-z])([A-Z])", r"\1 \2", text)):
        w = raw.lower()
        if w and w not in STOP and len(w) > 1:
            out.append(stem(w))
    return out


@dataclass
class Entry:
    """One recipe (a folder), with what a person (or a model) needs to judge it."""
    key: str                                  # root/folder, unique
    root: str
    folder: Path
    graph: Path                               # its main graph: `<folder>.graph.yaml`, else the first one
    title: str
    description: str
    readme: str = ""
    tags: List[str] = field(default_factory=list)
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    node_types: Dict[str, int] = field(default_factory=dict)
    llm_calls: int = 0                        # GENERATE nodes: a floor, loops and retries add calls
    has_code: bool = False
    shipped: bool = False
    prompts_text: str = ""
    graphs: List[str] = field(default_factory=list)       # every graph of the recipe, relative to its folder (sub-graphs too)

    def fields(self) -> Dict[str, str]:
        return {"title": f"{self.title} {self.folder.name} {self.graph.name}", "tags": " ".join(self.tags + self.inputs + self.outputs),
                "description": self.description, "readme": self.readme, "prompts": self.prompts_text}


@dataclass
class Hit:
    entry: Entry
    score: float
    matched: List[str]
    meaning: Optional[float] = None        # cosine similarity of the request and the recipe, when an embedding model is in use


def _first_paragraph(text: str) -> str:
    for block in re.split(r"\n\s*\n", text):
        block = block.strip()
        if block and not block.startswith(("#", "```", "|", "-", ">", "!")):
            return re.sub(r"\s+", " ", block)
    return ""


def _header_comment(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if line.startswith("#"):
            lines.append(line.lstrip("# ").strip())
        elif line.strip() == "" and not lines:
            continue
        else:
            break
    return " ".join(lines)


def main_graph(folder: Path) -> Optional[Path]:
    """The graph that stands for a recipe: `<folder>.graph.yaml`, else the first one beside the readme, else the first one found."""
    graphs = graphs_in(folder)
    named = folder / f"{folder.name}{GRAPH_SUFFIX}"
    return named if named in graphs else (graphs[0] if graphs else None)


def describe(root: str, folder: Path, writable: bool) -> Optional[Entry]:
    """Read a recipe folder into an Entry. Anything unreadable is skipped, not fatal: a broken recipe is still listed."""
    graph = main_graph(folder)
    if graph is None:
        return None
    text = graph.read_text(encoding="utf-8", errors="replace")
    try:
        raw = yaml.safe_load(text) or {}
    except yaml.YAMLError:
        raw = {}
    readme_path = next((p for p in (folder / "readme.md", folder / "README.md") if p.is_file()), None)
    readme = readme_path.read_text(encoding="utf-8", errors="replace")[:MAX_README_CHARS] if readme_path else ""
    title = next((line.lstrip("# ").strip() for line in readme.splitlines() if line.startswith("# ")), "") or folder.name
    declared = str((raw.get("workflow") or {}).get("description") or "").strip() if isinstance(raw, dict) else ""    # `workflow.description` wins
    description = declared or (_first_paragraph(readme) if readme else "") or _header_comment(text) or str((raw.get("workflow") or {}).get("name", ""))
    node_types: Counter = Counter()
    nodes = raw.get("nodes") if isinstance(raw, dict) else None
    if isinstance(nodes, list):
        node_types.update(str(n.get("type", "")) for n in nodes if isinstance(n, dict))
    elif isinstance(raw, dict) and isinstance(raw.get("steps"), list):                       # compact: a step names its kind by a key
        for step in raw["steps"]:
            if isinstance(step, dict):
                node_types.update(k.upper() for k in step if k.upper() in {"GENERATE", "SOLVE", "EVALUATE", "LOOP", "ASSERT", "GUARD", "MUTATE", "RUN", "USE", "FORK", "JOIN"})
    workflow = raw.get("workflow") if isinstance(raw, dict) and isinstance(raw.get("workflow"), dict) else {}
    inputs = [str(i.get("name")) for i in workflow.get("inputs", []) if isinstance(i, dict) and i.get("name")]
    outputs = [str(i.get("name")) for i in workflow.get("outputs", []) if isinstance(i, dict) and i.get("name")]
    prompts = [p.read_text(encoding="utf-8", errors="replace") for p in sorted(folder.rglob("prompts/*.md")) if "output" not in p.parts]
    for n in nodes if isinstance(nodes, list) else []:
        cfg = n.get("config") if isinstance(n, dict) else None
        if isinstance(cfg, dict) and isinstance(cfg.get("prompt_inline"), str):
            prompts.append(cfg["prompt_inline"])
    types = {t: n for t, n in node_types.items() if t and t not in BORING_NODES}
    graphs = [g.relative_to(folder).as_posix() for g in graphs_in(folder)]
    tags = sorted(t.lower() for t in types)
    if len(graphs) > 1:
        tags.append("subgraph" if any("/" in g for g in graphs) else "variants")
    code = bool(scan_for_code(folder))
    if code:
        tags.append("programs")
    return Entry(key=f"{root}/{folder.name}", root=root, folder=folder, graph=graph, title=title, description=description, readme=readme,
                 tags=tags, inputs=inputs, outputs=outputs, node_types=types, llm_calls=types.get("GENERATE", 0), has_code=code,
                 shipped=not writable, prompts_text="\n".join(prompts)[:MAX_PROMPT_CHARS], graphs=graphs)


def meaning_text(e: Entry) -> str:
    """What is embedded for a recipe: what it is and does, in a few lines (not the prompts, which are about how)."""
    return (f"{e.title}. {e.description[:700]} Steps: {', '.join(e.tags)}. Takes {', '.join(e.inputs) or 'nothing'}; "
            f"gives {', '.join(e.outputs) or 'nothing'}.")


# how the two signals are combined, and how many recipes are kept: the best one, and those close to it
# (measured on the cookbook with qwen3-embedding:0.6b: an unrelated recipe scores about 0.45-0.55 by cosine, a related one 0.6 and up)
BM25_WEIGHT, MARGIN, MEANING_FLOOR, WORDS_FRACTION = 0.25, 0.08, 0.55, 0.40


class RecipeIndex:
    """BM25 plus (when an embedding model is given) meaning, over recipe entries. `RecipeIndex.build(workspace, embedder)` reflects the files
    at that moment. `note` says which signals are in use, for the page to show."""

    def __init__(self, entries: Sequence[Entry], embedder: Optional[Embedder] = None, cache: Optional[VectorCache] = None, note: str = ""):
        self.entries = list(entries)
        self.embedder, self.note, self.error = embedder, note, ""
        self._tf: List[Counter] = []
        self._len: List[int] = []
        df: Counter = Counter()
        for e in self.entries:
            tf: Counter = Counter()
            for name, text in e.fields().items():
                for w in words(text):
                    tf[w] += FIELD_WEIGHT[name]
            self._tf.append(tf)
            self._len.append(sum(tf.values()))
            df.update(tf.keys())
        n = max(1, len(self.entries))
        self._idf = {w: math.log(1 + (n - c + 0.5) / (c + 0.5)) for w, c in df.items()}
        self._avg = (sum(self._len) / len(self._len)) if self._len else 1.0
        self._vectors: Optional[np.ndarray] = None
        self._queries: Dict[str, np.ndarray] = {}            # a query is embedded once (the app searches again on every rerun)
        if embedder is not None and self.entries:
            try:
                self._vectors = (cache or VectorCache(embedder.spec)).vectors([meaning_text(e) for e in self.entries], embedder)
            except Exception as err:                         # the model is not running, a bad reply: carry on with words
                self.error = f"{type(err).__name__}: {err}"
                self.note = f"words only: the embedding model {embedder.spec} failed ({self.error})"

    @property
    def semantic(self) -> bool:
        return self._vectors is not None

    @classmethod
    def build(cls, workspace: Workspace, embedder: Optional[Embedder] = None, note: str = "") -> "RecipeIndex":
        entries: List[Entry] = []
        for root in workspace.roots:
            if not root.path.is_dir():
                continue
            for folder in sorted(p for p in root.path.iterdir() if p.is_dir() and not p.name.startswith(".") and p.name not in {"output", "outputs"}):
                try:
                    entry = describe(root.name, folder, root.writable)
                except OSError:
                    continue
                if entry is not None:
                    entries.append(entry)
        return cls(entries, embedder, note=note or ("words only" if embedder is None else ""))

    @staticmethod
    def signature(workspace: Workspace) -> Tuple:
        """What changes when a recipe is added, removed or edited, so a caller can tell when to rebuild."""
        sig = []
        for root in workspace.roots:
            if root.path.is_dir():
                for p in root.path.glob("*/**/*"):
                    if p.is_file() and p.suffix in {".yaml", ".md"} and "output" not in p.parts:
                        sig.append((str(p), p.stat().st_mtime_ns))
        return tuple(sorted(sig))

    def _bm25(self, q: List[str]) -> Tuple[List[float], List[List[str]]]:
        scores, matched = [], []
        for tf, length in zip(self._tf, self._len):
            score, hit = 0.0, []
            for w in dict.fromkeys(q):
                f = tf.get(w, 0)
                if f:
                    score += self._idf.get(w, 0.0) * f * (K1 + 1) / (f + K1 * (1 - B + B * length / self._avg))
                    hit.append(w)
            scores.append(score)
            matched.append(hit)
        return scores, matched

    def search(self, query: str, k: int = 5, *, allow_code: bool = True, roots: Optional[Sequence[str]] = None, min_matched: int = 1) -> List[Hit]:
        """The best recipes for `query`, best first, at most `k`, and only those close to the best one.

        With an embedding model a recipe qualifies by meaning (cosine at least MEANING_FLOOR, or every word of the request found in it) and is
        ranked by meaning plus a share of the word score; without one it must share at least `min_matched` words (capped at the words asked) and score at least WORDS_FRACTION of
        the best."""
        q = words(query)
        if not q:
            return []
        scores, matched = self._bm25(q)
        best_words = max(scores) if scores else 0.0
        cosines: Optional[np.ndarray] = None
        if self._vectors is not None and self.embedder is not None:
            try:
                if query not in self._queries:
                    self._queries[query] = self.embedder.embed([query])[0]
                cosines = self._vectors @ self._queries[query]
            except Exception as err:                         # the model went away after the index was built
                self.error = f"{type(err).__name__}: {err}"
                self.note = f"words only: the embedding model failed ({self.error})"
        needed = min(max(1, min_matched), len(set(q)))
        pool: List[Hit] = []
        for i, e in enumerate(self.entries):
            if (not allow_code and e.has_code) or (roots is not None and e.root not in roots):
                continue
            rel = scores[i] / best_words if best_words else 0.0
            if cosines is not None:
                exact = len(matched[i]) == len(set(q)) and rel >= 0.5                  # every word asked is in the recipe: an exact term
                if float(cosines[i]) < MEANING_FLOOR and not exact:
                    continue
                pool.append(Hit(e, float(cosines[i]) + BM25_WEIGHT * rel, matched[i], float(cosines[i])))
            elif scores[i] > 0 and len(matched[i]) >= needed:
                pool.append(Hit(e, scores[i], matched[i]))
        pool.sort(key=lambda h: (-h.score, h.entry.key))
        if not pool:
            return []
        top = pool[0].score
        keep = [h for h in pool if (h.score >= top - MARGIN if cosines is not None else h.score >= WORDS_FRACTION * top)]
        return keep[:k]

    def listing(self, *, roots: Optional[Sequence[str]] = None, tag: Optional[str] = None) -> List[Entry]:
        return sorted((e for e in self.entries if (roots is None or e.root in roots) and (tag is None or tag in e.tags)), key=lambda e: e.key)


# ── the recipes as examples for the model ────────────────────────────────────────────────────────

MAX_REFERENCE_GRAPH, MAX_REFERENCE_PROMPTS = 5000, 2500


def reference_text(entries: Sequence[Entry]) -> str:
    """Existing recipes shown to the model as examples: description, graph and prompts, each cut to a size that keeps the prompt small."""
    parts = []
    for e in entries:
        graph = e.graph.read_text(encoding="utf-8", errors="replace")
        prompts = []
        for p in sorted((e.graph.parent / "prompts").glob("*.md")) if (e.graph.parent / "prompts").is_dir() else []:
            prompts.append(f"=== FILE: prompts/{p.name} ===\n{p.read_text(encoding='utf-8', errors='replace').rstrip()}")
        shown = "\n".join(prompts)
        parts.append(f"### Existing recipe `{e.folder.name}`: {e.description}\n\n=== FILE: {e.graph.name} ===\n{graph[:MAX_REFERENCE_GRAPH].rstrip()}"
                     + ("\n(cut short)" if len(graph) > MAX_REFERENCE_GRAPH else "")
                     + (f"\n{shown[:MAX_REFERENCE_PROMPTS]}" + ("\n(cut short)" if len(shown) > MAX_REFERENCE_PROMPTS else "") if shown else ""))
    return "\n\n".join(parts)
