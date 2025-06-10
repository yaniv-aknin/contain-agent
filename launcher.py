#!/usr/bin/env python3

import argparse
import os
import sys
import subprocess
from pathlib import Path


def is_sensitive_directory(path: Path) -> bool:
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
    script_dir = Path(__file__).parent.absolute()
    profiles = {}

    local_profiles_dir = script_dir / "profiles"
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


def main():
    parser = argparse.ArgumentParser(description="Launch Claude Code container")
    parser.add_argument(
        "--no-rm", action="store_true", help="Do not remove container after exit"
    )
    parser.add_argument(
        "--profile", default="default", help="Profile to use (default: default)"
    )
    parser.add_argument(
        "--force", action="store_true", help="Force mounting sensitive directories"
    )
    parser.add_argument(
        "--user", action="store_true", help="Run as an unprivileged user (see README)"
    )
    parser.add_argument(
        "-n",
        "--no-network",
        action="store_true",
        help="Disable network access for the container",
    )
    parser.add_argument(
        "code_dir",
        nargs="?",
        default=os.getcwd(),
        help="Code directory to mount (default: current directory)",
    )
    args = parser.parse_args()

    profiles = get_profile_paths()
    profile_dir = profiles.get(args.profile)
    if not profile_dir:
        print(f"Error: Profile '{args.profile}' not found")
        print("\nAvailable profiles:")
        for name in sorted(profiles.keys()):
            print(f" - {name}")
        sys.exit(1)

    try:
        code_dir = Path(args.code_dir).resolve()
    except Exception as e:
        print(f"Error: Cannot resolve directory '{args.code_dir}' to absolute path")
        sys.exit(1)

    if is_sensitive_directory(code_dir) and not args.force:
        print(
            f"Cowardly refusing to mount directory '{code_dir}'. Use --force to override."
        )
        sys.exit(1)

    print("Launching container with:")
    print(f" - Profile: {args.profile}")
    print(f" - Working directory: {code_dir}")
    if args.no_rm:
        print(" - Container will be preserved after exit")
    else:
        print(" - Container will be removed after exit")
    if args.user:
        print(" - Running as the app user (1000:1000)")
    if args.force:
        print(" - Force flag is enabled (protection bypassed)")
    if args.no_network:
        print(" - Network access disabled")

    docker_cmd = [
        "docker",
        "run",
        "-it",
        *([] if args.no_rm else ["--rm"]),
        *(["--network", "none"] if args.no_network else []),
        *(["--user", "1000:1000"] if args.user else []),
        "-v",
        f"{code_dir}:/app",
    ]

    for profile_path in profile_dir.iterdir():
        home_dir = 'root' if not args.user else 'home/ubuntu'
        docker_cmd.extend(["-v", f"{profile_path}:/{home_dir}/{profile_path.name}"])

    env_file = profile_dir / ".env"
    if env_file.exists():
        print(" - Loading environment from .env")
        docker_cmd.extend(["--env-file", str(env_file)])

    docker_cmd.extend(["contain-agent", "bash"])

    try:
        subprocess.run(docker_cmd)
    except KeyboardInterrupt:
        print("\nContainer launch interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"Error launching container: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
