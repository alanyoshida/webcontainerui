# Proposal

## Why

Achado I4 do pentest de 2026-11-01: o portal não registra nenhum evento de
segurança — falhas de login, operações administrativas, revogações e o ciclo
de vida de instâncias são invisíveis. Sem trilha, não há detecção de abuso
nem perícia após incidente (a limitação também atrapalhou a própria análise
do pentest, que dependeu de medição externa para concluir ausência de rate
limit).

## What Changes

- Emissor central de eventos de auditoria: uma linha JSON por evento, via
  logger dedicado (`wcui.audit`) para a saída padrão — capturada pelo
  `docker logs`, sem dependência nova e sem tabela no banco.
- Catálogo fixo de eventos cobrindo: autenticação (login com desfecho e
  origem, recusa pelo limitador, logout), gestão de acesso (usuário criado/
  desabilitado, grupo e grants alterados), catálogo e bibliotecas que
  propagam aos containers (imagens, documentos AGENTS.md, servidores MCP,
  skills) e ciclo de vida de instâncias (criação, parada, exclusão, erro de
  provisionamento).
- Todo evento carrega ator (id e e-mail quando aplicável), origem (IP do
  cliente), alvo e desfecho; segredos (senhas, tokens de sessão, credenciais
  internas de instância, valores de env/headers de MCP) jamais aparecem.

## Capabilities

### New Capabilities

- `security-audit-log`: trilha estruturada de eventos de segurança do portal
  (o que é registrado, com quais campos, e o que nunca é registrado).

### Modified Capabilities

(nenhuma — as capabilities existentes ganham emissão de eventos como
detalhe de implementação, sem mudança de comportamento especificado)

## Impact

- `backend/app/services/audit_log.py` (novo emissor) + configuração do
  logger no `main.py` (lifespan).
- Pontos de emissão: `api/auth.py`, `api/admin.py`, `api/access_control.py`,
  `api/images.py`, `api/agents_md.py`, `api/mcp_servers.py`,
  `api/agent_skills.py`, `api/instances.py`, `services/users.py` (via rota).
- `deploy/SECURITY.md`: seção documentando o formato e onde coletar.
- Testes: formato do evento, cobertura por categoria de rota, e ausência de
  segredos no registro.
