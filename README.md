# Contain Agent

A simple tool to launch a container to isolate coding agents like Claude Code or Codex.

## Invocation

This tool simply runs a Docker container with the current directory mounted as `/app`, also mounting any files in the profile into the container's home directory (so, for example, dotfiles for the agentic tool you'll use)

## Build container

`docker build -t contain-agent .`

## (lack of) UID/GID mapping

The current directory will be mounted without UID/GID mapping; created files will be assigned a platform-dependant owner/group.

* On macOS, typically, this would mean "the host UID/GID, no matter the UID/GID inside the container". This is probably a reasonable behaviour for your usecase.
* On Linux, typically, this would mean "the container UID/GID". This is probably the more correct behaviour, but also less useful for most scenarios where you'd want contain agent. Send PRs if you want this solved.
