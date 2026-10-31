# Design

## Context

Ver `proposal.md` para a motivação e os deltas em `specs/` para o contrato de
comportamento. Estado atual relevante:

- `seed_agent_images` (`backend/app/services/agent_images.py`) roda no `lifespan`
  depois da reconciliação e do backfill. Ele constrói a imagem base e as 5
  imagens de agente, registra as entradas ausentes e só reconstrói quando o
  `build_hash` do contexto muda. Hoje ele não toca em `icon_path`.
- `images.icon_path` guarda o nome do arquivo dentro de `uploads_dir`.
  `set_image_icon` (`backend/app/services/images.py`) valida PNG/JPEG/GIF/WebP
  por *magic bytes*, grava `<image_id>-<uuid>.<ext>`, atualiza `icon_path` e
  apaga o arquivo anterior. `ImageResponse.icon_url` expõe `/uploads/<icon_path>`.
- `uploads_dir` é criado no `lifespan`, e `/uploads` já é servido por
  `StaticFiles` (`backend/app/main.py`).
- O diretório `agent-images/` é copiado inteiro para a imagem do portal
  (`Dockerfile` raiz). O `context_hash` só percorre `_base` e o subdiretório de
  cada agente; arquivos em `agent-images/covers/` não entram no hash de build.
- Não há nenhum logo ou asset de imagem versionado no repositório. O frontend já
  exibe `icon_url` quando presente (`CatalogSection.jsx`), com altura fixa de
  140px e `objectFit: contain`, e mostra placeholder quando ausente.
- A validação de upload não aceita SVG, apenas formatos raster reconhecidos.

## Goals / Non-Goals

**Goals:**

- Cadastrar capa padrão em todas as entradas existentes no catálogo durante o
  startup, sem exigir ação do administrador e sem depender de rede.
- Resolver o logo pelo nome de exibição, repositório e tag, com fallback para
  uma capa genérica.
- Gerar capas 1200x400 PNG com a cor predominante da marca e apenas o logo.
- Preservar capas enviadas pelo administrador e atualizar automaticamente as
  capas padrão quando o asset versionado mudar.
- Manter o seed de capas independente do resultado do build das imagens e
  isolado por entrada.

**Non-Goals:**

- Alterar permissões de acesso, tornando imagens visíveis a todos.
- Iniciar instâncias automaticamente no startup.
- Cadastrar capa em imagens registradas depois do startup.
- Criar ação de UI para restaurar a capa padrão depois de um upload do admin.
- Introduzir geração de capas em tempo de execução ou dependência de internet
  no portal.

## Decisions

### D1: Origem da capa em coluna própria (`icon_source`)

Adicionar `images.icon_source TEXT` com valores `default` e `admin`. A migração
preenche `admin` para linhas que já têm `icon_path` (todo upload anterior era
manual) e deixa nulo para linhas sem capa. Uploads do administrador continuam
passando por `set_image_icon`, que passa a gravar `icon_source = 'admin'`; o seed
de capas grava `icon_source = 'default'`.

Sem essa coluna, não há como distinguir “capa padrão que pode ser atualizada” de
“capa do admin que deve ser preservada”. Alternativas consideradas:

- **Convenção no nome do arquivo** (`<id>-default-...`): evita coluna nova, mas
  é implícita e quebra se o admin enviar um arquivo com o mesmo prefixo.
- **Coluna `default_icon_path` separada de `icon_path`**: separa os dois mundos,
  mas duplica a lógica de URL e a semântica de substituição já existente.

### D2: Assets versionados em `agent-images/covers/`

O diretório conterá os PNGs finais 1200x400, os SVGs/PNGs de origem dos logos e
um script de geração reproduzível. Como `agent-images/` já é copiado para a
imagem do portal, nenhuma mudança de `Dockerfile` é necessária. Como o hash de
build não inclui `covers/`, mudar uma capa não dispara rebuild de imagem.

O seed procura os assets em `default_agent_images_dir() / "covers"`. O script de
geração roda apenas em desenvolvimento; o runtime só lê os PNGs versionados.
Alternativa considerada: gerar as capas dentro do portal com Pillow. Rejeitada
por adicionar dependência de runtime e por tornar o resultado dependente do
ambiente de execução.

### D3: Resolução por mapa local de palavras-chave

Um `LogoSpec` por logo contém chave, palavras-chave, cor de marca e caminho do
asset. A resolução normaliza `display_name`, `repository` e `tag` (minúsculas,
separadores e pontuação) e procura palavras-chave conhecidas. Quando o nome
contém distro e ambiente (ex.: `ubuntu kde`, `alpine MATE`), o ambiente tem
precedência sobre a distro. Quando nada corresponde, usa a capa genérica.

