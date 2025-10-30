FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    NODE_ENV=production
RUN apt-get update && apt-get install -y \
    sudo \
    iptables \
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
    net-tools \
    lsof \
    iproute2 \
    strace \
    tcpdump \
    dnsutils \
    traceroute \
    miller \
    sed \
    gawk \
    diffutils \
    gzip \
    bzip2 \
    xz-utils \
    p7zip-full \
    sysstat \
    ltrace \
    xxd \
    man-db \
    socat \
    libnss3 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libxss1 \
    libasound2t64 \
    libatspi2.0-0 \
    libgtk-3-0t64 \
    libxshmfence1 \
    libcups2 \
    libdbus-1-3 \
    libxcb1 \
    libxfixes3 \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    fonts-liberation \
    fonts-noto-color-emoji \
    xdg-utils \
    libgstreamer1.0-0 \
    libgstreamer-plugins-base1.0-0 \
    libgstreamer-plugins-bad1.0-0 \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-libav \
    libgtk-4-1 \
    libgraphene-1.0-0 \
    libxslt1.1 \
    libwoff1 \
    libevent-2.1-7 \
    libavif16 \
    libharfbuzz-icu0 \
    libenchant-2-2 \
    libsecret-1-0 \
    libhyphen0 \
    libmanette-0.2-0 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash -u 1001 agent

RUN mkdir -p /workspace && chown agent:agent /workspace

COPY scripts/xproxy /usr/local/bin/xproxy
RUN chmod 755 /usr/local/bin/xproxy && \
    chown root:root /usr/local/bin/xproxy

RUN echo 'Defaults!/usr/local/bin/xproxy env_keep += "HTTP_PROXY"' > /etc/sudoers.d/xproxy && \
    echo 'agent ALL=(root) NOPASSWD: /usr/local/bin/xproxy *' >> /etc/sudoers.d/xproxy && \
    chmod 0440 /etc/sudoers.d/xproxy

USER agent

RUN curl -LsSf https://astral.sh/uv/install.sh | bash
RUN /home/agent/.local/bin/uv python install

RUN curl -fsSL https://fnm.vercel.app/install | bash
RUN /home/agent/.local/share/fnm/fnm install 22

RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | bash -s -- -y

RUN /home/agent/.local/share/fnm/fnm exec --using=22 npm install -g @anthropic-ai/claude-code
RUN /home/agent/.local/share/fnm/fnm exec --using=22 npm install -g @openai/codex
RUN /home/agent/.local/share/fnm/fnm exec --using=22 npm install -g @google/gemini-cli
RUN curl https://cursor.com/install -fsSL | bash

RUN echo 'if [ -n "$TRANSPARENT_PROXY" ] && command -v xproxy &> /dev/null; then' >> /home/agent/.bashrc && \
    echo '    sudo xproxy start' >> /home/agent/.bashrc && \
    echo 'fi' >> /home/agent/.bashrc

COPY --chown=agent:agent scripts/bin/* /home/agent/.local/bin/
RUN chmod +x /home/agent/.local/bin/*

SHELL ["/bin/bash", "-c"]
WORKDIR /workspace
CMD ["/bin/bash"]
