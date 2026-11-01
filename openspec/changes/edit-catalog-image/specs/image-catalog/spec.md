# Spec Delta

## ADDED Requirements

### Requirement: Administrador edita a entrada do catálogo

O sistema DEVE permitir ao administrador editar o nome de exibição, os
limites de recurso e a porta de uma entrada do catálogo, alterando apenas os
campos recebidos. A identidade de provisionamento da entrada (repositório,
tag e forma de provisionamento) NÃO DEVE ser alterável por edição, e a
edição NÃO DEVE alterar o estado de provisionamento nem a habilitação da
entrada.

#### Scenario: Edição de nome e limites

- **WHEN** um administrador edita o nome e os limites de recurso de uma entrada
- **THEN** a entrada passa a refletir os valores recebidos
- **AND** os campos não enviados permanecem como estavam

#### Scenario: Identidade de provisionamento é imutável

- **WHEN** uma edição tenta alterar repositório, tag ou forma de provisionamento da entrada
- **THEN** o sistema recusa ou ignora esses campos
- **AND** a entrada continua provisionando a partir da identidade original

#### Scenario: Limites editados valem para instâncias novas e atualizadas

- **GIVEN** uma entrada com limites de recurso editados
- **WHEN** um usuário cria uma instância dessa entrada ou atualiza uma existente
- **THEN** o container é provisionado com os limites vigentes no catálogo

## MODIFIED Requirements

### Requirement: Entrada pode ser desabilitada sem remoção

O sistema DEVE permitir desabilitar uma entrada do catálogo, retirando-a da
oferta a novos usuários e preservando seu registro. A desabilitação DEVE exigir
confirmação explícita que descreva o efeito de retirar a imagem da oferta. O
sistema DEVE permitir reativar uma entrada desabilitada, devolvendo-a à oferta
conforme os grants vigentes.

#### Scenario: Imagem desabilitada

- **WHEN** um administrador desabilita uma entrada do catálogo
- **THEN** a entrada deixa de aparecer no catálogo dos usuários
- **AND** novas instâncias a partir dela são recusadas

#### Scenario: Desabilitação sem confirmação

- **WHEN** a desabilitação de uma entrada é pedida sem confirmação explícita
- **THEN** o sistema não altera a entrada

#### Scenario: Entrada desabilitada é reativada

- **GIVEN** uma entrada do catálogo desabilitada
- **WHEN** um administrador a reativa
- **THEN** ela volta a ser oferecida a novos usuários conforme os grants vigentes

#### Scenario: Reativação de entrada já ativa é idempotente

- **WHEN** um administrador reativa uma entrada que já está ativa
- **THEN** a entrada permanece ativa, sem erro e sem efeito colateral
