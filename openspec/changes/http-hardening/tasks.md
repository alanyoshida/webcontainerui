# Tasks

## 1. Cabeçalhos de segurança no backend

- [x] 1.1 Implementar middleware de headers em `backend/app/main.py` (`X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options: SAMEORIGIN`, CSP da D2 como constante única), aplicando a todo path que não comece com `/i/` — verificado com testes novos: `/` e `/api/...` carregam os quatro cabeçalhos; rota de proxy `/i/{id}/...` (com `proxy_client` do conftest) não recebe nenhum deles
- [x] 1.2 Documentar no README de deploy a lista de cabeçalhos, a exclusão do `/i/` e o motivo do `style-src 'unsafe-inline'` (MUI/Emotion) — conferência por leitura cruzada com o design

## 2. Documentação interativa desligada por padrão

- [x] 2.1 Adicionar `docs_enabled: bool = False` a `Settings` (`WCUI_DOCS_ENABLED`) e ligar `docs_url/redoc_url/openapi_url` no `FastAPI(...)` só quando ativo — testes: `/docs` e `/openapi.json` 404 por padrão e 200 com a flag ligada (app criado com settings próprios)
- [x] 2.2 Registrar `WCUI_DOCS_ENABLED` na tabela de variáveis do `deploy/README.md` (padrão desligado; ligar em dev) — verificado rodando o comando documentado contra o stack dev

## 3. Frontend

- [x] 3.1 Criar helper `isLocalUploadUrl` e usá-lo em `CatalogSection.jsx` e `ImagesPanel.jsx` para decidir o `src` da capa (fallback = tratamento atual de capa ausente) — testes de componente: capa `/uploads/...` renderiza `<img>` com o src; URL externa não gera requisição e cai no fallback
- [x] 3.2 Conferir no build que a CSP não bloqueia nada do bundle (fontes self-hosted, WebSocket same-origin) rodando `npm run build` e abrindo o portal dev com o console do navegador limpo de violações — evidência registrada na change

## 4. Borda (Caddy) e verificação

- [x] 4.1 Adicionar `header -Server` ao site do `deploy/Caddyfile` e validar com `caddy validate` (binário oficial, como em harden-login)
- [x] 4.2 Rodar suíte backend (`pytest`) e front (`npm test && npm run build`) verdes; contra o stack dev, `curl -D -` em `/`, `/api/config` e `/i/<id>/` confirmando headers presentes nas duas primeiras e ausentes na terceira
