# Spec Delta

## Purpose

Mantém o conjunto de imagens de desktop que o portal oferece, incluindo o
download da imagem e o estado de prontidão que decide se ela já pode ser usada
para criar instâncias, de modo que o usuário final nunca espere um download de
vários gigabytes ao iniciar sua sessão.

## ADDED Requirements

### Requirement: Somente administrador gerencia o catálogo

O sistema DEVE restringir o registro, a edição e a remoção de entradas do
catálogo a usuários com papel de administrador.

#### Scenario: Usuário comum tenta registrar imagem

- **WHEN** um usuário sem papel de administrador tenta registrar uma imagem
- **THEN** o sistema recusa a operação por falta de permissão
- **AND** o catálogo permanece inalterado

### Requirement: Entrada do catálogo identifica a imagem de container

Cada entrada do catálogo DEVE registrar um nome de exibição e a referência da
imagem de container, composta por repositório e tag, que define o desktop a ser
executado.

#### Scenario: Registro de imagem

- **WHEN** um administrador registra um nome de exibição, repositório e tag
- **THEN** a entrada passa a existir no catálogo com essa referência

### Requirement: Referência de imagem é única no catálogo

O sistema DEVE recusar o registro de uma entrada cuja combinação de repositório e
tag já exista no catálogo.

#### Scenario: Repositório e tag duplicados

- **WHEN** um administrador registra repositório e tag já presentes no catálogo
- **THEN** o sistema recusa a operação e informa o conflito

### Requirement: Entrada do catálogo define os limites de recurso do container

Cada entrada DEVE registrar os limites de recurso aplicados aos containers criados
a partir dela, incluindo memória compartilhada, memória e CPU, de modo que o
administrador controle o consumo por tipo de desktop.

#### Scenario: Limites definidos no registro

- **WHEN** um administrador registra uma imagem informando limites de recurso
- **THEN** a entrada guarda esses limites
- **AND** containers criados a partir dela recebem esses limites

#### Scenario: Limites omitidos no registro

- **WHEN** um administrador registra uma imagem sem informar limites
- **THEN** a entrada recebe os limites padrão do sistema

### Requirement: Registro de imagem dispara o download

O sistema DEVE iniciar o download da imagem de container ao registrá-la no
catálogo, sem bloquear a resposta ao administrador.

#### Scenario: Download iniciado no registro

- **WHEN** um administrador registra uma imagem ainda não presente no host
- **THEN** o sistema responde imediatamente
- **AND** a entrada passa ao estado de download em andamento

### Requirement: Estado de prontidão da imagem é observável

Cada entrada DEVE expor seu estado entre download em andamento, pronta e falha,
e o progresso DEVE ser consultável enquanto o download ocorre.

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

### Requirement: Download pode ser repetido após falha

O sistema DEVE permitir ao administrador disparar novamente o download de uma
entrada em estado de falha, sem recriar a entrada.

#### Scenario: Nova tentativa de download

- **GIVEN** uma entrada em estado de falha
- **WHEN** o administrador dispara o download novamente
- **THEN** a entrada volta ao estado de download em andamento

### Requirement: Somente imagem pronta pode originar instância

O sistema NÃO DEVE permitir a criação de instância a partir de entrada que não
esteja no estado pronta.

#### Scenario: Tentativa de usar imagem em download

- **WHEN** um usuário com permissão tenta criar instância de imagem em download
- **THEN** o sistema recusa a operação e informa que a imagem não está pronta

### Requirement: Catálogo do usuário mostra apenas imagens prontas e permitidas

O catálogo apresentado a um usuário não administrador DEVE conter apenas as
entradas habilitadas, no estado pronta, e permitidas a ele.

#### Scenario: Catálogo com imagem permitida ainda em download

- **GIVEN** um usuário com permissão sobre uma imagem em download
- **WHEN** esse usuário consulta o catálogo
- **THEN** a imagem em download não aparece na listagem

### Requirement: Entrada pode ser desabilitada sem remoção

O sistema DEVE permitir desabilitar uma entrada do catálogo, retirando-a da
oferta a novos usuários e preservando seu registro.

#### Scenario: Imagem desabilitada

- **WHEN** um administrador desabilita uma entrada do catálogo
- **THEN** a entrada deixa de aparecer no catálogo dos usuários
- **AND** novas instâncias a partir dela são recusadas
