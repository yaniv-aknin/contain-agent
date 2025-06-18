# Contain Agent

A simple tool to launch a container to isolate coding agents like Claude Code or Codex.

## Setup

1. Build the container:

   ```bash
   docker build -t contain-agent .
   ```

2. Create an alias to `launcher.py` for easy access:

   ```bash
   alias agent='/path/to/launcher.py'
   ```

3. Set up authentication by running an agent outside the container first to create authentication files in your home directory (like `.claude`)

4. Copy those authentication files to a _profile directory_ (like `~/.contain-agent/default/`).

## Usage

Run the launcher to drop into a containerized shell where your current directory is mounted at `/app`:

```bash
python launcher.py [directory]
```

The tool mounts your specified directory (or current directory if none specified) into the container at `/app`, and maps profile files from `~/.contain-agent/default/` into the container's home directory. The idea is that the agent is contained, but the profile files are shared and reused across sessions.

### Options

- `--profile <name>`: Use a different profile (default: `default`)
- `--user`: Run as unprivileged user instead of root
- `--no-rm`: Keep container after exit
- `--force`: Override protection for sensitive directories
- `--no-network`: Disable network access (if your agent doesn't need it)

Additional profiles can be created in `~/.contain-agent/` or in a local `profiles/` directory.

## UID/GID Mapping

Files created will be assigned platform-dependent ownership:

- **macOS**: Host UID/GID (convenient for most use cases)
- **Linux**: Container UID/GID (more correct but less convenient)
