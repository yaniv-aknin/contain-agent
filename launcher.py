#!/usr/bin/env python3

import argparse
import os
import sys
import subprocess
from pathlib import Path


def is_sensitive_directory(path: Path) -> bool:
    """Check if the given path is a sensitive directory that should be protected."""
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
    """Get a dictionary mapping profile names to their absolute paths.

    Searches both the local profiles directory and ~/.contain-agent.
    Local profiles take precedence over home profiles if there are duplicates.
    """
    script_dir = Path(__file__).parent.absolute()
    profiles = {}

    # Check local profiles first (they take precedence)
    local_profiles_dir = script_dir / "profiles"
    if local_profiles_dir.exists():
        for profile_dir in local_profiles_dir.iterdir():
            if profile_dir.is_dir():
                profiles[profile_dir.name] = profile_dir

    # Then check ~/.contain-agent
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
        "code_dir",
        nargs="?",
        default=os.getcwd(),
        help="Code directory to mount (default: current directory)",
    )
    args = parser.parse_args()

    # Find profile directory
    profiles = get_profile_paths()
    profile_dir = profiles.get(args.profile)
    if not profile_dir:
        print(f"Error: Profile '{args.profile}' not found")
        print("\nAvailable profiles:")
        for name in sorted(profiles.keys()):
            print(f" - {name}")
        sys.exit(1)

    # Determine the code directory
    try:
        code_dir = Path(args.code_dir).resolve()
    except Exception as e:
        print(f"Error: Cannot resolve directory '{args.code_dir}' to absolute path")
        sys.exit(1)

    # Check for sensitive directories
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
    if args.force:
        print(" - Force flag is enabled (protection bypassed)")

    # Build docker command
    docker_cmd = [
        "docker",
        "run",
        "-it",
        *([] if args.no_rm else ["--rm"]),
        "-v",
        f"{code_dir}:/app",
    ]

    # Add all top-level files and directories from the profile directory as volume mounts
    for profile_path in profile_dir.iterdir():
        # Mount to /root maintaining the same name
        docker_cmd.extend(["-v", f"{profile_path}:/root/{profile_path.name}"])

    # Check for .env file and add it to environment
    env_file = profile_dir / ".env"
    if env_file.exists():
        print(" - Loading environment from .env")
        docker_cmd.extend(["--env-file", str(env_file)])

    # Add the container name and command
    docker_cmd.extend(["contain-agent", "bash"])

    # Run the container
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
