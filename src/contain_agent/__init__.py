#!/usr/bin/env python3
"""
Utility to run containerized AI coding agents.
"""

import os
import subprocess
import sys

from pathlib import Path
from typing import Optional
import typer
from typing_extensions import Annotated

from .proxy import NullContext, ProxyContext, MitmContext

DEFAULT_IMAGE = "contain-agent"


def is_sensitive_directory(path: Path) -> bool:
    """Check if a path is a sensitive directory that should not be mounted."""
    sensitive_paths = [
        Path("/"),
        Path("/tmp"),
        Path(os.path.expanduser("~")),  # $HOME
        Path("/etc"),
    ]
    return any(
        path.samefile(sensitive) for sensitive in sensitive_paths if sensitive.exists()
    )


def get_profile_paths() -> dict[str, Path]:
    """Get available profiles from both local ./profiles/ and ~/.contain-agent/."""
    profiles = {}

    local_profiles_dir = Path.cwd() / "profiles"
    if local_profiles_dir.exists():
        for profile_dir in local_profiles_dir.iterdir():
            if profile_dir.is_dir():
                profiles[profile_dir.name] = profile_dir

    home_profiles_dir = Path.home() / ".contain-agent"
    if home_profiles_dir.exists():
        for profile_dir in home_profiles_dir.iterdir():
            if profile_dir.is_dir() and profile_dir.name not in profiles:
                profiles[profile_dir.name] = profile_dir

    return profiles


def get_profile_mounts(profile_dir: Path) -> list:
    """Get list of volume mounts for a profile."""
    mounts = []
    for item in profile_dir.iterdir():
        host_path = str(item.absolute())
        container_path = f"/home/agent/{item.name}"
        mounts.append((host_path, container_path))

    return mounts


def build_docker_command(
    image_name: str,
    workspace_path: str = None,
    proxy_vars: dict[str, str] = None,
    profile_mounts: list = None,
    rm: bool = True,
    env_file_path: Path = None,
    command: list[str] = None,
) -> list:
    """Build the docker run command with appropriate flags."""
    cmd = ["docker", "run"]

    if rm:
        cmd.append("--rm")

    cmd.append("-it")

    if env_file_path and env_file_path.exists():
        cmd.extend(["--env-file", str(env_file_path)])
        print(f" - Loading environment from {env_file_path}")

    if proxy_vars:
        mitmproxy_dir = Path.home() / ".mitmproxy"
        cmd.extend(["-v", f"{mitmproxy_dir}:/home/agent/.mitmproxy:ro"])

        for env_var, value in proxy_vars.items():
            container_value = value.replace(
                str(mitmproxy_dir), "/home/agent/.mitmproxy"
            )
            cmd.extend(["-e", f"{env_var}={container_value}"])

    if workspace_path:
        workspace_abs = os.path.abspath(workspace_path)
        if not os.path.exists(workspace_abs):
            print(
                f"ERROR: Workspace path does not exist: {workspace_abs}",
                file=sys.stderr,
            )
            sys.exit(1)
        cmd.extend(["-v", f"{workspace_abs}:/workspace"])

    if profile_mounts:
        for host_path, container_path in profile_mounts:
            cmd.extend(["-v", f"{host_path}:{container_path}"])

    cmd.append(image_name)

    if command:
        import shlex
        quoted_command = ' '.join(shlex.quote(arg) for arg in command)
        cmd.extend(['bash', '-l', '-i', '-c', quoted_command])

    return cmd


app = typer.Typer(help=f"Run interactive shell with {DEFAULT_IMAGE} container")


def main():
    app()


