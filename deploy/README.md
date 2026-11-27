# Implantação

Esta pasta guarda as composições Docker e a configuração do Caddy:

| Arquivo | Uso |
|---|---|
| `docker-compose.yml` | Produção: Caddy (TLS e plano de dados das sessões), portal e PostgreSQL |
| `docker-compose.dev.yml` | Desenvolvimento: só o portal, em `http://127.0.0.1:8000`, com SQLite |
| `Caddyfile` | Borda de produção: TLS, `forward_auth` das sessões e cabeçalhos |
| `.env.example` | Modelo das variáveis de ambiente (`.env` é ignorado pelo git) |
| `SECURITY.md` | Aviso sobre a superfície de confiança do portal |

**Antes de expor o portal além da sua própria máquina, leia
[`SECURITY.md`](SECURITY.md).**

## Subir

Produção, pelo caminho rápido (pré-requisitos, coleta de configuração, geração
de segredos e subida):

```bash
./install.sh   # na raiz do repositório
```

Desenvolvimento:

```bash
cd deploy
docker compose -f docker-compose.dev.yml up --build
```

## Documentação completa

O guia de operação vive no site do projeto, e não aqui, para existir num só
lugar:

| Assunto | Português | English |
|---|---|---|
| Subida manual, passo a passo | [Subida manual](https://alanyoshida.github.io/webcontainerui/pt-br/operations/manual-deployment/) | [Manual deployment](https://alanyoshida.github.io/webcontainerui/operations/manual-deployment/) |
| Variáveis de ambiente | [Variáveis](https://alanyoshida.github.io/webcontainerui/pt-br/operations/environment-variables/) | [Variables](https://alanyoshida.github.io/webcontainerui/operations/environment-variables/) |
| Backup e restauração do banco | [Backup](https://alanyoshida.github.io/webcontainerui/pt-br/operations/backup-and-restore/) | [Backup](https://alanyoshida.github.io/webcontainerui/operations/backup-and-restore/) |
| Reversão | [Reversão](https://alanyoshida.github.io/webcontainerui/pt-br/operations/rollback/) | [Rollback](https://alanyoshida.github.io/webcontainerui/operations/rollback/) |
| Checklist pós-deploy | [Checklist](https://alanyoshida.github.io/webcontainerui/pt-br/operations/post-deploy-checklist/) | [Checklist](https://alanyoshida.github.io/webcontainerui/operations/post-deploy-checklist/) |

Sem acesso à internet, os mesmos textos estão em Markdown no repositório:
`site/src/content/docs/pt-br/operations/` (origem, em português) e
`site/src/content/docs/operations/` (tradução para o inglês).
