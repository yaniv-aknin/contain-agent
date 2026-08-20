from pathlib import Path

from contain_agent.constants import KNOWN_CONFIG_NAMES, SENSITIVE_DIRECTORIES


def is_sensitive_directory(path: Path) -> bool:
    """Check if a path is a sensitive directory that should not be mounted without --force."""
    try:
        resolved = path.resolve()
    except OSError:
        return False

    for sensitive in SENSITIVE_DIRECTORIES:
        try:
            if sensitive.exists() and resolved == sensitive.resolve():
                return True
        except OSError:
            continue
    return False


def get_config_mounts(share_config: bool, dotfiles_dir: Path) -> list[tuple[str, str]]:
    """Determine volume mounts for agent configuration / dotfiles."""
    mounts: list[tuple[str, str]] = []

    if share_config:
        home = Path.home()
        for name in KNOWN_CONFIG_NAMES:
            host_path = home / name
            if host_path.exists():
                mounts.append((str(host_path.resolve()), f"/home/agent/{name}"))
    else:
        if dotfiles_dir.exists() and dotfiles_dir.is_dir():
            for item in sorted(dotfiles_dir.iterdir()):
                mounts.append((str(item.resolve()), f"/home/agent/{item.name}"))

    return mounts
