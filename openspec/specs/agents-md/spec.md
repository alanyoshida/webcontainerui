# agents-md Specification

## Purpose

Mantém uma biblioteca de documentos `AGENTS.md` gerenciada pelo administrador
do portal, permite vincular cada entrada do catálogo a um deles e injeta o
documento nas instâncias criadas a partir daquela entrada.

## Requirements

### Requirement: Biblioteca de documentos AGENTS.md é gerenciada somente pelo administrador

O sistema DEVE oferecer criação, edição, listagem e remoção de documentos
`AGENTS.md` nomeados, restritas a usuários com papel de administrador.

#### Scenario: Administrador cria um documento

- **WHEN** um administrador envia nome e conteúdo de um novo documento
- **THEN** o documento passa a existir na biblioteca, listável e editável

#### Scenario: Usuário comum tenta gerenciar documentos

- **WHEN** um usuário sem papel de administrador tenta criar, editar ou
  remover um documento
- **THEN** o sistema recusa a operação por falta de permissão
- **AND** a biblioteca permanece inalterada

### Requirement: Nome do documento é único e o conteúdo é obrigatório

O sistema DEVE recusar a criação de documento cujo nome já exista na
biblioteca e DEVE recusar conteúdo vazio ou maior que o limite configurado.

#### Scenario: Nome duplicado

- **WHEN** um administrador tenta criar um documento com nome já usado
- **THEN** o sistema recusa a operação e informa o conflito
- **AND** o documento existente permanece inalterado

#### Scenario: Conteúdo vazio ou excedente

- **WHEN** um administrador envia conteúdo vazio ou acima do limite de
  tamanho configurado
- **THEN** o sistema recusa a operação
- **AND** nenhum documento é criado nem alterado

### Requirement: Cada entrada do catálogo vincula-se a no máximo um documento

O sistema DEVE permitir vincular uma entrada do catálogo a no máximo um
documento da biblioteca, e DEVE permitir remover o vínculo sem remover o
documento.

#### Scenario: Vincular um documento

- **GIVEN** uma entrada do catálogo e um documento existente na biblioteca
- **WHEN** um administrador vincula o documento à entrada
- **THEN** a entrada passa a referenciar aquele documento

#### Scenario: Trocar o documento vinculado

- **GIVEN** uma entrada com um documento vinculado
- **WHEN** um administrador vincula outro documento à mesma entrada
- **THEN** a entrada passa a referenciar o novo documento
- **AND** o documento anterior continua na biblioteca, sem vínculo com ela

#### Scenario: Remover o vínculo

- **GIVEN** uma entrada com um documento vinculado
- **WHEN** um administrador remove o vínculo
- **THEN** a entrada passa a não referenciar nenhum documento
- **AND** o documento permanece intacto na biblioteca

### Requirement: Documento vinculado é injetado na criação da instância

Ao criar uma instância cuja imagem tem documento vinculado, o sistema DEVE
gravar o conteúdo como `/config/AGENTS.md` no container, com o dono adequado
ao tipo de imagem, sem impedir a instância de ficar pronta em caso de falha
da injeção. Retomar uma instância parada (parar e iniciar de novo) reaproveita
o container existente e NÃO repete essa injeção — a instância só recebe uma
versão nova do documento se for recriada (excluída e criada de novo) ou se
estiver viva quando o documento for editado ou revinculado (ver "Salvar
documento reescreve nas instâncias vivas").

#### Scenario: Instância de imagem com documento

- **GIVEN** uma imagem do catálogo com documento vinculado
- **WHEN** uma instância dela é criada
- **THEN** o arquivo `/config/AGENTS.md` existe no container com o conteúdo
  do documento

#### Scenario: Instância de imagem sem documento

- **GIVEN** uma imagem do catálogo sem documento vinculado
- **WHEN** uma instância dela é criada
- **THEN** nenhum `AGENTS.md` de biblioteca é gravado no container

#### Scenario: Falha na injeção não impede a instância

- **GIVEN** uma imagem com documento vinculado cuja injeção falha
- **WHEN** a instância é criada
- **THEN** a instância fica pronta normalmente
- **AND** permanece utilizável, apenas sem o documento

### Requirement: Salvar documento reescreve nas instâncias vivas

Quando um administrador edita o conteúdo de um documento ou altera o vínculo
de uma imagem, o sistema DEVE reescrever o arquivo nas instâncias vivas das
imagens afetadas, isolando falhas por instância.

#### Scenario: Edição de conteúdo propaga

- **GIVEN** instâncias vivas de imagens vinculadas a um documento
- **WHEN** um administrador salva novo conteúdo para o documento
- **THEN** cada instância viva afetada passa a ter a nova versão do arquivo
- **AND** uma falha em uma instância não impede a atualização das demais
- **AND** o resultado de cada instância é informado ao administrador

#### Scenario: Novo vínculo propaga

- **GIVEN** instâncias vivas de uma imagem sem documento
- **WHEN** um administrador vincula um documento a essa imagem
- **THEN** cada instância viva passa a receber o arquivo do documento

### Requirement: Desvincular remove o documento das instâncias vivas

Quando um administrador desvincula um documento de uma imagem, o sistema
DEVE remover o arquivo `/config/AGENTS.md` das instâncias vivas dessa
imagem, isolando falhas por instância.

#### Scenario: Remoção do arquivo nas instâncias vivas

- **GIVEN** instâncias vivas de uma imagem com documento vinculado
- **WHEN** um administrador remove o vínculo
- **THEN** o arquivo deixa de existir em cada instância viva
- **AND** uma falha de remoção em uma instância não impede as demais

### Requirement: Remoção de documento é recusada com vínculos ativos

O sistema DEVE recusar a remoção de um documento da biblioteca enquanto
alguma entrada do catálogo o referenciar, informando o conflito.

#### Scenario: Remover documento em uso

- **GIVEN** um documento vinculado a uma ou mais imagens
- **WHEN** um administrador tenta removê-lo
- **THEN** o sistema recusa a operação e informa o conflito
- **AND** o documento e seus vínculos permanecem intactos
