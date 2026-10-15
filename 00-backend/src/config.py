import json
import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    ollama_url: str = os.getenv("HIVEMIND_OLLAMA_URL", "http://localhost:11434")
    # LM Studio serves the OpenAI shape, base path included. Any
    # OpenAI-compatible endpoint can stand in for the local server: the key and
    # extra headers are configuration too (a hosted gateway needs a session
    # header and a real key; a local LM Studio ignores both).
    lmstudio_url: str = os.getenv("HIVEMIND_LMSTUDIO_URL", "http://localhost:1234/v1")
    lmstudio_api_key: str = os.getenv("HIVEMIND_LMSTUDIO_API_KEY", "lm-studio")
    lmstudio_headers: str = os.getenv("HIVEMIND_LMSTUDIO_HEADERS", "")
    title_provider: str = os.getenv("HIVEMIND_TITLE_PROVIDER", "ollama")
    # Titles are very short calls, so the smallest model is the right default.
    title_model: str = os.getenv("HIVEMIND_TITLE_MODEL", "qwen2.5:7b")
    # Applies to any turn whose agent names no word limit of its own. Raise it
    # if a team legitimately needs longer answers than roughly 700 words.
    max_output_tokens: int = int(os.getenv("HIVEMIND_MAX_OUTPUT_TOKENS", "1024"))
    # Off by default: see the note in provider.chat.
    ollama_thinking: bool = os.getenv("HIVEMIND_OLLAMA_THINKING", "").lower() in {
        "1",
        "true",
        "yes",
    }
    host: str = os.getenv("HIVEMIND_HOST", "127.0.0.1")
    port: int = int(os.getenv("HIVEMIND_PORT", "8000"))
    data_dir: Path = Path(os.getenv("HIVEMIND_DATA_DIR", ROOT / "data"))
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            os.getenv("HIVEMIND_CORS_ORIGINS", "http://localhost:5173").split(",")
        )
    )

    @property
    def db_path(self) -> Path:
        return self.data_dir / "hivemind.db"

    @property
    def lmstudio_header_dict(self) -> dict[str, str]:
        """Extra headers for the OpenAI-compatible engine, best-effort.

        A malformed value is ignored rather than fatal: a typo in an optional
        header must not take the whole debate down.
        """
        if not self.lmstudio_headers:
            return {}
        try:
            parsed = json.loads(self.lmstudio_headers)
        except json.JSONDecodeError:
            return {}
        if not isinstance(parsed, dict):
            return {}
        return {str(key): str(value) for key, value in parsed.items()}

    @property
    def checkpoints_path(self) -> Path:
        return self.data_dir / "checkpoints.db"
