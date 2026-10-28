# Tasks

## 1. Backend: schema e configuração

- [x] 1.1 Adicionar coluna nullable `icon_path TEXT` à tabela `images` em
      `backend/app/db.py` e verificar com `backend/tests/test_db.py` (ou teste
      novo) que a migração roda em banco já existente sem erro
- [x] 1.2 Adicionar `uploads_dir: Path` (default `/data/uploads/images`) e
      `max_icon_upload_mb: int` a `Settings` em `backend/app/config.py`, criando
      o diretório na inicialização se ausente, e verificar com
      `backend/tests/test_config.py`

## 2. Backend: upload e substituição da imagem de capa

- [x] 2.1 Implementar `set_image_icon`/`clear_previous_icon` em
      `backend/app/services/images.py`: valida tipo por assinatura de arquivo e
      tamanho máximo, grava em `uploads_dir`, remove o arquivo anterior e
      atualiza `icon_path`; verificar com teste novo em
      `backend/tests/test_image_catalog.py` cobrindo substituição e remoção do
      arquivo antigo
- [x] 2.2 Adicionar endpoint `POST /api/admin/images/{id}/icon` (multipart,
      `UploadFile`) em `backend/app/api/images.py`, restrito a administrador,
      recusando arquivo de tipo não suportado ou maior que o limite; verificar
      com teste cobrindo os cenários de sucesso, tipo inválido e tamanho
      excedido
- [x] 2.3 Adicionar `icon_url` a `ImageResponse` (derivado de `icon_path`,
      `None` quando ausente) e expor nas respostas de `GET /images` (admin) e
      `GET /catalog` (usuário); verificar com teste de serialização em
      `backend/tests/test_image_catalog.py`

## 3. Backend: servir o arquivo enviado

- [x] 3.1 Montar `StaticFiles` em `/uploads` apontando para `uploads_dir` em
      `backend/app/main.py`, condicional à existência do diretório (mesmo
      padrão do mount de `/assets`); verificar com
      `backend/tests/test_health_and_spa.py` (ou teste novo) que uma imagem
      enviada é servida em `/uploads/...` com o content-type correto

## 4. Frontend: upload no formulário de administração

- [x] 4.1 Adicionar campo de seleção de arquivo de imagem de capa ao formulário
      em `frontend/src/features/admin/ImagesPanel.jsx`, chamando um novo método
      `api.adminUploadImageIcon(id, file)` em `frontend/src/api/client.js`
      (multipart); verificar com `ImagesPanel.test.jsx` cobrindo envio
      bem-sucedido e exibição de erro de upload

## 5. Frontend: exibição da imagem de capa no catálogo

- [x] 5.1 Exibir `icon_url` como imagem no `Card` de cada template em
      `frontend/src/features/catalog/CatalogSection.jsx`, com um placeholder
      visual padrão (ícone MUI) quando `icon_url` for `null`; verificar com
      `CatalogSection.test.jsx` cobrindo entrada com e sem imagem

## 6. Frontend: layout responsivo da listagem de instâncias e refresh visual

- [x] 6.1 Envolver os `InstanceCard` em `frontend/src/features/instances/InstancesSection.jsx`
      num `Grid container spacing={2}` com `Grid item xs={12} sm={6} md={4}`
      (mesmo breakpoint do catálogo), substituindo o empilhamento vertical
      atual; verificar com `InstanceCard.test.jsx`/`InstancesSection` que a
      listagem ainda renderiza todas as instâncias e que a sessão embutida
      aberta ocupa a largura total do card
- [x] 6.2 Ajustar espaçamento, elevação e tipografia dos cartões de catálogo e
      de instâncias via `sx`/tema (`frontend/src/theme.js`) para o refresh
      visual descrito no proposal.md, sem alterar comportamento; verificar
      visualmente no preview local (`npm run dev`) em larguras mobile, tablet e
      desktop

## 7. Verificação integrada

- [x] 7.1 Rodar a suíte completa (`pytest` no backend, `npm test` no frontend)
      e verificar que todos os testes passam
- [x] 7.2 Validar manualmente no preview: cadastrar imagem com e sem capa,
      substituir a capa, e redimensionar a janela na página de instâncias para
      confirmar a adaptação de colunas

## Workflow follow-up

- Sincronizar as specs delta (`image-catalog`, `desktop-instances`) para as
  specs principais e arquivar esta change após a revisão do usuário.
