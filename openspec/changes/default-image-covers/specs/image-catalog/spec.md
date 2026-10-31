# Spec Delta

## ADDED Requirements

### Requirement: Capa padrão é provisionada automaticamente no startup

Para cada entrada do catálogo existente no startup que ainda não tenha capa
enviada pelo administrador, o sistema DEVE cadastrar uma capa padrão, sem exigir
ação do administrador. A capa padrão NÃO DEVE depender do resultado do
provisionamento da imagem.

#### Scenario: Entradas sem capa recebem capa padrão

- **GIVEN** entradas do catálogo sem capa enviada pelo administrador
- **WHEN** o portal inicia
- **THEN** cada uma dessas entradas passa a referenciar uma capa padrão

#### Scenario: Entrada com capa do administrador é preservada

- **GIVEN** uma entrada com capa enviada pelo administrador
- **WHEN** o portal inicia
- **THEN** a capa do administrador continua sendo a capa da entrada
- **AND** nenhuma capa padrão é cadastrada por cima dela

#### Scenario: Entrada com provisionamento falho recebe capa padrão

- **GIVEN** uma entrada do catálogo cujo download ou build falhou
- **WHEN** o portal inicia
- **THEN** a entrada recebe capa padrão normalmente

#### Scenario: Falha ao cadastrar capa não impede o startup

- **GIVEN** uma entrada cuja capa padrão não pôde ser cadastrada
- **WHEN** o portal inicia
- **THEN** o portal conclui o startup normalmente
- **AND** as demais entradas recebem capa padrão normalmente

#### Scenario: Imagem registrada depois do startup

- **GIVEN** uma imagem registrada depois que o portal já iniciou, sem capa
- **WHEN** não houve novo startup
- **THEN** a entrada permanece sem capa padrão
- **AND** recebe capa padrão no próximo startup, se continuar sem capa do
  administrador

### Requirement: Capa padrão é escolhida pelo nome da imagem

O sistema DEVE resolver a capa padrão a partir do nome de exibição, repositório
e tag da entrada, usando um mapa local versionado de logos de agentes de código
e ambientes de desktop. Quando nenhum logo conhecido corresponder, o sistema
DEVE usar uma capa genérica.

#### Scenario: Nome com ambiente de desktop conhecido

- **WHEN** uma entrada tem nome de exibição como "Webtop XFCE"
- **THEN** sua capa padrão usa o logo do XFCE

#### Scenario: Nome com distro e ambiente

- **WHEN** uma entrada tem nome de exibição como "ubuntu kde" ou "alpine MATE"
- **THEN** sua capa padrão usa o logo do ambiente de desktop correspondente,
  não o da distro

#### Scenario: Nome com agente de código conhecido

- **WHEN** uma entrada corresponde a um dos agentes de código do catálogo
- **THEN** sua capa padrão usa o logo daquele agente

#### Scenario: Nome sem correspondência

- **WHEN** nenhum logo conhecido corresponde ao nome, repositório ou tag da
  entrada
- **THEN** a entrada recebe a capa genérica do portal

### Requirement: Capa padrão é atualizada quando o asset versionado muda

Quando o arquivo versionado da capa padrão de um logo mudar, o sistema DEVE
substituir a capa das entradas que ainda usam a capa padrão. Entradas com capa
enviada pelo administrador NÃO DEVEM ser alteradas.

#### Scenario: Asset da capa padrão alterado

- **GIVEN** uma entrada que ainda usa a capa padrão
- **AND** o arquivo versionado dessa capa mudou
- **WHEN** o portal inicia
- **THEN** a entrada passa a referenciar a nova capa padrão
- **AND** o arquivo anterior deixa de ser acessível publicamente

#### Scenario: Asset alterado, mas a entrada tem capa do administrador

- **GIVEN** uma entrada com capa enviada pelo administrador
- **AND** o arquivo versionado da capa padrão mudou
- **WHEN** o portal inicia
- **THEN** a capa do administrador permanece inalterada

#### Scenario: Asset da capa padrão inalterado

- **GIVEN** uma entrada que ainda usa a capa padrão
- **AND** o arquivo versionado dessa capa não mudou
- **WHEN** o portal inicia
- **THEN** a capa padrão existente é preservada
