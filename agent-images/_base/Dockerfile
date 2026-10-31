# Base comum das imagens de agente: ttyd (terminal web) mais os runtimes
# que as CLIs dos agentes costumam usar (Node e Python).
FROM node:20-bookworm-slim

ARG TARGETARCH=amd64
ARG TTYD_VERSION=1.7.7
ARG GH_CLI_VERSION=2.103.3
ARG GLAB_CLI_VERSION=1.126.0

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        openssh-client \
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

# GitHub CLI e GitLab CLI: binário estático pinado por versão, direto do
# release oficial (mesmo padrão do ttyd acima) — sem repositório apt extra
# nem `curl | sh`. O login de cada um é manual pelo usuário no terminal
# (`gh auth login` / `glab auth login`); nenhum dos dois usa a identidade
# SSH do portal.
RUN curl -fsSL -o /tmp/gh.tar.gz \
        "https://github.com/cli/cli/releases/download/v${GH_CLI_VERSION}/gh_${GH_CLI_VERSION}_linux_${TARGETARCH}.tar.gz" \
    && tar -xzf /tmp/gh.tar.gz -C /tmp \
    && mv "/tmp/gh_${GH_CLI_VERSION}_linux_${TARGETARCH}/bin/gh" /usr/local/bin/gh \
    && rm -rf /tmp/gh.tar.gz "/tmp/gh_${GH_CLI_VERSION}_linux_${TARGETARCH}" \
    && curl -fsSL -o /tmp/glab.tar.gz \
        "https://gitlab.com/gitlab-org/cli/-/releases/v${GLAB_CLI_VERSION}/downloads/glab_${GLAB_CLI_VERSION}_linux_${TARGETARCH}.tar.gz" \
    && tar -xzf /tmp/glab.tar.gz -C /tmp bin/glab \
    && mv /tmp/bin/glab /usr/local/bin/glab \
    && rm -rf /tmp/glab.tar.gz /tmp/bin

COPY entrypoint.sh /usr/local/bin/agent-entrypoint
RUN chmod +x /usr/local/bin/agent-entrypoint

# O volume nomeado por usuário+imagem é montado em /config. Fixar HOME ali
# faz as CLIs gravarem credenciais, sessões e configuração no volume, em vez
# da camada gravável do container (que se perde ao recriá-lo). `ENV HOME`
# sozinho não basta: o cliente `ssh` resolve o diretório do usuário via
# /etc/passwd (getpwuid), não pela variável de ambiente — sem corrigir o
# passwd, `ssh`/`git` continuam procurando em /root mesmo com HOME=/config
# (descoberto testando a injeção de identidade SSH; as imagens webtop do
# LinuxServer não têm esse problema porque o usuário delas já nasce com
# /config como home no próprio passwd).
RUN mkdir -p /config \
    && sed -i 's#^root:x:0:0:root:/root:#root:x:0:0:root:/config:#' /etc/passwd
ENV HOME=/config

# Sem WORKDIR o processo do container nasce em `/` (padrão do Docker), não
# em HOME — e é em `/config` que o AGENTS.md é injetado (ver
# `agents_md.py`). Fixar o cwd aqui garante que a CLI do agente (CMD de
# cada imagem derivada) já inicie em `/config` e enxergue o arquivo.
WORKDIR $HOME

# O portal sobrescreve PORT com a porta da entrada do catálogo.
ENV PORT=3000
EXPOSE 3000

ENTRYPOINT ["/usr/local/bin/agent-entrypoint"]
