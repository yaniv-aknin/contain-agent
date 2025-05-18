FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt update && apt install -y \
  curl git build-essential pkg-config unzip \
  ca-certificates gnupg lsb-release \
  && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | bash

ENV PATH="/root/.cargo/bin:$PATH"

RUN /root/.local/bin/uv python install

RUN curl -fsSL https://fnm.vercel.app/install | bash

RUN /root/.local/share/fnm/fnm install v22.15.0 && /root/.local/share/fnm/fnm default v22.15.0

RUN /root/.local/share/fnm/fnm exec --using=v22.15.0 npm install -g @anthropic-ai/claude-code

WORKDIR /app
CMD [ "bash" ]
