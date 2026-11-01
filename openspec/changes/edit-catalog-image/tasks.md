# Tasks

## 1. Backend — edição e reativação

- [x] 1.1 Implementar `update_image` em `backend/app/services/images.py` (só as colunas recebidas, validação `> 0` e `port` 1–65535, `NotFoundError` se inexistente) e a rota `PATCH /api/admin/images/{id}` com `UpdateImageRequest` (400 se corpo vazio, `ImageResponse` na resposta, evento `admin.image.changed` com `detail=op=editar` na trilha) — testes: edição parcial preserva não-enviados, validação recusa valores inválidos com 400, 404 para id inexistente, identidade (`repository`/`tag`) inalterada mesmo com campos desconhecidos no corpo
- [x] 1.2 Implementar `POST /api/admin/images/{id}/enable` idempotente (204, `UPDATE enabled = 1`, evento `admin.image.changed` com `detail=op=reativar`) — testes: reativar desabilitada volta ao catálogo do usuário com grant; reativar ativa é no-op; 404 inexistente
- [x] 1.3 Remover `harden_desktop` de `CreateImageRequest`, `ImageResponse`, `create_image` (assinatura e INSERT) e dos testes que o citam; conferir que nenhuma consulta/escrita deixa de funcionar sem a coluna no INSERT (coluna NOT NULL DEFAULT 0 permanece no banco, sem migração) — suíte verde após a remoção

## 2. Frontend

- [x] 2.1 Adicionar `adminEditImage(imageId, payload)` (PATCH) e `adminEnableImage(imageId)` (POST) em `frontend/src/api/client.js` — conferência por uso nos componentes do grupo 2.2
- [x] 2.2 Em `ImagesPanel.jsx`: reutilizar o diálogo/formulário de criação para edição (pré-preenchido, submetendo só os campos alterados), botão de editar na linha e botão "reativar" visível apenas para entradas desabilitadas; texto curto no diálogo informando que instâncias existentes aplicam limites ao serem atualizadas — testes de componente: editar salva com payload parcial; entrada desabilitada mostra reativar e o clique chama a API
- [x] 2.3 Rodar `npm test -- --run` e `npm run build` verdes

## 3. Verificação de integração

- [x] 3.1 Rodar a suíte padrão (`cd backend && .venv/bin/python -m pytest`) verde
- [x] 3.2 Contra o stack dev: editar nome/limite de uma entrada via API e conferir a resposta; reativar a entrada desabilitada do catálogo de referência; criar instância da entrada editada e conferir o limite novo no `docker inspect` do container — evidência registrada na change

## Workflow follow-up

- Arquivar (`openspec archive "edit-catalog-image"`) após revisão, sincronizando o delta na spec `image-catalog`.
- Fechar o achado I1 do relatório de pentest referenciando esta change.
