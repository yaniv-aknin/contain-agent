import shlex
import subprocess
import sys
from pathlib import Path
from typing import Annotated

import typer

from contain_agent.constants import DEFAULT_IMAGE
from contain_agent.docker import (
    build_docker_command,
    build_image_command,
    check_image_exists,
)
from contain_agent.paths import get_config_mounts, is_sensitive_directory
from contain_agent.settings import load_settings

app = typer.Typer(
    help="A lightweight tool to run AI coding agents inside isolated Docker containers.",
    add_completion=False,
    context_settings={"allow_interspersed_args": False},
)


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

    current_settings = load_settings()
    if not command_args and current_settings.default_command:
        command_args = [
            current_settings.default_command,
            *current_settings.default_args,
        ]

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


def main() -> None:
    app()
