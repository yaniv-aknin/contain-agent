#!/usr/bin/env python3

import argparse
import os
import sys
import subprocess
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description='Launch Claude Code container')
    parser.add_argument('--no-rm', action='store_true', help='Do not remove container after exit')
    parser.add_argument('--profile', default='default', help='Profile to use (default: default)')
    parser.add_argument('code_dir', nargs='?', default=os.getcwd(), help='Code directory to mount (default: current directory)')
    args = parser.parse_args()

    # Get the directory where the script is located
    script_dir = Path(__file__).parent.absolute()

    # Find profile directory
    profile_dir = script_dir / "profiles" / args.profile
    if not profile_dir.exists():
        print(f"Error: Profile '{args.profile}' not found at {profile_dir}")
        sys.exit(1)

    # Determine the code directory
    try:
        code_dir = Path(args.code_dir).resolve()
    except Exception as e:
        print(f"Error: Cannot resolve directory '{args.code_dir}' to absolute path")
        sys.exit(1)

    print("Launching container with:")
    print(f" - Profile: {args.profile}")
    print(f" - Working directory: {code_dir}")
    if args.no_rm:
        print(" - Container will be preserved after exit")
    else:
        print(" - Container will be removed after exit")

    # Build docker command
    docker_cmd = [
        "docker", "run", "-it",
        *([] if args.no_rm else ["--rm"]),
        "-v", f"{code_dir}:/app",
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