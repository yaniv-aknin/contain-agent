import json
import os
import shlex
import subprocess
import sys
import time
from importlib.resources import files
from pathlib import Path
from typing import Annotated

import typer
from pydantic import BaseModel, Field, ValidationError

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

app = typer.Typer(
    help="A lightweight tool to run AI coding agents inside isolated Docker containers.",
    add_completion=False,
    context_settings={"allow_interspersed_args": False},
)


def get_docker_cmd() -> str:
    """Get the docker command binary name or path."""
    return os.environ.get("CONTAIN_AGENT_DOCKER_CMD", "docker")


def get_docker_context() -> tuple[Path, Path]:
    """Locate the packaged Dockerfile and its build context directory."""
    try:
        pkg_root = files("contain_agent")
        dockerfile = pkg_root / "Dockerfile"
        if dockerfile.is_file():
            return Path(str(dockerfile)), Path(str(pkg_root))
    except TypeError, OSError, AttributeError:
        pass

    current = Path(__file__).resolve().parent
    if (current / "Dockerfile").is_file():
        return current / "Dockerfile", current

    raise FileNotFoundError("Could not find Dockerfile for contain-agent.")


def build_image_command(
    image: str,
    no_cache: bool = False,
    fresh_rebuild: bool = False,
    cache_bust_value: str | None = None,
    uid: int | None = None,
) -> list[str]:
    """Build the docker build command line."""
    dockerfile_path, context_dir = get_docker_context()
    effective_uid = (
        uid if uid is not None else (os.getuid() if hasattr(os, "getuid") else 1000)
    )
    cmd = [
        get_docker_cmd(),
        "build",
        "-t",
        image,
        "-f",
        str(dockerfile_path.resolve()),
        "--build-arg",
        f"UID={effective_uid}",
    ]
    if no_cache:
        cmd.append("--no-cache")
    elif fresh_rebuild:
        val = cache_bust_value or str(int(time.time()))
        cmd.extend(["--build-arg", f"CACHE_BUST={val}"])

    cmd.append(str(context_dir.resolve()))
    return cmd


