FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    NODE_ENV=production
RUN apt-get update && apt-get install -y \
    curl \
    git \
    bash \
    ca-certificates \
    gnupg \
    telnet \
    jq \
    ffmpeg \
    vim \
    build-essential \
    sqlite3 \
    wget \
    unzip \
    zip \
    tree \
    imagemagick \
    graphviz \
    ripgrep \
    findutils \
    file \
    fd-find \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash -u 1001 agent

RUN mkdir -p /workspace && chown agent:agent /workspace

USER agent

RUN curl -LsSf https://astral.sh/uv/install.sh | bash
RUN /home/agent/.local/bin/uv python install

RUN curl -fsSL https://fnm.vercel.app/install | bash
RUN /home/agent/.local/share/fnm/fnm install 22

RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | bash -s -- -y

RUN /home/agent/.local/share/fnm/fnm exec --using=22 npm install -g @anthropic-ai/claude-code
RUN /home/agent/.local/share/fnm/fnm exec --using=22 npm install -g @openai/codex
RUN /home/agent/.local/share/fnm/fnm exec --using=22 npm install -g @google/gemini-cli

SHELL ["/bin/bash", "-c"]
WORKDIR /workspace
CMD ["/bin/bash"]
