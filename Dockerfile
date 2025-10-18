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
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | UV_INSTALL_DIR=/usr/local/bin bash
RUN uv python install

RUN npm install -g @anthropic-ai/claude-code
RUN npm install -g @openai/codex

RUN useradd -m -s /bin/bash -u 1001 agent

RUN mkdir -p /workspace && chown agent:agent /workspace

USER agent

SHELL ["/bin/bash", "-c"]
WORKDIR /workspace
CMD ["/bin/bash"]
