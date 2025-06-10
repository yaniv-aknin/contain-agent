FROM ubuntu:24.04

ARG NODE_VERSION=v22.16.0

ENV DEBIAN_FRONTEND=noninteractive

RUN apt update && apt install -y \
  curl git build-essential pkg-config unzip \
  ca-certificates gnupg lsb-release && \
  rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | UV_INSTALL_DIR=/usr/local/bin bash
RUN uv python install

RUN curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - && \
  apt-get install -y nodejs

RUN npm install -g @anthropic-ai/claude-code
RUN npm install -g @openai/codex

WORKDIR /app
CMD [ "bash" ]
