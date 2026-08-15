# contain-agent

A containerized environment for running AI coding agents.

## What it does

- Runs AI coding agents (such as Claude or Antigravity) in isolated Docker containers
- Mounts a workspace directory and agent configuration files

## Basic usage

```bash
# Run a command in the container
contain-agent [MOUNT_DIR] [COMMAND...]

# Examples
contain-agent foo cat bar.txt              # Run cat on foo/bar.txt
contain-agent . ls -la                     # Run ls in current dir
```

## Automated agent wrappers (y\* scripts)

The container has pre-installed wrappers that run agents in "dangerous" mode.

## Testing agent behaviour

Use tmux to run and control agents.

```bash
# Create session and split into panes
tmux new-session -d -s multi
tmux split-window -h -t multi
tmux split-window -v -t multi

# Run different agents in each pane
tmux send-keys -t multi:0.0 'contain-agent . yclaude "task"' C-m
tmux send-keys -t multi:0.1 'contain-agent . yagy "task"' C-m

# Wait for completion, then capture output
sleep 10
tmux capture-pane -t multi:0.0 -p
tmux capture-pane -t multi:0.1 -p

# Cleanup
tmux kill-session -t multi
```

`tmux` is needed because the entire setup is oriented around interactive use, even with the `y\*`
scripts. If running tests, you should probably make a small ad-hoc `python3`/`subprocess` script
to orchestrate the tmux commands with pre-planned polling, `capture-pane`, and `send-keys`.

In particular, refrain from needlessly long sleeps in your script. `sleep 1` to avoid a bit of
polling complexity is fine, but hardcoding `sleep 60` in the hope the command will exit sometime
under 60 seconds makes me sad while I wait for results. It's fine to run the entire script with an
appropriately long/defensive timeout, based on time complexity.

## How it works

1. The specified directory is mounted to `/workspace/$(basename $DIRECTORY)` in container
2. Mounts homedir configs (`.claude`, `.gemini`, `.codex`) to `/home/agent/`
   - Optionally uses configs under `~/contain-agent/dotfiles` if `--no-share-config` is passed
3. Loads `~/.contain-agent/.env` into the environment
4. Runs command via `bash -l -i -c`
