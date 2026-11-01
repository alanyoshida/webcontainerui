# Proposal

## Why

O pentest de 2026-11-01 (`docs/relatorio-pentest-2026-11-01.md`) apontou dois
achados de severidade média no caminho de login: o cookie de sessão nasce sem a
flag `Secure` em produção (M1 — o uvicorn roda sem `--proxy-headers`, então
atrás do Caddy o portal nunca vê que o cliente usa HTTPS) e o endpoint de login
não limita tentativas (M2 — 25 senhas erradas consecutivas foram processadas sem
barreira, sem atraso e sem bloqueio, inclusive alcançável direto pela rede
Docker interna). Juntos, eles permitem força bruta online sem custo aplicativo
e sequestro de sessão por um atacante capaz de forçar tráfego HTTP puro.

## What Changes

- uvicorn passa a honrar cabeçalhos de proxy encaminhados (`X-Forwarded-Proto`,
  `X-Forwarded-For`) quando configurado para isso: novas variáveis de ambiente
  `UVICORN_PROXY_HEADERS` e `UVICORN_FORWARDED_ALLOW_IPS` nas composições
  Docker, com subnet do `wcui_net` fixada via IPAM no compose de produção.
  Efeito: atrás do Caddy, `request.url.scheme` vira `https` e o cookie de
  sessão ganha `Secure` (comportamento que a spec `auth` já exige, mas que a
  configuração atual quebra); o IP real do cliente fica disponível para o
  limitador de M2.
- Caddyfile do deploy de produção passa a enviar
  `Strict-Transport-Security: max-age=31536000`, eliminando o downgrade para
  HTTP como vetor de roubo do cookie.
- Novo limitador de tentativas de login **em memória, sem dependência nova**,
  no processo do portal (um worker, por design): janela deslizante por conta
  (e-mail) e por origem (IP do cliente); ao exceder, respostas `429` com
  `Retry-After` por um período curto, sem bloqueio permanente e sem distinção
  entre conta existente e inexistente; limiar e janela configuráveis via
  `WCUI_LOGIN_MAX_FAILURES`, `WCUI_LOGIN_WINDOW_SECONDS` e
  `WCUI_LOGIN_LOCK_SECONDS`.
- Nada muda para o usuário final além das duas proteções: o login correto
  dentro do limite continua idêntico.

## Capabilities

### New Capabilities

(nenhuma)

### Modified Capabilities

- `auth`: novo requisito de limitação de tentativas de login com falha (por
  conta e por origem, recusa temporária uniforme); o requisito existente "Cookie
  de sessão protegido no transporte" ganha um cenário do portal servido atrás
  de proxy TLS confiável, fixando que a flag `Secure` deve de fato ser aplicada
  nesse arranjo.

## Impact

- `backend/app/api/auth.py`: rota de login consulta e alimenta o limitador.
- `backend/app/services/` (novo módulo de limitação) e `backend/app/config.py`
  (três campos novos de `Settings`).
- `deploy/docker-compose.yml` (IPAM da `wcui_net` + env do uvicorn) e
  `deploy/docker-compose.dev.yml` (sem proxy à frente: permanece sem confiar
  em cabeçalhos encaminhados), `deploy/Caddyfile` (HSTS).
- `deploy/README.md` / `deploy/SECURITY.md`: documentação das variáveis novas.
- Testes: unitários para o limitador (relógio injetado), de rota para o
  comportamento 429/`Retry-After`, e verificação de deploy para o cookie
  `Secure` atrás de proxy (ver design, seção de verificação — o nível uvicorn
  não é observável pelo TestClient).
