# Proposal

## Why

Hoje o catálogo de templates mostra apenas nome, repositório e tag em cartões
idênticos, o que dificulta reconhecer visualmente qual desktop escolher. A lista
de instâncias já lançadas é empilhada verticalmente sem nenhuma adaptação ao
tamanho da tela, o que fica ruim em telas estreitas. Esta change permite ao
administrador cadastrar uma imagem de capa para cada template (exibida ao
usuário no momento de escolher/lançar o container) e torna a lista de
instâncias responsiva, junto com um refresh visual geral da interface.

## What Changes

- Administrador pode enviar (upload) uma imagem de capa ao cadastrar ou editar
  uma entrada do catálogo.
- O cartão de cada template no catálogo do usuário passa a exibir essa imagem
  de capa; na ausência de imagem, exibe um placeholder consistente.
- A lista de instâncias já lançadas (`InstancesSection`/`InstanceCard`) passa a
  usar um layout em grade responsivo (como o catálogo já faz), em vez de
  empilhamento vertical fixo, adaptando o número de colunas ao tamanho da tela.
- Refresh visual geral dos cartões de catálogo e de instâncias (espaçamento,
  elevação, tipografia) usando o tema MUI existente — sem introduzir novo
  framework de estilo. Esta parte é puramente de apresentação e não altera
  contrato de comportamento, então não gera requisito de spec próprio.

## Capabilities

### New Capabilities

Nenhuma.

### Modified Capabilities

- `image-catalog`: entrada do catálogo passa a admitir uma imagem de capa
  opcional, enviada pelo administrador e exibida aos usuários no catálogo.
- `desktop-instances`: a listagem de instâncias do usuário passa a se
  apresentar em layout responsivo, adaptando o número de colunas ao tamanho da
  tela do dispositivo.

## Impact

- Backend: `backend/app/db.py` (nova coluna `icon_path`/`thumbnail` na tabela
  `images`), `backend/app/api/images.py` (novo endpoint de upload, inclusão do
  campo nas respostas), `backend/app/services/images.py` (armazenamento do
  caminho do arquivo), `backend/app/main.py` (nova rota estática para servir os
  arquivos enviados), `backend/app/config.py` (diretório de upload
  configurável).
- Frontend: `frontend/src/features/admin/ImagesPanel.jsx` (campo de upload no
  formulário de cadastro), `frontend/src/features/catalog/CatalogSection.jsx`
  (exibição da imagem de capa no cartão), `frontend/src/features/instances/InstancesSection.jsx`
  e `InstanceCard.jsx` (layout em grade responsivo), `frontend/src/api/client.js`
  (chamada de upload).
- Sem mudança de API pública além de novos campos opcionais e um novo endpoint
  de upload — não é **BREAKING**.
