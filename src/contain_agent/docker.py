import os
import shlex
import subprocess
import time
from importlib.resources import files
from pathlib import Path

from contain_agent.constants import DEFAULT_IMAGE


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
