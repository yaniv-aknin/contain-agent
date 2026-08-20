import json
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError


class Settings(BaseModel):
    default_command: str | None = None
    default_args: list[str] = Field(default_factory=list)


def load_settings(settings_path: Path | None = None) -> Settings:
    """Load settings from ~/.contain-agent/settings.json if it exists."""
    path = (
        settings_path
        if settings_path is not None
        else (Path.home() / ".contain-agent" / "settings.json")
    )
    if path.is_file():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return Settings.model_validate(data)
        except json.JSONDecodeError, ValidationError, OSError:
            return Settings()
    return Settings()


settings: Settings = load_settings()
