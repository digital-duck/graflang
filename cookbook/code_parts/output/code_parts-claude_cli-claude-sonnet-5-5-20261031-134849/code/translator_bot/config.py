"""Settings and defaults."""

from dataclasses import dataclass, field
from typing import Dict, Optional

DEFAULT_ADAPTER = "claude_cli"
DEFAULT_MODEL = "claude-sonnet-5-5"
ADAPTERS = ["claude_cli", "anthropic", "openai", "gemini"]

# Default model per adapter. Unknown adapters fall back to DEFAULT_MODEL
# only when the adapter is a Claude one; otherwise the model must be given.
DEFAULT_MODELS: Dict[str, str] = {
    "claude_cli": "claude-sonnet-5-5",
    "anthropic": "claude-sonnet-5-5",
    "openai": "gpt-4o",
    "gemini": "gemini-2.0-flash",
}

LANGUAGES = [
    "English", "Chinese", "Spanish", "French", "German", "Japanese",
    "Korean", "Portuguese", "Italian", "Russian", "Arabic", "Hindi",
]
AUTO_DETECT = "Auto-detect"

DEFAULT_TIMEOUT = 120.0
MAX_HISTORY = 50

# Adapters that authenticate through their own login and ignore API keys.
KEYLESS_ADAPTERS = {"claude_cli"}


def default_model_for(adapter: str) -> str:
    """Default model for an adapter ('' if unknown)."""
    return DEFAULT_MODELS.get(adapter, "")


@dataclass
class Settings:
    adapter: str = DEFAULT_ADAPTER
    model: str = DEFAULT_MODEL
    api_key: Optional[str] = field(default=None, repr=False)
    source_lang: str = AUTO_DETECT
    target_lang: str = "English"
    timeout: float = DEFAULT_TIMEOUT
