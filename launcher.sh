#!/bin/bash

# Default to removing container when done
REMOVE_FLAG="--rm"

# Check for --no-rm flag
if [[ "$1" == "--no-rm" ]]; then
    REMOVE_FLAG=""
    shift  # Remove this argument from the parameters
fi

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Find credentials relative to the script location
CLAUDE_JSON="${SCRIPT_DIR}/claude.json"
DOT_CLAUDE="${SCRIPT_DIR}/dot-claude" 

# Check if credentials exist
if [ ! -f "$CLAUDE_JSON" ]; then
    echo "Error: claude.json not found at $CLAUDE_JSON"
    exit 1
fi

if [ ! -d "$DOT_CLAUDE" ]; then
    echo "Error: dot-claude directory not found at $DOT_CLAUDE"
    exit 1
fi

# Determine the code directory
if [ $# -ge 1 ]; then
    # Use provided directory, convert to absolute path
    CODE_DIR="$(cd "$1" 2>/dev/null && pwd)"
    if [ -z "$CODE_DIR" ]; then
        echo "Error: Cannot resolve directory '$1' to absolute path"
        exit 1
    fi
else
    # Use current directory
    CODE_DIR="$(pwd)"
fi

echo "Launching Claude Code container with:"
echo " - Credentials from: $SCRIPT_DIR"
echo " - Working directory: $CODE_DIR"
if [ -z "$REMOVE_FLAG" ]; then
    echo " - Container will be preserved after exit"
else
    echo " - Container will be removed after exit"
fi

# Run the container with appropriate mounts
docker run -it $REMOVE_FLAG \
    -v "$CLAUDE_JSON:/root/.claude.json" \
    -v "$DOT_CLAUDE:/root/.claude" \
    -v "$CODE_DIR:/app" \
    claude-code bash
