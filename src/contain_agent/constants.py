from pathlib import Path

DEFAULT_IMAGE = "contain-agent"

KNOWN_CONFIG_NAMES = [
    ".claude",
    ".claude.json",
    ".gemini",
    ".codex",
    ".anthropic",
    ".openai",
]

SENSITIVE_DIRECTORIES = [
    Path("/"),
    Path("/tmp"),
    Path.home(),
    Path("/etc"),
    Path("/var"),
    Path("/usr"),
    Path("/System"),
    Path("/Library"),
    Path("/Applications"),
]
