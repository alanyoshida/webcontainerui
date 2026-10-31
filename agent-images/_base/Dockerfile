# Base comum das imagens de agente: ttyd (terminal web) mais os runtimes
# que as CLIs dos agentes costumam usar (Node e Python).
FROM node:20-bookworm-slim

ARG TARGETARCH=amd64
ARG TTYD_VERSION=1.7.7

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        python3 \
        python3-pip \
        python3-venv \
    && rm -rf /var/lib/apt/lists/*

# O pacote ttyd não está disponível nos repositórios do Debian bookworm
# usado pela imagem oficial do Node; usa o binário estático do release.
RUN case "$TARGETARCH" in \
        amd64) ttyd_arch=x86_64 ;; \
        arm64) ttyd_arch=aarch64 ;; \
        *) echo "arquitetura sem binário do ttyd: $TARGETARCH" >&2; exit 1 ;; \
    esac \
    && curl -fsSL -o /usr/local/bin/ttyd \
        "https://github.com/tsl0922/ttyd/releases/download/${TTYD_VERSION}/ttyd.${ttyd_arch}" \
    && chmod +x /usr/local/bin/ttyd

COPY entrypoint.sh /usr/local/bin/agent-entrypoint
RUN chmod +x /usr/local/bin/agent-entrypoint

# O volume nomeado por usuário+imagem é montado em /config. Fixar HOME ali
# faz as CLIs gravarem credenciais, sessões e configuração no volume, em vez
# da camada gravável do container (que se perde ao recriá-lo).
RUN mkdir -p /config
ENV HOME=/config

# O portal sobrescreve PORT com a porta da entrada do catálogo.
ENV PORT=3000
EXPOSE 3000

ENTRYPOINT ["/usr/local/bin/agent-entrypoint"]
