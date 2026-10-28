# Design

## Context

O catálogo (`backend/app/api/images.py`, `backend/app/services/images.py`,
tabela `images` em `backend/app/db.py`) hoje não tem nenhum campo de
imagem/arquivo, e o backend não tem nenhuma rota de upload existente (ver
proposal.md - Impact). O frontend não usa CSS próprio: todo o estilo passa pelo
tema MUI (`frontend/src/theme.js`) e pela prop `sx`, e o único padrão
responsivo hoje é o `Grid item xs/sm/md` já usado em
`CatalogSection.jsx`. A persistência do backend roda em container com volume
nomeado `wcui_db:/data` (`deploy/docker-compose.yml`), onde já vive o arquivo
SQLite.

## Goals / Non-Goals

**Goals:**
- Permitir upload de uma imagem de capa por entrada do catálogo e servi-la de
  volta ao frontend por URL estável.
- Reaproveitar o padrão de grade responsiva do MUI (`Grid item xs/sm/md`) já
  usado no catálogo, aplicando-o também à listagem de instâncias.
- Manter a superfície de API additiva (campos novos opcionais, endpoint novo),
  sem quebrar o schema atual de `ImageResponse`.

**Non-Goals:**
- Não introduzir Tailwind, CSS Modules ou outro mecanismo de estilo além do
  tema MUI já existente — o "modernizar o layout" do proposal.md é só ajuste de
  `sx`/tema, tratado como refatoração visual sem requisito de spec.
- Não suportar múltiplas imagens por entrada, nem galeria — uma imagem de capa
  por entrada.
- Não implementar redimensionamento/otimização de imagem no servidor (fora de
  escopo; apenas validação de tipo e tamanho).

## Decisions

### Armazenamento do arquivo: disco local sob o volume já existente

A imagem é salva em `Settings.uploads_dir` (novo campo, default
`/data/uploads/images`), dentro do mesmo volume nomeado `wcui_db` já montado em
`/data` para o SQLite. Isso evita declarar um volume novo no
docker-compose e mantém backup/restauração do `/data` cobrindo também as
imagens.

Alternativa considerada: armazenar o bytes da imagem como BLOB no SQLite.
Rejeitada porque complica servir a imagem por URL direta (exigiria uma rota
que leia o BLOB a cada requisição) sem ganho real, já que o volume de disco já
é persistente.

### Coluna nova: `icon_path` nullable em `images`

Guarda o caminho relativo do arquivo dentro de `uploads_dir` (não a URL
completa). `ImageResponse` ganha um campo `icon_url` derivado (construído a
partir de `icon_path` na camada de serviço), para o frontend não precisar
conhecer a estrutura de diretórios do servidor.

### Servir a imagem: nova rota estática dedicada, não reaproveitar `/assets`

Nova montagem `app.mount("/uploads", StaticFiles(directory=settings.uploads_dir), ...)`
em `backend/app/main.py`, condicional à existência do diretório (mesmo padrão
já usado para `/assets`). Mantém o mount de `/assets` exclusivo ao bundle do
frontend, sem misturar conteúdo gerado em runtime com build estático.

### Upload: endpoint multipart dedicado, não embutido no `POST /images`

Dado que não há precedente de `UploadFile` no backend, o upload é um endpoint
novo e específico — `POST /api/admin/images/{id}/icon` — chamado após a
criação da entrada (ou na edição), em vez de forçar o `CreateImageRequest`
atual a aceitar multipart. Mantém `POST /images` simples (JSON) e isola a
validação de arquivo (tipo MIME por assinatura, tamanho máximo configurável via
`Settings.max_icon_upload_mb`) num único lugar.

Alternativa considerada: aceitar a imagem já na criação via multipart form.
Rejeitada por exigir reescrever `CreateImageRequest` e seu teste existente só
para acomodar um campo opcional, quando um endpoint separado é additive e mais
simples de validar isoladamente.

### Layout responsivo das instâncias: trocar `.map` empilhado por `Grid`

`InstancesSection.jsx` passa a envolver os `InstanceCard` num
`Grid container spacing={2}` com `Grid item xs={12} sm={6} md={4}` — o mesmo
breakpoint já usado em `CatalogSection.jsx`, para consistência visual entre as
duas listagens. A sessão embutida (`InstanceSession`) dentro de cada card
continua ocupando a largura total do card (`xs={12}` interno), preservando área
útil de interação em qualquer número de colunas.

## Risks / Trade-offs

- [Upload sem antivírus/sanitização de conteúdo] → validar apenas por
  assinatura de tipo de imagem (magic bytes) e tamanho máximo; não processar o
  arquivo além de servi-lo estaticamente, reduzindo superfície de ataque.
- [Grade de 3 colunas deixa sessões embutidas (iframe/noVNC) pequenas em
  telas médias] → manter o breakpoint em `md={4}` (3 colunas) mas permitir que
  a sessão embutida, quando aberta, expanda temporariamente o card para
  `xs={12}` dentro do próprio grid item, preservando usabilidade.
- [Arquivos de imagem antigos (substituídos) acumulando no disco] → o upload
  que substitui a imagem remove o arquivo anterior do disco antes de gravar o
  novo caminho.

## Migration Plan

- Migração de schema: `ALTER TABLE images ADD COLUMN icon_path TEXT` em
  `backend/app/db.py`, aplicada no caminho de inicialização já existente do
  banco (idempotente, como as demais colunas da tabela).
- Deploy: nenhuma mudança de volume necessária (reaproveita `wcui_db:/data`);
  apenas garantir que `uploads_dir` seja criado na inicialização se ausente.
- Rollback: reverter a imagem da aplicação; a coluna nova fica inerte (nullable)
  e não afeta leituras antigas do schema.
