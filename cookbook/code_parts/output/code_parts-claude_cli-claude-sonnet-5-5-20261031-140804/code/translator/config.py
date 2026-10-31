"""Settings and adapter registry for the translator chatbot."""
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

DEFAULT_ADAPTER = os.environ.get("TRANSLATOR_ADAPTER", "claude_cli")
DEFAULT_MODEL = os.environ.get("TRANSLATOR_MODEL", "claude-sonnet-5-5")

MAX_INPUT_CHARS = 8000
MAX_OUTPUT_TOKENS = 4096
TIMEOUT_SECONDS = 120

AUTO_DETECT = "Auto-detect"

LANGUAGES: List[str] = [
    AUTO_DETECT, "English", "Chinese (Simplified)", "Chinese (Traditional)",
    "Spanish", "French", "German", "Japanese", "Korean", "Portuguese",
    "Italian", "Russian", "Arabic", "Hindi", "Dutch", "Turkish", "Vietnamese",
]


@dataclass(frozen=True)
class AdapterInfo:
    key_env: Optional[str]
    models: List[str]


CLAUDE_MODELS = ["claude-sonnet-5-5", "claude-opus-5-5", "claude-haiku-5-5"]

ADAPTERS: Dict[str, AdapterInfo] = {
    "claude_cli": AdapterInfo(None, CLAUDE_MODELS),
    "anthropic": AdapterInfo("ANTHROPIC_API_KEY", CLAUDE_MODELS),
    "openai": AdapterInfo("OPENAI_API_KEY", ["gpt-4o", "gpt-4o-mini"]),
    "gemini": AdapterInfo("GEMINI_API_KEY", ["gemini-2.0-flash", "gemini-1.5-pro"]),
}


def default_model_for(adapter: str) -> str:
    """Env/default model for the default adapter, else the adapter's first suggestion."""
    if adapter == DEFAULT_ADAPTER and DEFAULT_MODEL:
        return DEFAULT_MODEL
    return ADAPTERS[adapter].models[0]


@dataclass
class LLMSettings:
    adapter: str = DEFAULT_ADAPTER
    model: str = DEFAULT_MODEL
    api_key: str = field(default="", repr=False)

    def effective_api_key(self) -> str:
        """API key from the settings, else from the adapter's environment variable."""
        if self.api_key:
            return self.api_key
        info = ADAPTERS.get(self.adapter)
        if info and info.key_env:
            return os.environ.get(info.key_env, "")
        return ""