@app.command(context_settings={"allow_interspersed_args": False})
def run(
    args: Annotated[
        Optional[list[str]],
        typer.Argument(
            help="[MOUNT_DIR] [COMMAND...] - Mount directory (optional) and command to run in container"
        ),
    ] = None,
    dump: Annotated[
        Optional[str], typer.Option(help="Enable mitmproxy and dump traffic to FILE")
    ] = None,
    proxy: Annotated[
        bool,
        typer.Option(
            help="Configure proxy settings without starting mitmdump (you run mitmproxy yourself)"
        ),
    ] = False,
    proxy_host: Annotated[
        str,
        typer.Option(
            help="Proxy host to use (default: host.rancher-desktop.internal:8080)"
        ),
    ] = "host.rancher-desktop.internal:8080",
    mitmproxy_dir: Annotated[
        Optional[Path],
        typer.Option(
            help="Directory to store mitmproxy certificates (default: ~/.mitmproxy)"
        ),
    ] = Path.home() / ".mitmproxy",
    profile: Annotated[
        Optional[str],
        typer.Option(
            help="Mount files/dirs from profile directory to /home/agent/<name>"
        ),
    ] = None,
    no_profile: Annotated[
        bool, typer.Option("--no-profile", help="Do not use default profile")
    ] = False,
    rm: Annotated[bool, typer.Option(help="Remove container after exit")] = True,
    force: Annotated[
        bool, typer.Option(help="Force mounting sensitive directories")
    ] = False,
    mount: Annotated[bool, typer.Option(help="Mount workspace directory")] = True,
    env_file: Annotated[
        Optional[str],
        typer.Option(
            help="Path to .env file to load (default: <profile>/.env if profile is used)"
        ),
    ] = None,
    image: Annotated[str, typer.Option(help="Docker image name")] = DEFAULT_IMAGE,
):
    """Run coding agents in a container."""

    if dump and proxy:
        print("ERROR: --dump and --proxy are mutually exclusive", file=sys.stderr)
        raise typer.Exit(1)

    workspace_arg = None
    command_args = []

    if args:
        if mount:
            if len(args) >= 1:
                first_arg = args[0]
                workspace_arg = first_arg
                command_args = args[1:]
        else:
            command_args = args

    if workspace_arg and not Path(workspace_arg).exists():
        print(f"{workspace_arg} does not exist; perhaps you forgot to use --no-mount?")
        raise typer.Exit(1)

    profile_dir = None
    profile_mounts = None
    env_file_path = None

    if not profile and not no_profile:
        default_profile_path = Path.home() / ".contain-agent" / "default"
        if default_profile_path.exists() and default_profile_path.is_dir():
            profile = "default"

    if profile:
        profiles = get_profile_paths()
        profile_dir = profiles.get(profile)
        if not profile_dir:
            print(f"Error: Profile '{profile}' not found")
            print("\nAvailable profiles:")
            for name in sorted(profiles.keys()):
                print(f" - {name}")
            raise typer.Exit(1)

        profile_mounts = get_profile_mounts(profile_dir)
        print(f"Using profile '{profile}' from {profile_dir}")
        print(f"Mounting {len(profile_mounts)} items from profile:")
        for host_path, container_path in profile_mounts:
            print(f"  {host_path} -> {container_path}")

        if not env_file:
            env_file_path = profile_dir / ".env"

    if env_file:
        try:
            env_file_path = Path(env_file).resolve()
        except Exception:
            print(f"Error: Cannot resolve env file path '{env_file}'")
            raise typer.Exit(1)

    workspace_path = None
    if mount:
        if not workspace_arg:
            workspace_arg = os.getcwd()

        try:
            workspace_path = Path(workspace_arg).resolve()
        except Exception:
            print(f"Error: Cannot resolve directory '{workspace_arg}' to absolute path")
            raise typer.Exit(1)

        if is_sensitive_directory(workspace_path) and not force:
            print(
                f"Cowardly refusing to mount directory '{workspace_path}'. Use --force to override."
            )
            raise typer.Exit(1)

    print("\nLaunching container with:")
    if profile:
        print(f" - Profile: {profile}")
    if workspace_path:
        print(f" - Working directory: {workspace_path}")
    else:
        print(" - No workspace mounted")
    if command_args:
        print(f" - Command: {' '.join(command_args)}")
    if rm:
        print(" - Container will be removed after exit")
    else:
        print(" - Container will be preserved after exit")
    if force:
        print(" - Force flag is enabled (protection bypassed)")

    if dump:
        context = MitmContext(
            proxy_host=proxy_host,
            mitmproxy_dir=mitmproxy_dir,
            dump_file=dump,
        )
    elif proxy:
        context = ProxyContext(
            proxy_host=proxy_host,
            mitmproxy_dir=mitmproxy_dir,
        )
    else:
        context = NullContext()

    docker_cmd = build_docker_command(
        image,
        workspace_path=str(workspace_path) if workspace_path else None,
        proxy_vars=context.env,
        profile_mounts=profile_mounts,
        rm=rm,
        env_file_path=env_file_path,
        command=command_args if command_args else None,
    )

    print(f"\nStarting container: {' '.join(docker_cmd)}\n")

    try:
        with context:
            if not mitmproxy_dir.exists():
                print(
                    f"ERROR: {mitmproxy_dir} directory not found. Please run 'mitmproxy' once to generate certificates."
                )
                raise typer.Exit(1)
            result = subprocess.run(docker_cmd)
        exit_code = result.returncode
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        exit_code = 130

    raise typer.Exit(exit_code)
