# Spec Delta

## MODIFIED Requirements

### Requirement: Estado de prontidão da imagem é observável

Cada entrada DEVE expor seu estado entre provisionamento em andamento, pronta
e falha, e o progresso DEVE ser consultável enquanto o provisionamento ocorre,
seja ele por download de um repositório remoto ou por build local de um
Dockerfile.

#### Scenario: Consulta durante o download

- **WHEN** um administrador consulta uma entrada com download em andamento
- **THEN** o sistema retorna o estado de download e o progresso corrente

#### Scenario: Download concluído

- **WHEN** o download de uma imagem termina com sucesso
- **THEN** a entrada passa ao estado pronta

#### Scenario: Download falha

- **WHEN** o download de uma imagem falha
- **THEN** a entrada passa ao estado de falha
- **AND** o motivo da falha fica disponível ao administrador

## ADDED Requirements

### Requirement: Entrada do catálogo define a porta de encaminhamento do container

Cada entrada DEVE registrar a porta em que o processo de interface do
container escuta, usada pelo encaminhamento de sessão, com um valor padrão
quando omitida.

#### Scenario: Porta definida no registro

- **WHEN** uma entrada é registrada informando a porta de encaminhamento
- **THEN** a entrada guarda essa porta
- **AND** instâncias criadas a partir dela são encaminhadas a essa porta

#### Scenario: Porta omitida no registro

- **WHEN** uma entrada é registrada sem informar a porta de encaminhamento
- **THEN** a entrada recebe a porta padrão do sistema
