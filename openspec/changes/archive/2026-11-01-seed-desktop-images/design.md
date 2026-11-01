# Design

## Context

O seed de agentes (`services/agent_images.py`) é o molde: tupla de specs,
garantia por (repositório, tag), falha isolada por entrada, startup nunca
bloqueado por erro individual. Diferença essencial: agentes são
`provision_kind='build'` a partir de contextos do repositório; desktops são
`provision_kind='pull'` — o caminho já usado pelo cadastro manual
(`create_image` + `run_pull` em segundo plano, com progresso e retry-pull).
O `seed_image_covers` já roda depois dos seeds no lifespan e cobre toda
entrada existente, inclusive em provisionamento.

## Goals / Non-Goals

**Goals:**

- Deploy do zero com as duas entradas de desktop nascendo prontas para uso
  (download automático, capa padrão no mesmo boot).
- Zero surpresa para quem já tem catálogo: nada de linhas duplicadas,
  reativação ou sobrescrita de configuração do admin.

**Non-Goals:**

- Grupo padrão com grants automáticos — acesso continua sendo fluxo do admin
  (criar grupo, conceder imagem, adicionar usuário); automatizar quem vê o
  quê é decisão de produto separada.
- Administrador enxergar todo o catálogo sem grant (mesmo racional).
- Tornar as entradas de desktop editáveis/removíveis como lista — a tupla é
  código, como `AGENT_IMAGES`.
- Variável para desligar o seed (mesma decisão do seed de agentes: não há
  caso de uso legítimo para um deploy sem o catálogo padrão).

## Decisions

### D1 — Módulo próprio, tupla de duas entradas, `provision_kind='pull'`

`services/desktop_images.py` com `DESKTOP_IMAGES` — as quatro entradas de
desktop do catálogo de referência: `webtop:latest` ("Webtop XFCE"),
`webtop:ubuntu-kde` ("Ubuntu KDE"), `webtop:alpine-mate` ("Alpine MATE") e
`vscode:latest` ("VS Code") — e `seed_desktop_images(settings, runtime)`:
para cada spec, se (repositório, tag) já existe → `return` (qualquer estado —
`pulling`, `ready`, `failed`, `enabled=0` — o admin mandou, o admin fica);
senão `create_image(..., provision_kind='pull')` com limites default das
`Settings` e `spawn(run_pull(...))`. Cada entrada em try/except próprio, no
padrão do seed de agentes (falha marca `failed` nas demais regras; aqui o
`create_image`/`spawn` falho é logado e a próxima entrada segue).
Alternativas rejeitadas: estender `agent_images.py` (mistura semântica
build×pull num módulo só); reaproveitar o mecanismo de buildargs/skills
(desnecessário para pull).

### D2 — Download em segundo plano, startup sem esperar

Diferente dos agentes (que aguardam o build — D8 do design original), o pull
é `spawn`: o portal fica de pé em segundos e o download aparece no painel com
progresso, exatamente como no cadastro manual. Downloads de ~1-2GB bloqueando
o startup atrasariam o primeiro acesso sem ganho nenhum — o estado
`pulling` já é observável e `create_instance` recusa imagem não pronta.

### D3 — Ordem no lifespan: agentes → desktops → capas

Inserir `seed_desktop_images` entre os seeds existentes em `main.py`. O seed
de capas roda depois e encontra as entradas novas: capa padrão aplicada no
mesmo boot, sem janela de "entrada sem capa". (Hoje oVS Code registrado à mão
só ganhou capa no boot seguinte — a ordem nova elimina isso para deploys
novos.)

### D4 — Nomes de exibição alinhados às capas versionadas

Os nomes ("Webtop XFCE", "Ubuntu KDE", "Alpine MATE", "VS Code") contêm as
palavras-chave que o `seed_image_covers` já resolve (`xfce`, `kde`, `mate`,
`vscode`), então cada entrada nasce com sua capa correta no mesmo boot, sem
nenhum mapeamento extra.

### D5 — Tags móveis `:latest`, versão por digest

Mesmo comportamento do cadastro manual: `:latest` com `image_version`
capturada por digest/label (`version_from_image_info`), atualização via
"atualizar imagem" do admin. Pinhar tag por versão no seed envelheceria mal
e divergiria do fluxo manual que o produto já tem.

## Risks / Trade-offs

- [Admin registrou webtop:latest manualmente e o seed "não faz nada"] → é o
  comportamento desejado (D1); a entrada existente prevalece.
- [Quatro downloads grandes em todo primeiro boot (~4-8GB)] → em segundo
  plano, com progresso observável e retry-pull; sem custo no tempo de
  startup (D2). Espaço em disco passa a ser requisito do deploy — anotado
  no README.
- [`:latest` muda debaixo do catálogo] → mesmo risco já aceito no fluxo
  manual; versão registrada por digest dá a visibilidade.
- [Seed com conflito de UNIQUE por corrida] → impossível em um worker com
  execução sequencial no lifespan; `ConflictError` tratado como "já existe"
  por robustez.

## Migration Plan

Deploy único, aditivo. Em bancos existentes com as entradas já cadastradas:
nada muda (D1). Rollback: `git revert` — entradas criadas pelo seed ficam no
catálogo (dados do admin), o que é inofensivo.
