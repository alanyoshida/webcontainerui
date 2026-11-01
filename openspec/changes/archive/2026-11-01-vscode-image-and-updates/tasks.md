# Tasks

## 1. Versão da imagem no runtime e no catálogo (D1, D4)

- [x] 1.1 Adicionar `inspect_image(repository, tag)` ao protocolo do runtime retornando labels/digest; implementar em `docker_runtime.py` (aiodocker `images.get(...).show()`) e em `fake.py`. Verificar: teste unitário do fake e do parse do label `build_version`.
- [x] 1.2 Migração idempotente em `db.py`: coluna `image_version TEXT` em `images` e `instances` (padrão `PRAGMA table_info`). Verificar: teste de migração em banco novo e em banco com dados antigos.
- [x] 1.3 `run_pull` captura a versão ao concluir (`inspect_image` → label, senão digest curto) e grava em `images.image_version`. Verificar: teste de `run_pull` atualizando `image_version`.
- [x] 1.4 `reopen_for_update` em `images.py` (`WHERE pull_state='ready' AND provision_kind='pull'`) + endpoint admin `POST /images/{id}/update-image` que agenda `run_pull`. Verificar: teste de API — ready aceita, pulling/failed/build recusam, não-admin 403.
- [x] 1.5 Expor `image_version` em `ImageResponse` e na resposta de instâncias ( campo novo). Verificar: teste de contrato da API.

## 2. Atualização de instância (D3)

- [x] 2.1 `update_instance` em `services/instances.py`: recusa imagem não pronta; para (se rodando), `remove_container`, limpa `container_id`, chama `_resume_existing`. Verificar: teste com fake runtime — volume intacto, container recriado do tag atual, run de métricas fechado/aberto.
- [x] 2.2 Endpoint `POST /instances/{id}/update` (dono; não-dono 404 anônimo, como no resto da API). Verificar: teste de API de permissão e happy path.
- [x] 2.3 Registrar `image_version` da imagem na criação/recriação (`_provision_and_start` snapshot do valor atual do catálogo). Verificar: teste — recriação atualiza o snapshot da instância.

## 3. Frontend do catálogo e da instância

- [x] 3.1 Painel admin: botão "Atualizar imagem" quando `ready` (entrada pull), com estado `pulling`/progresso reusado do fluxo existente. Verificar: `npm test` com teste do componente admin.
- [x] 3.2 Card do catálogo: mostrar `image_version` quando presente. Verificar: teste do componente de catálogo.
- [x] 3.3 Visão de sessão/listagem: botão "Atualizar" para o dono com `ConfirmDialog` (aviso de perda de trabalho em andamento) e badge "desatualizada" (versão da instância < versão do catálogo; sem badge quando versão da instância é `NULL`). Verificar: `npm test` — badge nos três casos, confirmação dispara chamada.
- [x] 3.4 Cobertura visual do VS Code: logo em `agent-images/covers/logos/` e capa 1200x400 gerada por `generate.py` resolvendo pelo nome de exibição. Verificar: PNG gerado e `seed_image_covers` associa à entrada registrada.

## 4. Verificação integrada

- [x] 4.1 Suíte backend: `cd backend && .venv/bin/python -m pytest` verde. Verificar: comando completo sem falhas.
- [x] 4.2 Suíte frontend: `cd frontend && npm test` e `npm run build` verdes. Verificar: comandos completos sem falhas.
- [x] 4.3 Verificação manual no dev stack: registrar a imagem, abrir sessão do VS Code (iframe renderiza como no spike), atualizar imagem no admin (entra em pulling), e atualizar uma instância parada confirmado o diálogo — arquivos preservados. Verificar: roteiro executado em `docker compose -f deploy/docker-compose.dev.yml up --build`.