def is_sensitive_directory(path: Path) -> bool:
    """Check if a path is a sensitive directory that should not be mounted without --force."""
    try:
        resolved = path.resolve()
    except OSError:
        return False

    sensitive_candidates = [
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

    for sensitive in sensitive_candidates:
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


def build_docker_command(
    image: str = DEFAULT_IMAGE,
    workspace_path: Path | None = None,
    config_mounts: list[tuple[str, str]] | None = None,
    env_file_path: Path | None = None,
    command: list[str] | None = None,
    network: str | None = None,
    rm: bool = True,
    interactive: bool = True,
) -> list[str]:
    """Build the docker run command line."""
    cmd = [get_docker_cmd(), "run"]

    if rm:
        cmd.append("--rm")

    if interactive:
        cmd.append("-it")
    else:
        cmd.append("-i")

    if network:
        cmd.extend(["--network", network])

    if env_file_path and env_file_path.exists():
        cmd.extend(["--env-file", str(env_file_path.resolve())])

    if config_mounts:
        for host_path, container_path in config_mounts:
            cmd.extend(["-v", f"{host_path}:{container_path}"])

    if workspace_path:
        workspace_resolved = workspace_path.resolve()
        basename = workspace_resolved.name
        container_workspace = f"/workspace/{basename}"
        cmd.extend(["-v", f"{workspace_resolved}:{container_workspace}"])
        cmd.extend(["-w", container_workspace])
    else:
        cmd.extend(["-w", "/workspace"])

    cmd.append(image)

    if command:
        quoted_command = " ".join(shlex.quote(arg) for arg in command)
        cmd.extend(["bash", "-l", "-i", "-c", quoted_command])
    else:
        cmd.extend(["bash", "-l", "-i"])

    return cmd


def check_image_exists(image: str) -> bool:
    """Check if the Docker image exists locally."""
    try:
        res = subprocess.run(
            [get_docker_cmd(), "image", "inspect", image],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return res.returncode == 0
    except FileNotFoundError, OSError:
        return True


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


@app.command()
def run(
    args: Annotated[
        list[str] | None,
        typer.Argument(
            help="[MOUNT_DIR] [COMMAND...] - Directory to mount and command to execute inside container"
        ),
    ] = None,
    mount: Annotated[
        bool,
        typer.Option("--mount/--no-mount", help="Mount workspace directory"),
    ] = True,
    share_config: Annotated[
        bool,
        typer.Option(
            "--share-config/--no-share-config",
            help="Mount agent configuration from host home directory",
        ),
    ] = True,
    dotfiles_dir: Annotated[
        Path | None,
        typer.Option(
            "--dotfiles-dir",
            help="Directory for dotfiles when --no-share-config is used (default: ~/.contain-agent/dotfiles)",
        ),
    ] = None,
    env_file: Annotated[
        Path | None,
        typer.Option(
            "--env-file",
            help="Path to .env file to load (default: ~/.contain-agent/.env if present)",
        ),
    ] = None,
    no_env_file: Annotated[
        bool,
        typer.Option("--no-env-file", help="Do not load any .env file"),
    ] = False,
    image: Annotated[
        str,
        typer.Option("--image", help="Docker image to run"),
    ] = DEFAULT_IMAGE,
    network: Annotated[
        str | None,
        typer.Option("--network", help="Docker network to connect container to"),
    ] = None,
    build_image: Annotated[
        bool,
        typer.Option(
            "--build-image",
            help="Build image before running (cache hit if built)",
        ),
    ] = False,
    fresh_rebuild_image: Annotated[
        bool,
        typer.Option(
            "--fresh-rebuild-image",
            help="Rebuild image updating agents (busts agent cache)",
        ),
    ] = False,
    no_cache_rebuild_image: Annotated[
        bool,
        typer.Option(
            "--no-cache-rebuild-image",
            help="Rebuild image from scratch (no cache)",
        ),
    ] = False,
    rm: Annotated[
        bool,
        typer.Option("--rm/--no-rm", help="Remove container automatically after exit"),
    ] = True,
    force: Annotated[
        bool,
        typer.Option("-f", "--force", help="Allow mounting sensitive host directories"),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Print the docker command without executing it"),
    ] = False,
) -> None:
    """Run AI coding agents in an isolated Docker container."""
    workspace_path: Path | None = None
    command_args: list[str] = []

    if mount:
        if args:
            workspace_arg = args[0]
            command_args = args[1:]
            workspace_path = Path(workspace_arg)
        else:
            workspace_path = Path.cwd()

        if not workspace_path.exists():
            print(
                f"Error: Directory '{workspace_path}' does not exist (did you forget --no-mount?)",
                file=sys.stderr,
            )
            raise typer.Exit(1)

        try:
            workspace_path = workspace_path.resolve()
        except OSError as e:
            print(
                f"Error: Cannot resolve directory '{workspace_path}': {e}",
                file=sys.stderr,
            )
            raise typer.Exit(1)

        if is_sensitive_directory(workspace_path) and not force:
            print(
                f"Cowardly refusing to mount sensitive directory '{workspace_path}'. Use --force to override.",
                file=sys.stderr,
            )
            raise typer.Exit(1)
    else:
        if args:
            command_args = args

    if not command_args and settings.default_command:
        command_args = [settings.default_command, *settings.default_args]

    # Determine env file
    env_file_path: Path | None = None
    if not no_env_file:
        if env_file:
            if not env_file.exists() or not env_file.is_file():
                print(
                    f"Error: Specified env file '{env_file}' does not exist.",
                    file=sys.stderr,
                )
                raise typer.Exit(1)
            env_file_path = env_file
        else:
            default_env = Path.home() / ".contain-agent" / ".env"
            if default_env.is_file():
                env_file_path = default_env

    # Determine config mounts
    effective_dotfiles_dir = (
        dotfiles_dir
        if dotfiles_dir is not None
        else (Path.home() / ".contain-agent" / "dotfiles")
    )
    config_mounts = get_config_mounts(share_config, effective_dotfiles_dir)

    image_exists = check_image_exists(image)
    should_build = (
        build_image or fresh_rebuild_image or no_cache_rebuild_image or not image_exists
    )

    if should_build:
        if not (build_image or fresh_rebuild_image or no_cache_rebuild_image):
            print(
                f"Docker image '{image}' not found locally. Building it...",
                file=sys.stderr,
            )
        b_cmd = build_image_command(
            image=image,
            no_cache=no_cache_rebuild_image,
            fresh_rebuild=fresh_rebuild_image,
        )
        if dry_run:
            print(" ".join(shlex.quote(arg) for arg in b_cmd))
        else:
            try:
                build_res = subprocess.run(b_cmd, check=False)
                if build_res.returncode != 0:
                    raise typer.Exit(build_res.returncode)
            except FileNotFoundError:
                print(
                    "Error: 'docker' command not found. Please ensure Docker is installed and in your PATH.",
                    file=sys.stderr,
                )
                raise typer.Exit(1)

    docker_cmd = build_docker_command(
        image=image,
        workspace_path=workspace_path,
        config_mounts=config_mounts,
        env_file_path=env_file_path,
        command=command_args,
        network=network,
        rm=rm,
        interactive=sys.stdin.isatty(),
    )

    if dry_run:
        print(" ".join(shlex.quote(arg) for arg in docker_cmd))
        raise typer.Exit(0)

    try:
        result = subprocess.run(docker_cmd, check=False)
        raise typer.Exit(result.returncode)
    except FileNotFoundError:
        print(
            "Error: 'docker' command not found. Please ensure Docker is installed and in your PATH.",
            file=sys.stderr,
        )
        raise typer.Exit(1)
    except KeyboardInterrupt:
        raise typer.Exit(130)
