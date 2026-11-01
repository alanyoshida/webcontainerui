# Design

## Context

O portal hoje não adiciona nenhum cabeçalho de segurança (verificado no
pentest: resposta de `/` traz apenas `server`, `content-type`, `etag`).
`create_app` (main.py) monta API, uploads e SPA catch-all; o proxy de sessão
(`/i/...`, session_proxy.py) faz streaming do conteúdo do container. A
interface embute a sessão em iframe same-origin (`InstanceSession.jsx`) e
acessa o DOM dele (`contentWindow.term`, `contentDocument`) — o que restringe
as opções de `X-Frame-Options` e CSP. O front usa MUI/Emotion (injeta
`<style>` inline), fontes self-hosted (`@fontsource`), WebSocket same-origin
para o terminal — sem CDNs (confirmado na revisão do pentest).

## Goals / Non-Goals

**Goals:**

- Cabeçalhos de segurança em toda resposta própria do portal, sem quebrar a
  interface nem o iframe da sessão.
- Superfície HTTP mínima: docs off por padrão, `Server` fora da borda.
- Front robusto contra `icon_url` que um dia aponte para fora.

**Non-Goals:**

- Endurecer o conteúdo dos containers (é conteúdo do usuário; virará pauta da
  change `session-origin-isolation`).
- HSTS por app (já feito no Caddy pela change `harden-login`).
- Nonce-based CSP / remoção do `unsafe-inline` de estilo (ver D2).

## Decisions

### D1 — Middleware de headers com exclusão explícita do `/i/`

Middleware ASGI puro em `main.py` (padrão do Starlette, sem dependência):
adiciona os quatro cabeçalhos quando o path **não** começa com `/i/`. Dois
motivos para a exclusão: (a) o conteúdo é do container — impor CSP/XFO do
portal lá poderia quebrar as UIs de ttyd/Selkies; (b) o proxy repassa
`response_headers` do upstream e o middleware do portal não deve filtrar
resposta de terceiros. Exclusão por path, não por rota: mais simples e o
prefixo é o próprio contrato do proxy.

Alternativa rejeitada: adicionar os headers no Caddy — não cobre o dev stack
(sem Caddy) nem o acesso direto pela rede interna (M2 do pentest mostrou que
o portal é alcançável direto), e ainda aplicaria ao `/i/`.

### D2 — CSP restritiva onde dá, explícita onde MUI exige

```
default-src 'self';
script-src 'self';
style-src 'self' 'unsafe-inline';   # MUI/Emotion injeta <style> inline
img-src 'self' data:;
font-src 'self';
connect-src 'self' ws: wss:;        # terminal WebSocket same-origin
frame-src 'self';                   # iframe da sessão em /i/
frame-ancestors 'self';             # clica-jacking: só o próprio portal embute
object-src 'none'; base-uri 'self'
```

`X-Frame-Options: SAMEORIGIN` (não `DENY`): o portal embute a si mesmo o
iframe same-origin da sessão — `DENY` quebraria a visão de sessão;
`frame-ancestors 'self'` na CSP reforça o mesmo recado para navegadores
modernos. `style-src 'unsafe-inline'` é trade-off registrado: Emotion não
suporta nonce sem mudança de provider; a exposição incremental é pequena
(script-src segue restrito) e a revisão da CSP acontecerá de novo na change
de origem isolada (M3).

### D3 — Docs por flag, padrão desligado

`docs_enabled: bool = False` em Settings (`WCUI_DOCS_ENABLED`). `create_app`
passa `docs_url/redoc_url/openapi_url` só quando ligado. Padrão seguro
(fechado); desenvolvimento liga com uma variável. Alternativa rejeitada:
"docs atrás de `require_admin`" — acoplaria o OpenAPI ao ciclo de sessão e
exigiria login para o Swagger funcionar (OAuth2/cookie flow manual), por um
benefício menor que o da flag.

### D4 — `Server` removido na borda (Caddy)

O uvicorn não permite desligar o cabeçalho `Server`; a remoção é no Caddy
(`header -Server`), que é a única borda exposta em produção. Acesso direto
interno continuará vendo `uvicorn` — informação mínima (sem versão), risco
aceito e anotado no pentest (I3).

### D5 — `icon_url`: validação de prefixo na renderização

Helper único no frontend (`isLocalUploadUrl`): `icon_url?.startsWith('/uploads/')`.
`CatalogSection` e `ImagesPanel` passam a derivar o `src` por esse helper com
fallback para o avatar/capa padrão atuais de capa ausente. Validar no ponto
de renderização (não só no fetch da API) fecha também dados manipulados no
banco — camada extra barata apontada no B5.

## Risks / Trade-offs

- [CSP quebra algo não previsto (fonte externa escondida, WebSocket em outro
  host)] → mitigação: a revisão do pentest não achou nenhuma origem externa;
  o teste de build + e2e manual (abrir sessão, ver capas) é tarefa; se algo
  aparecer, a diretiva específica relaxa num commit de uma linha.
- [`X-Frame-Options` em respostas da API] → inócuo (JSON não é embutível de
  forma útil) e mantém o middleware simples.
- [Docs off por padrão surpreende desenvolvedor] → variável única e
  documentada no README de deploy; o CLI continua com `openapi.json` via
  flag quando ligado.
- [Mudança de arquitetura futura (M3) altera frame-src/connect-src] →
  esperado; a CSP fica centralizada numa constante do middleware, ajuste
  pontual.

## Migration Plan

Deploy único; docs saem do ar e headers passam a valer. Se a CSP regredir
algo em produção, o rollback pontual é remover a diretoria específica (ou a
CSP inteira) num commit — middleware isolado, sem dado envolvido.
