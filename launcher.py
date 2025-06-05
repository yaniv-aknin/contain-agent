#!/usr/bin/env python3

import argparse
import os
import sys
import subprocess
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description='Launch Claude Code container')
    parser.add_argument('--no-rm', action='store_true', help='Do not remove container after exit')
    parser.add_argument('code_dir', nargs='?', default=os.getcwd(), help='Code directory to mount (default: current directory)')
    args = parser.parse_args()

    # Get the directory where the script is located
    script_dir = Path(__file__).parent.absolute()

    # Find credentials relative to the script location
    claude_json = script_dir / "claude.json"
    dot_claude = script_dir / "dot-claude"

    # Check if credentials exist
    if not claude_json.exists():
        print(f"Error: claude.json not found at {claude_json}")
        sys.exit(1)

    if not dot_claude.exists():
        print(f"Error: dot-claude directory not found at {dot_claude}")
        sys.exit(1)

    # Determine the code directory
    try:
        code_dir = Path(args.code_dir).resolve()
    except Exception as e:
        print(f"Error: Cannot resolve directory '{args.code_dir}' to absolute path")
        sys.exit(1)

    print("Launching Claude Code container with:")
    print(f" - Credentials from: {script_dir}")
    print(f" - Working directory: {code_dir}")
    if args.no_rm:
        print(" - Container will be preserved after exit")
    else:
        print(" - Container will be removed after exit")

    # Build docker command
    docker_cmd = [
        "docker", "run", "-it",
        *([] if args.no_rm else ["--rm"]),
        "-v", f"{claude_json}:/root/.claude.json",
        "-v", f"{dot_claude}:/root/.claude",
        "-v", f"{code_dir}:/app",
        "claude-code", "bash"
    ]

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