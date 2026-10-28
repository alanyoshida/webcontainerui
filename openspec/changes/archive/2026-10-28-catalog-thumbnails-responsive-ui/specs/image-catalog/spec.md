# Spec Delta

## ADDED Requirements

### Requirement: Entrada do catálogo admite imagem de capa opcional

Cada entrada do catálogo DEVE admitir uma imagem de capa opcional, enviada pelo
administrador, usada para identificar visualmente o template ao usuário.

#### Scenario: Cadastro com imagem de capa

- **WHEN** um administrador registra ou edita uma entrada enviando um arquivo de
  imagem como capa
- **THEN** a entrada passa a referenciar esse arquivo como sua imagem de capa

#### Scenario: Cadastro sem imagem de capa

- **WHEN** um administrador registra uma entrada sem enviar imagem de capa
- **THEN** a entrada é criada sem imagem de capa, sem erro

### Requirement: Upload de imagem de capa valida tipo e tamanho do arquivo

O sistema DEVE recusar o upload de imagem de capa cujo tipo não seja de imagem
reconhecida ou cujo tamanho exceda o limite configurado, sem alterar a entrada.

#### Scenario: Arquivo de tipo não suportado

- **WHEN** um administrador envia como imagem de capa um arquivo que não é uma
  imagem reconhecida
- **THEN** o sistema recusa o upload e informa o motivo
- **AND** a entrada permanece com a imagem de capa anterior, se havia

#### Scenario: Arquivo maior que o limite

- **WHEN** um administrador envia uma imagem de capa maior que o limite
  configurado de tamanho
- **THEN** o sistema recusa o upload e informa o motivo
- **AND** a entrada permanece com a imagem de capa anterior, se havia

### Requirement: Imagem de capa é exibida ao usuário no momento de escolher o template

O catálogo apresentado ao usuário DEVE exibir a imagem de capa de cada entrada
que a possua, e DEVE exibir um indicador visual padrão no lugar da imagem para
entradas sem imagem de capa cadastrada.

#### Scenario: Entrada com imagem de capa

- **GIVEN** uma entrada do catálogo com imagem de capa cadastrada
- **WHEN** um usuário consulta o catálogo para escolher um template
- **THEN** a imagem de capa dessa entrada é exibida junto a ela

#### Scenario: Entrada sem imagem de capa

- **GIVEN** uma entrada do catálogo sem imagem de capa cadastrada
- **WHEN** um usuário consulta o catálogo para escolher um template
- **THEN** um indicador visual padrão é exibido no lugar da imagem de capa

### Requirement: Nova imagem de capa substitui a anterior

O sistema DEVE substituir a imagem de capa anterior de uma entrada quando o
administrador enviar uma nova, sem manter o arquivo anterior acessível.

#### Scenario: Substituição de imagem

- **GIVEN** uma entrada com imagem de capa já cadastrada
- **WHEN** o administrador envia uma nova imagem de capa para essa entrada
- **THEN** o catálogo passa a exibir a nova imagem
- **AND** a imagem anterior deixa de ser acessível publicamente
