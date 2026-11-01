# Design

## Context

O portal provisiona imagens de duas formas: `pull` (webtop, registradas no
catálogo e baixadas em segundo plano) e `build` (agentes CLI, Dockerfiles em
`agent-images/`). O proxy de sessão encaminha `/i/<uuid>/...` sem reescrever o
caminho, então a aplicação do container precisa servir sob prefixo
(`SUBFOLDER`, `instances.py:111`) — contrato que a base Selkies da
`lscr.io/linuxserver/vscode` cumpre nativamente (confirmado em spike: auth
401/200, `?resize=scale`, sharing off, VS Code desktop renderizando sem erros).

O ciclo de atualização de imagens `pull` hoje termina no primeiro pull:
`reopen_for_retry` só reabre entrada em `failed` (`images.py:114`) e
`_resume_existing` religa o mesmo container (`instances.py:302-304`), então
nem instância nova nascida de tag atualizado, nem instância existente, têm
caminho de migração dentro do produto.

## Goals / Non-Goals

**Goals:**
- VS Code desktop no catálogo como imagem `pull` comum, sem mudanças de proxy
  ou runtime de criação.
- Ciclo de atualização completo dentro do produto: re-pull de entrada `ready`,
  migração de instância existente preservando o volume, versão visível.

**Non-Goals:**
- Suporte genérico a `cap_add` no `ContainerSpec` (spike: desnecessário nesta
  imagem).
- Tags pinadas; atualização automática de instâncias; atualização de imagens
  `build` (agentes seguem o fluxo de rebuild existente).
- Subdomínios por instância (única forma de suportar code-server web nativo —
  rejeitada por expandir DNS/TLS/arquitetura).

## Decisions

- **D1 — Captura de versão: label da imagem, com fallback para digest curto.**
  Após o pull, o runtime inspeciona a imagem e extrai o label de versão
  (`build_version` nas imagens LinuxServer, ex.: `1.143.1-ls31`); sem label,
  usa o digest curto do conteúdo. Gravado em `images.image_version` (coluna
  nova, migração idempotente padrão `PRAGMA table_info`). Alternativa
  descartada: derivar versão do tag — com `:latest` o tag nunca muda.
  Requer um método novo no protocolo do runtime (ex.: `inspect_image`), pois
  o stream de pull do Docker não devolve labels.

- **D2 — Badge de desatualização por snapshot na criação, não por inspeção ao
  vivo.** `instances.image_version` (coluna nova) registra a versão usada
  quando o container foi criado/recriado; a comparação com a versão do
  catálogo acontece na leitura. Alternativa descartada: inspecionar o label do
  container a cada listagem — colocaria chamadas Docker no caminho quente de
  polling da interface (o portal roda com um worker; inspeção por instância a
  cada ciclo não cabe). Instâncias sem versão registrada (criadas antes da
  migração) ficam sem badge — evita falso "desatualizada" em massa no deploy.

- **D3 — Atualização de instância reusa o caminho de recriação existente.**
  Nova função de serviço `update_instance`: `stop_instance` quando rodando
  (fecha o run de métricas), `remove_container`, limpa `container_id` e chama
  `_resume_existing` — que recria via `_provision_and_start` reutilizando
  volume, credenciais, injeção de identidade SSH e AGENTS.md. Recusa com
  imagem não pronta (mesma checagem de `create_instance`). Falha de recriação
  cai no estado `error` existente, com volume intacto. Alternativa descartada:
  `docker stop/start` com container recriado por fora do fluxo — duplicaria a
  lógica de provisionamento.

- **D4 — Endpoint próprio para atualização de imagem**, não reuso de
  `retry-pull`: são semânticas distintas (recuperação de falha × manutenção
  programada), com pré-condições diferentes (`failed` × `ready`). Nova função
  `reopen_for_update` (`WHERE pull_state = 'ready' AND provision_kind =
  'pull'`) e endpoint `POST /images/{id}/update-image` (admin), que agenda o
  mesmo `run_pull`. O bloqueio de instanciação durante o pull já existe
  (`create_instance` exige `pull_state = 'ready'`).

- **D5 — Entrada do VS Code registrada como imagem `pull` comum**, pela UI
  admin (`latest`, porta 3000, limites padrão: shm 1024 MB — valor exigido
  pela imagem —, mem 2048 MB, cpu 2.0). Capa gerada pelo mecanismo existente
  (`agent-images/covers/generate.py` a partir de logo em `covers/logos/`;
  `seed_image_covers` resolve pelo nome de exibição). Nada de seed de código:
  catálogo é gerido pelo admin.

- **D6 — Sem `cap_add`.** O spike executou a imagem com e sem `IPC_LOCK`:
  zero menção a keyring nos logs nas duas variantes — a sessão labwc da
  imagem nem inicia o `gnome-keyring-daemon`. `ContainerSpec` fica intocado.

## Risks / Trade-offs

- [Imagem de 6,21 GB: primeiro pull longo e re-pull de update pode baixar
  camadas grandes quando o VS Code muda] → o catálogo já expõe estado
  `pulling` com progresso; a instanciação fica bloqueada até concluir
  (comportamento existente).
- [`:latest` é tag móvel: um re-pull muda a versão para todas as novas
  instâncias, e o admin não escolhe a versão] → aceito por decisão do
  escopo; a versão registrada (D1) dá visibilidade do que entrou.
- [Atualização de instância interrompe sessão em uso] → ação é manual do
  dono, com diálogo de confirmação explícito sobre perda de trabalho em
  andamento; arquivos preservados.
- [Recriação falha no meio (container removido, imagem antiga já não está
  mais no host se o update do catálogo removeu camadas)] → estado `error`
  existente com mensagem; novo tentar recria; o volume nunca é tocado pelo
  fluxo.

## Migration Plan

Migração idempotente em `init_db` (padrão `CREATE TABLE IF NOT EXISTS` +
`ALTER TABLE` guardado por `PRAGMA table_info`): colunas `image_version` em
`images` e `instances`. Nenhuma migração de dados — versões antigas ficam
`NULL` e a regra de badge (D2) trata `NULL` como "versão desconhecida".
Rollback: código anterior lê/ignora as colunas novas; instâncias continuam
rodando.

## Open Questions

(nenhuma)
