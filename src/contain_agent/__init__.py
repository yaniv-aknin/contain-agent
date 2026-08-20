"""contain-agent: A lightweight tool to run AI coding agents inside isolated Docker containers."""

from contain_agent.cli import app, run
from contain_agent.constants import (
    DEFAULT_IMAGE,
    KNOWN_CONFIG_NAMES,
    SENSITIVE_DIRECTORIES,
)
from contain_agent.docker import (
    build_docker_command,
    build_image_command,
    check_image_exists,
    get_docker_cmd,
    get_docker_context,
)
from contain_agent.paths import (
    get_config_mounts,
    is_sensitive_directory,
)
from contain_agent.settings import (
    Settings,
    load_settings,
    settings,
)

__all__ = [
    "DEFAULT_IMAGE",
    "KNOWN_CONFIG_NAMES",
    "SENSITIVE_DIRECTORIES",
    "Settings",
    "app",
    "build_docker_command",
    "build_image_command",
    "check_image_exists",
    "get_config_mounts",
    "get_docker_cmd",
    "get_docker_context",
    "is_sensitive_directory",
    "load_settings",
    "run",
    "settings",
]
