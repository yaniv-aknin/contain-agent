# Contain Agent

A lightweight tool to run AI coding agents (like Claude Code or OpenAI Codex) inside isolated Docker containers.

## Setup

1. Build the container image:

   ```bash
   docker build -t contain-agent .
   ```

2. Set up authentication:

   Run your agent (e.g., Claude Code) outside the container first to create authentication files in your home directory (like `~/.claude/`).

3. Create a profile directory:

   ```bash
   mkdir -p ~/.contain-agent/default
   ```

4. Copy authentication files to your profile:

   ```bash
   cp -r ~/.claude ~/.contain-agent/default/
   ```

If you drop a `.env` in your profile it will be loaded in the container.

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

## mitmproxy Integration

For inspecting API traffic between the agent and AI services:

```bash
# Start mitmproxy automatically and dump traffic to file
contain-agent --dump traffic.mitm

# Configure for manually started proxy on port 8080
contain-agent --proxy

# Configure for transparent proxying on port 8080
```

Depending on the agent communication protocol, you may want to stream and store bodies with `mitmproxy --set stream_large_bodies=1 --set store_streamed_bodies=true`.
