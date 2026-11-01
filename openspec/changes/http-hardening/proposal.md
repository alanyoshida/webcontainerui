# Proposal

## Why

Achados B2, B3, B5 e I3 do pentest de 2026-11-01: o portal responde sem
nenhum cabeçalho de segurança (sem CSP, `X-Content-Type-Options`,
`Referrer-Policy` — qualquer XSS futuro rodaria sem restrição e a interface é
embutível por terceiros), a documentação interativa da API (`/docs`,
`/openapi.json`) fica exposta sem autenticação entregando o mapa completo da
superfície, o frontend carrega `icon_url` sem validar a origem (regressão
futura carregaria imagem externa sem barreira), e a borda anuncia
`Server: uvicorn`.

## What Changes

- Middleware de cabeçalhos de segurança nas respostas **do portal** (SPA, API,
  uploads): `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`,
  `X-Frame-Options: SAMEORIGIN` e uma CSP restritiva (`default-src 'self'`,
  com `style-src 'unsafe-inline'` — requisito do MUI/Emotion — e `connect-src`
  cobrindo WebSocket same-origin). Respostas do proxy de sessão (`/i/...`)
  ficam fora: o conteúdo embutido é do container, e cabeçalhos do portal
  aplicados lá poderiam quebrar as UIs de desktop/terminal.
- Documentação interativa desligada por padrão: `WCUI_DOCS_ENABLED` (default
  falso) controla `/docs`, `/redoc` e `/openapi.json`; dev liga quando quiser.
- Frontend valida que `icon_url` começa com `/uploads/` antes de renderizar
  a capa (catálogo do usuário e painel admin); caso contrário, usa o
  placeholder de capa ausente.
- Caddy de produção remove o cabeçalho `Server` (`header -Server`).

## Capabilities

### New Capabilities

- `http-hardening`: cabeçalhos de segurança e exposição mínima da superfície
  HTTP do portal (headers, documentação interativa, identificação de server).

### Modified Capabilities

- `image-catalog`: novo requisito — a capa exibida carrega somente de origem
  própria (`/uploads/`), nunca de URL externa.

## Impact

- `backend/app/main.py` (middleware + flags de docs no `FastAPI(...)`),
  `backend/app/config.py` (`docs_enabled`).
- Frontend: `CatalogSection.jsx`, `ImagesPanel.jsx` (validação de prefixo).
- `deploy/Caddyfile` (`header -Server`), `deploy/README.md` (variável nova).
- Testes: middleware adiciona headers e não os aplica em `/i/`; docs 404 com
  flag off e 200 com on; front renderiza placeholder para URL externa.
