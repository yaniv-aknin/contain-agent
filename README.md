# Contain Agent

A simple tool to launch a container to isolate coding agents like Claude Code or Codex.

## Invocation

This tool simply runs a Docker container with the current directory mounted as `/app`, also mounting any files in the profile into the container's home directory (so, for example, dotfiles for the agentic tool you'll use)

## Build container

`docker build -t contain-agent .`
