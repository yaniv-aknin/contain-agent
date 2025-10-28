# contain-agent

A containerized environment for running AI coding agents with traffic capture capabilities.

## What it does

- Runs AI coding agents (Claude, Gemini, Codex) in isolated Docker containers
- Mounts a workspace directory and agent configuration files
- Optionally captures all network traffic via mitmproxy for analysis

## Basic usage

```bash
# Run a command in the container
contain-agent [MOUNT_DIR] [COMMAND...]

# Examples
contain-agent foo cat bar.txt              # Run cat on foo/bar.txt
contain-agent . ls -la                     # Run ls in current dir
```

## Automated agent wrappers (a\* scripts)

The container has pre-installed wrappers that bypass approval prompts for automated execution. Run them as `aclaude <prompt>`, `acodex <prompt>` or `agemini <prompt>`.

## Traffic capture

```bash
# Capture all traffic to a file
contain-agent --dump FILENAME [MOUNT_DIR] [COMMAND...]

# Example
contain-agent --dump traffic.dump . aclaude 'print hello world'

# Read captured traffic
uvx --from mitmproxy mitmdump -r traffic.dump
```

When `--dump` is used:

- mitmproxy starts automatically and captures all HTTP/HTTPS traffic
- Container is configured with proxy settings and SSL certificates
- Traffic is saved to the specified file when agent completes

## Running multiple agents in parallel

Use tmux to run multiple agents simultaneously, each capturing its own traffic:

```bash
# Create session and split into panes
tmux new-session -d -s multi
tmux split-window -h -t multi
tmux split-window -v -t multi

# Run different agents in each pane
tmux send-keys -t multi:0.0 'contain-agent --dump claude.dump . aclaude "task"' C-m
tmux send-keys -t multi:0.1 'contain-agent --dump gemini.dump . agemini "task"' C-m
tmux send-keys -t multi:0.2 'contain-agent --dump codex.dump . acodex "task"' C-m

# Wait for completion, then capture output
sleep 10
tmux capture-pane -t multi:0.0 -p
tmux capture-pane -t multi:0.1 -p
tmux capture-pane -t multi:0.2 -p

# Cleanup
tmux kill-session -t multi
```

`tmux` is needed because the entire setup is oriented around interactive use, even with the a\* scripts. You should probably write a little ad-hoc `python3`/`subprocess` script that orchestrates the tmux commands with pre-planned polling, `capture-pane`, and `send-keys`.

In particular, refrain from needlessly long sleeps in your script. `sleep 1` to avoid a bit of polling complexity is fine, but hardcoding `sleep 60` in the hope the command will exit sometime under 60 seconds makes me sad while I wait for results. It's fine to run the entire script with an appropriately long/defensive timeout, based on time complexity.

## Key options

- `--dump FILE` - Enable traffic capture to FILE
- `--profile NAME` - Use named profile (default: 'default')
- `--no-profile` - Skip profile mounting
- `--no-mount` - Don't mount workspace directory
- `--image NAME` - Use custom Docker image (default: 'contain-agent')

## How it works

1. Mounts specified directory to `/workspace` in container
2. Mounts profile configs (`.claude`, `.gemini`, `.codex`, `.env`) to `/home/agent/`
3. If `--dump` specified, starts mitmproxy and configures container proxy settings
4. Runs command via `bash -l -i -c`
5. Captures traffic and cleans up container on exit
