"""3-tier resource resolver for GraphLang."""

from pathlib import Path
from typing import Any, Dict, Optional

SUFFIX = {"procedures": ".spl", "prompts": ".md", "policies": ".cedar"}


class ResourceResolver:
    """Resolves Tier 2 resources (procedures, prompts, policies).

    A reference is `<type>.<name>` (as in `prompts.draft`) or a bare name. The path comes from the
    graph's `resources` block when it lists the name (relative to the graph file's folder); otherwise
    from the convention `<base_dir>/<type>/<name><suffix>`.
    """

    def __init__(self, base_dir: Path, resources: Optional[Dict[str, Dict[str, str]]] = None):
        self.base_dir = Path(base_dir)
        self.resources = resources or {}
        self._cache: Dict[str, Any] = {}

    def path_for(self, ref: str, resource_type: str) -> Path:
        if resource_type not in SUFFIX:
            raise ValueError(f"Unknown resource type: {resource_type}")
        name = ref.removeprefix(f"{resource_type}.")
        declared = self.resources.get(resource_type, {}).get(name)
        if declared:
            return (self.base_dir / declared).resolve()
        return self.base_dir / resource_type / f"{name.replace('.', '/')}{SUFFIX[resource_type]}"

    def resolve(self, ref: str, resource_type: str) -> Any:
        """Resolve a resource reference."""
        cache_key = f"{resource_type}:{ref}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        file_path = self.path_for(ref, resource_type)
        if not file_path.exists():
            raise FileNotFoundError(f"Resource not found: {ref} (expected at {file_path})")
        if resource_type == "procedures":
            # For now, just return the file path; a later step parses the SPL file into a sub-graph
            content = {"type": "procedure", "path": str(file_path)}
        elif resource_type == "prompts":
            content = {"type": "prompt", "content": file_path.read_text(encoding="utf-8")}
        else:
            content = {"type": "policy", "content": file_path.read_text(encoding="utf-8")}
        self._cache[cache_key] = content
        return content
