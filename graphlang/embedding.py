"""The embedding model behind recipe search: which one is used, how texts become vectors, and a cache so a recipe is embedded once.

The choice is the `embedding` setting (Settings page):
  auto                              sentence-transformers if it is installed, else a local Ollama model whose name has "embed"
  none                              no embedding: the search uses words only
  sentence_transformers:<model>     for example sentence_transformers:all-MiniLM-L6-v2 (`pip install sentence-transformers`)
  ollama:<model>                    for example ollama:qwen3-embedding:0.6b (`ollama pull qwen3-embedding:0.6b`)
  <any other dd-embed adapter>:<model>   openai, gemini, voyage ... as dd-embed provides them
Everything goes through dd-embed's adapters. An unavailable choice is not an error: `resolve` returns None and says why, and the search
falls back to words.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Tuple

import numpy as np

from . import workspace

DEFAULT_ST_MODEL = "all-MiniLM-L6-v2"


@dataclass
class Embedder:
    spec: str                                            # "provider:model", what the cache is keyed by
    embed: Callable[[Sequence[str]], np.ndarray]         # texts -> (n, dim), rows normalised to length 1


def _normalise(vectors: np.ndarray) -> np.ndarray:
    vectors = np.asarray(vectors, dtype="float32")
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.where(norms == 0, 1, norms)


def _ollama_models(host: Optional[str] = None) -> List[str]:
    import requests
    host = host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    if not host.startswith("http"):
        host = "http://" + host
    reply = requests.get(f"{host}/api/tags", timeout=2)
    return [m["name"] for m in reply.json().get("models", [])]


def resolve(spec: str = "auto") -> Tuple[Optional[Embedder], str]:
    """(an Embedder or None, a line saying what is used or why nothing is)."""
    spec = (spec or "auto").strip()
    if spec == "none":
        return None, "words only (embedding switched off in Settings)"
    if spec == "auto":
        from importlib.util import find_spec
        if find_spec("sentence_transformers") is not None:
            return resolve(f"sentence_transformers:{DEFAULT_ST_MODEL}")
        try:
            models = [m for m in _ollama_models() if "embed" in m.lower()]
        except Exception:
            models = []
        if models:
            return resolve(f"ollama:{models[0]}")
        return None, ("words only: no embedding model found (install sentence-transformers, or `ollama pull qwen3-embedding:0.6b`, "
                      "or choose one in Settings)")
    provider, _, model = spec.partition(":")
    try:
        import dd_embed
        adapter = dd_embed.get_adapter(provider, **({"model_name": model} if model else {}))
    except ImportError:
        return None, "words only: dd-embed is not installed (`pip install dd-embed`)"
    except Exception as e:                               # an unknown provider, a missing package, a bad setting
        return None, f"words only: embedding {spec!r} is not available ({e})"

    def embed(texts: Sequence[str]) -> np.ndarray:
        result = adapter.embed(list(texts))
        if not result.success:
            raise RuntimeError(result.error or "the embedding call failed")
        return _normalise(result.embeddings)
    return Embedder(spec, embed), f"meaning and words ({spec})"


class VectorCache:
    """text -> vector on disk, one file per embedding model, so a recipe that did not change is not embedded again."""

    def __init__(self, spec: str, folder: Optional[Path] = None):
        folder = Path(folder) if folder else workspace.home() / "cache"
        self.path = folder / f"embeddings-{hashlib.sha1(spec.encode()).hexdigest()[:12]}.json"
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.data = {}
        self._dirty = False

    @staticmethod
    def key(text: str) -> str:
        return hashlib.sha1(text.encode("utf-8")).hexdigest()

    def vectors(self, texts: Sequence[str], embedder: Embedder) -> np.ndarray:
        missing = [t for t in dict.fromkeys(texts) if self.key(t) not in self.data]
        if missing:
            for text, vector in zip(missing, embedder.embed(missing)):
                self.data[self.key(text)] = [float(x) for x in vector]
            self._dirty = True
            self.save()
        return np.array([self.data[self.key(t)] for t in texts], dtype="float32")

    def save(self) -> None:
        if not self._dirty:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.data), encoding="utf-8")
            self._dirty = False
        except OSError:
            pass                                          # a cache that cannot be written only costs time
