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

from .proxy import (
    find_free_port,
    get_proxy_env,
    get_transparent_proxy_env,
    start_mitmdump,
    stop_mitmdump,
)

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
    net_admin: bool = True,
    cert_dir: Path = None,
) -> list:
    """Build the docker run command with appropriate flags."""
    cmd = ["docker", "run"]

    if rm:
        cmd.append("--rm")

    cmd.append("-it")

    if net_admin:
        cmd.extend(["--cap-add", "NET_ADMIN"])

    if env_file_path and env_file_path.exists():
        cmd.extend(["--env-file", str(env_file_path)])
        print(f" - Loading environment from {env_file_path}")

    if proxy_vars and cert_dir:
        cmd.extend(["-v", f"{cert_dir}:/home/agent/.certs:ro"])

        for env_var, value in proxy_vars.items():
            container_value = value.replace(
                str(cert_dir), "/home/agent/.certs"
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
        Optional[str], typer.Option(help="Start proxy and dump traffic: [executable:]file")
    ] = None,
    dump_file: Annotated[
        Optional[str], typer.Option(help="File to dump traffic to")
    ] = None,
    dump_executable: Annotated[
        str,
        typer.Option(
            help="Executable to use for dumping (default: mitmdump)"
        ),
    ] = "mitmdump",
    proxy_type: Annotated[
        Optional[str],
        typer.Option(
            help="Proxy type: 'http' for HTTP_PROXY env vars, 'transparent' for transparent proxying with xproxy"
        ),
    ] = None,
    proxy_host: Annotated[
        str,
        typer.Option(
            help="Proxy hostname (default: host.rancher-desktop.internal)"
        ),
    ] = "host.rancher-desktop.internal",
    proxy_port: Annotated[
        Optional[int],
        typer.Option(
            help="Proxy port to use (default: 8080)"
        ),
    ] = None,
    ca_cert: Annotated[
        Optional[Path],
        typer.Option(
            help="CA certificate file for proxy HTTPS interception (default: ~/.mitmproxy/mitmproxy-ca-cert.pem)"
        ),
    ] = Path.home() / ".mitmproxy" / "mitmproxy-ca-cert.pem",
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
    net_admin: Annotated[
        bool, typer.Option(help="Grant NET_ADMIN capability (allows iptables)")
    ] = False,
    no_net_admin: Annotated[
        bool, typer.Option(help="Explicitly disable NET_ADMIN capability")
    ] = False,
):
    """Run coding agents in a container."""

    if dump is not None:
        if ":" in dump:
            exec_name, file_name = dump.split(":", 1)
            if dump_file is None:
                dump_file = file_name
            if dump_executable == "mitmdump":
                dump_executable = exec_name
        else:
            if dump_file is None:
                dump_file = dump

    if dump is None and dump_file is None:
        if dump_executable != "mitmdump":
            print("ERROR: --dump-executable requires --dump or --dump-file to be specified", file=sys.stderr)
            raise typer.Exit(1)

    if dump_file is not None and proxy_port is None:
        proxy_port = find_free_port()

    use_proxy = dump_file is not None or proxy_port is not None or proxy_type is not None

    if use_proxy and proxy_type is None:
        proxy_type = "http"

    if use_proxy and proxy_port is None:
        proxy_port = 8080

    if proxy_type is not None and proxy_type not in ("http", "transparent"):
        print(f"ERROR: --proxy-type must be 'http' or 'transparent', got '{proxy_type}'", file=sys.stderr)
        raise typer.Exit(1)

    if proxy_type == "transparent" and no_net_admin:
        print("ERROR: --proxy-type transparent requires NET_ADMIN capability, cannot use with --no-net-admin", file=sys.stderr)
        raise typer.Exit(1)

    effective_net_admin = net_admin or (proxy_type == "transparent")
    if no_net_admin:
        effective_net_admin = False

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

    mitm_process = None
    proxy_vars = {}
    cert_dir = None

    if use_proxy:
        if not ca_cert.exists():
            print(f"ERROR: CA certificate not found at {ca_cert}")
            print("Please run 'mitmproxy' once to generate certificates, or specify --ca-cert")
            raise typer.Exit(1)

        cert_dir = ca_cert.parent
        container_cert_path = Path("/home/agent/.certs") / ca_cert.name

        if dump_file:
            mitm_process, actual_port = start_mitmdump(dump_file, proxy_port, dump_executable)
        else:
            actual_port = proxy_port

        if proxy_type == "http":
            proxy_vars = get_proxy_env(proxy_host, actual_port, container_cert_path)
        elif proxy_type == "transparent":
            proxy_vars = get_transparent_proxy_env(proxy_host, actual_port, container_cert_path)

    docker_cmd = build_docker_command(
        image,
        workspace_path=str(workspace_path) if workspace_path else None,
        proxy_vars=proxy_vars if proxy_vars else None,
        profile_mounts=profile_mounts,
        rm=rm,
        env_file_path=env_file_path,
        command=command_args if command_args else None,
        net_admin=effective_net_admin,
        cert_dir=cert_dir,
    )

    print(f"\nStarting container: {' '.join(docker_cmd)}\n")

    try:

        result = subprocess.run(docker_cmd)
        exit_code = result.returncode
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        exit_code = 130
    finally:
        if mitm_process:
            stop_mitmdump(mitm_process, dump_file)

    raise typer.Exit(exit_code)