Mapa inicial: os 5 agentes (Claude Code, Hermes, Agy, OpenCode, oh-my-pi) e os
ambientes XFCE, KDE/Plasma, MATE, GNOME, Cinnamon, LXDE, LXQt, i3 e Sway. Nomes
como “Webtop” sem ambiente caem na capa genérica, conforme o escopo aprovado.

### D4: Composição da capa

Cada PNG final tem 1200x400 e é composto com fundo em gradiente da cor
predominante da marca e o logo centralizado, sem texto. O contraste do logo é
ajustado por marca (variante clara ou escura) para evitar logo invisível em
fundo da mesma cor. A capa genérica usa a cor primária do portal (`#1565c0`) e
um símbolo neutro de container/terminal.

### D5: Seed de capas separado do seed de imagens de agente

Novo serviço `backend/app/services/image_covers.py` com
`seed_image_covers(settings, base_dir=None)`, chamado no `lifespan` depois de
`seed_agent_images`. Separar responsabilidades evita acoplar a resolução de
capas ao build de imagens e deixa o seed de capas reutilizável para qualquer
entrada do catálogo.

O seed de capas abre sua própria conexão, percorre todas as entradas do
catálogo (inclusive desabilitadas e em falha), isola falhas por entrada e não
propaga exceção para o startup. Ele não espera nem depende do resultado do
build.

### D6: Atualização idempotente por hash no nome do arquivo

Para uma entrada com `icon_source = 'default'`, o seed calcula o hash SHA-256 do
PNG desejado e usa um nome determinístico
`<image_id>-default-<hash>.<ext>`. Se `icon_path` já aponta para esse arquivo e
ele existe, nada é feito. Se o hash mudou, grava o novo arquivo, atualiza
`icon_path` e apaga o arquivo padrão anterior. Entradas com
`icon_source = 'admin'` são ignoradas. Entradas sem `icon_path` recebem a capa
padrão.

Alternativa considerada: gravar sempre um UUID novo a cada startup. Rejeitada
por gerar churn de arquivos e por não detectar “já está atualizado”.

### D7: Sem alteração no frontend nem na API pública

O catálogo já consome `icon_url`; capas padrão aparecem como qualquer capa
enviada. O único campo novo no banco é interno. O painel de admin continua
usando o endpoint de upload existente; o upload passa a registrar
`icon_source = 'admin'` e a remover a capa padrão anterior, como já remove
qualquer capa anterior.

## Risks / Trade-offs

- [Uso de logos de terceiros e marcas registradas] → usar logos oficiais,
  registrar a fonte e a licença em `agent-images/covers/README.md`; se um logo
  não puder ser usado, cair para a capa genérica ou para um símbolo estilizado.
- [Contraste ruim em algumas marcas] → escolher a variante clara/escura do logo
  por marca e validar visualmente cada capa gerada.
- [Falso positivo na resolução por palavra-chave] → normalizar tokens e dar
  precedência a ambientes de desktop; nomes ambíguos caem na capa genérica e
  testes cobrem os casos citados.
- [Seed de capas atrasado por builds lentos] → o seed de capas roda depois do
  seed de imagens, mas não depende do resultado; uma falha de build não impede
  a capa. Se o atraso incomodar, o seed de capas pode ser movido para antes dos
  builds em uma iteração futura.
- [Acúmulo de arquivos no disco] → nome determinístico por hash e remoção do
  arquivo padrão anterior; só grava quando o conteúdo muda.
- [SVG no upload] → não aceitar SVG; as capas padrão são PNGs gerados e
  versionados.
- [Tamanho do asset] → manter cada PNG abaixo do limite configurado de upload e
  validar no seed antes de gravar.

## Migration Plan

1. Adicionar `images.icon_source` com migração idempotente em
   `backend/app/db.py`; preencher `admin` para linhas com `icon_path` não nulo.
2. Adicionar os assets em `agent-images/covers/` e o script de geração.
3. Implementar a resolução de logo e o seed de capas em
   `backend/app/services/image_covers.py`; ajustar `set_image_icon` para gravar
   `icon_source = 'admin'`.
4. Chamar `seed_image_covers` no `lifespan` depois de `seed_agent_images`.
5. No primeiro startup após o deploy, todas as entradas sem capa do admin
   recebem a capa padrão. Capas existentes do admin permanecem.
6. Rollback: remover a chamada do seed de capas; a coluna `icon_source` fica
   inerte e as capas padrão já gravadas continuam válidas como qualquer capa.
   Nenhuma migração destrutiva é executada.
