FROM ubuntu:24.04

ARG NODE_VERSION=v22.16.0

ENV DEBIAN_FRONTEND=noninteractive

RUN apt update && apt install -y \
  curl git build-essential pkg-config unzip \
  ca-certificates gnupg lsb-release \
  && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | bash

ENV PATH="/root/.cargo/bin:$PATH"

RUN /root/.local/bin/uv python install

RUN curl -fsSL https://fnm.vercel.app/install | bash

RUN /root/.local/share/fnm/fnm install ${NODE_VERSION} && /root/.local/share/fnm/fnm default ${NODE_VERSION}

RUN /root/.local/share/fnm/fnm exec --using=${NODE_VERSION} npm install -g @anthropic-ai/claude-code
RUN /root/.local/share/fnm/fnm exec --using=${NODE_VERSION} npm install -g @openai/codex

WORKDIR /app
CMD [ "bash" ]
