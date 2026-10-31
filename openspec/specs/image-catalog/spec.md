# image-catalog Specification

## Purpose

Mantém o conjunto de imagens de desktop que o portal oferece, incluindo o
download da imagem e o estado de prontidão que decide se ela já pode ser usada
para criar instâncias, de modo que o usuário final nunca espere um download de
vários gigabytes ao iniciar sua sessão.

## Requirements

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

#### Scenario: Consulta durante o build

- **WHEN** um administrador consulta uma entrada com build em andamento
- **THEN** o sistema retorna o estado de provisionamento e o progresso
  corrente

#### Scenario: Build concluído

- **WHEN** o build de uma imagem termina com sucesso
- **THEN** a entrada passa ao estado pronta

#### Scenario: Build falha

- **WHEN** o build de uma imagem falha
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

### Requirement: Provisionamento por build é distinguível e repetível

Cada entrada DEVE registrar se foi provisionada por download de registry ou
por build local. Quando o provisionamento falhar, o sistema DEVE permitir
repeti-lo pelo mesmo tipo usado originalmente.

#### Scenario: Repetir download falho

- **GIVEN** uma entrada provisionada por download em estado de falha
- **WHEN** a repetição é solicitada
- **THEN** o sistema executa um novo download

#### Scenario: Repetir build falho

- **GIVEN** uma entrada provisionada por build em estado de falha
- **WHEN** a repetição é solicitada
- **THEN** o sistema executa um novo build, não um download

### Requirement: Rebuild só ocorre quando o contexto de build muda

Uma entrada provisionada por build DEVE guardar a identidade do conteúdo do
seu contexto e só DEVE ser reconstruída quando esse conteúdo mudar.

#### Scenario: Contexto inalterado

- **GIVEN** uma entrada provisionada por build já pronta
- **WHEN** o provisionamento é reavaliado sem mudança de contexto
- **THEN** a entrada não é reconstruída

#### Scenario: Contexto alterado

- **GIVEN** uma entrada provisionada por build já pronta
- **WHEN** o conteúdo do seu contexto de build muda
- **THEN** a entrada é reconstruída

### Requirement: Entrada do catálogo define a porta de encaminhamento do container

Cada entrada DEVE registrar a porta em que o processo de interface do
container escuta, com um valor padrão quando omitida. A porta DEVE ser usada
tanto pelo encaminhamento de sessão quanto pela variável de ambiente `PORT`
injetada no container.

#### Scenario: Porta definida no provisionamento interno

- **WHEN** o portal provisiona uma entrada com porta de encaminhamento própria
- **THEN** a entrada guarda essa porta
- **AND** instâncias criadas a partir dela são encaminhadas a essa porta
- **AND** o container recebe essa porta como `PORT`

#### Scenario: Porta omitida no registro

- **WHEN** uma entrada é registrada sem informar a porta de encaminhamento
- **THEN** a entrada recebe a porta padrão do sistema
