# Tasks

## 1. Assets e geração das capas

- [x] 1.1 Pesquisar e versionar os logos oficiais dos 5 agentes e dos ambientes
  XFCE, KDE/Plasma, MATE, GNOME, Cinnamon, LXDE, LXQt, i3 e Sway, além do símbolo
  genérico, em `agent-images/covers/logos/`; verificar que cada arquivo existe e
  que `agent-images/covers/README.md` registra a fonte e a licença de cada logo.
- [x] 1.2 Criar o script `agent-images/covers/generate.py` que compõe cada PNG
  1200x400 com fundo em gradiente da cor predominante da marca e o logo
  centralizado, sem texto, com contraste ajustado por marca; verificar que o
  script roda do zero e gera um PNG para cada chave do mapa e para a capa
  genérica.
- [x] 1.3 Gerar e versionar os PNGs finais em `agent-images/covers/`; verificar
  com inspeção de imagem que todos têm exatamente 1200x400 e que cada chave
  usada pelo resolvedor possui seu arquivo.

## 2. Banco e persistência da capa

- [x] 2.1 Adicionar a coluna `icon_source` à tabela `images` em
  `backend/app/db.py`, com migração idempotente no padrão de
  `_migrate_add_icon_path`; verificar com teste que `init_db` cria a coluna e
  que rodar de novo não falha nem duplica.
- [x] 2.2 Preencher `icon_source = 'admin'` para entradas que já tinham
  `icon_path` antes da migração e deixar nulo para entradas sem capa; verificar
  com teste que uma entrada antiga com capa fica marcada como `admin` e uma sem
  capa fica nula.
- [x] 2.3 Ajustar `set_image_icon` (`backend/app/services/images.py`) para gravar
  `icon_source = 'admin'` junto do novo `icon_path` e continuar removendo o
  arquivo anterior; verificar com teste que o upload do administrador substitui
  a capa existente e marca a origem como `admin`.
- [x] 2.4 Implementar a gravação da capa padrão com nome determinístico
  `<image_id>-default-<sha256>.<ext>`, atualizando `icon_path` e
  `icon_source = 'default'` e apagando o arquivo padrão anterior quando o hash
  mudar; verificar com teste unitário a gravação inicial, o no-op com conteúdo
  igual e a substituição quando o conteúdo muda.

## 3. Resolução de logo e seed de capas

- [x] 3.1 Implementar o mapa local de logos e a resolução por `display_name`,
  `repository` e `tag`, com precedência do ambiente de desktop sobre a distro e
  fallback para a capa genérica; verificar com testes os casos "Webtop XFCE",
  "ubuntu kde", "alpine MATE", "Claude Code", "Hermes", "Agy", "OpenCode",
  "oh-my-pi" e um nome desconhecido.
- [x] 3.2 Implementar `seed_image_covers(settings, base_dir=None)` em
  `backend/app/services/image_covers.py` percorrendo todas as entradas do
  catálogo, incluindo desabilitadas e em falha, sem depender do build; verificar
  com testes que todas recebem capa quando não têm capa do admin, que entradas
  sem logo conhecido recebem a genérica e que entradas com capa do admin são
  preservadas.
- [x] 3.3 Verificar a idempotência e a atualização automática do seed: com o
  mesmo asset, um segundo startup não altera arquivos; com o asset alterado,
  entradas com origem `default` passam a usar a nova capa, o arquivo anterior é
  removido e entradas com origem `admin` permanecem intactas.
- [x] 3.4 Isolar falhas por entrada no seed de capas e garantir que uma falha
  não impede o startup nem as demais entradas; verificar com teste usando um
  asset ausente ou inválido em uma entrada e confirmando que as outras recebem
  capa e que o seed conclui sem propagar exceção.
- [x] 3.5 Verificar que uma imagem registrada depois do startup não recebe capa
  na criação e recebe no próximo startup, se continuar sem capa do admin; cobrir
  também uma entrada desabilitada e uma em estado de falha.

## 4. Integração com o startup

- [x] 4.1 Chamar `seed_image_covers` no `lifespan` de `backend/app/main.py` após
  `seed_agent_images`; verificar com teste de integração via `TestClient` que as
  entradas existentes no catálogo recebem capa após o startup.
- [x] 4.2 Verificar que o seed de capas não altera `build_hash` nem dispara
  rebuild de imagem: alterar um PNG em `agent-images/covers/` e confirmar que o
  próximo startup atualiza a capa sem chamar `build_image`.
- [x] 4.3 Verificar que uma falha de build de uma imagem de agente não impede a
  capa padrão daquela entrada nem o startup, usando o runtime fake com falha
  isolada.
- [x] 4.4 Verificar que uma falha no próprio seed de capas não impede o startup,
  usando um asset inválido e confirmando que o `TestClient` conclui o startup e
  as demais entradas recebem capa.

## 5. Documentação e verificação final

- [x] 5.1 Documentar em `agent-images/covers/README.md` como adicionar um novo
  logo, como regenerar as capas e como o seed decide entre capa padrão e capa do
  admin; verificar que os comandos documentados rodam como escritos.
- [x] 5.2 Atualizar o `README.md` do projeto com uma nota curta sobre capas
  padrão no startup e a precedência do upload do administrador; verificar que a
  nota corresponde ao comportamento implementado.
- [x] 5.3 Rodar a suíte completa do backend (`pytest` em `backend/`) e confirmar
  que todos os testes passam, incluindo os novos testes de capa.
- [x] 5.4 Rodar a suíte do frontend (`npm test` em `frontend/`) e confirmar que
  nada regrediu, mesmo sem mudança de código no frontend.
- [x] 5.5 Subir o stack de desenvolvimento e verificar no catálogo do admin que
  todas as entradas existentes exibem capa padrão, e que um upload do admin
  continua prevalecendo após reiniciar o portal.

## Workflow follow-up

- Arquivar a change após a revisão, sincronizando os deltas nas specs
  `image-catalog` e `coding-agent-images`.
- Verificar o resultado arquivado.
