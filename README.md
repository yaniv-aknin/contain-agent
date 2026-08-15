# Contain Agent

A lightweight tool to run AI coding agents inside isolated Docker containers.

## Setup

1. Build the container image:

   ```bash
   docker build -t contain-agent .
   ```

2. Set up authentication:

   Run your agent (e.g., Claude Code) outside the container first to create authentication files in your home directory (like `~/.claude/`).

3. Optionally, create an isolated dotfile directory and copy files there:

   ```bash
   mkdir -p ~/.contain-agent/dotfiles
   cp -r ~/.claude ~/.contain-agent/dotfiles/
   ```

If you drop a `.env` in `~/.contain-agent` it will be loaded in the container.

## Usage

Launch a containerized shell with your current directory mounted:

```bash
contain-agent
```

Or specify a directory to mount:

```bash
contain-agent /path/to/project
```

See `--help` for more options. See also [usage instructions](USAGE.md) geared at agents, i.e., helping agents invoke `contain-agent` to research agents.
