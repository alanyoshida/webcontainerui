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
oferta a novos usuários e preservando seu registro. A desabilitação DEVE exigir
confirmação explícita que descreva o efeito de retirar a imagem da oferta.

#### Scenario: Imagem desabilitada

- **WHEN** um administrador desabilita uma entrada do catálogo
- **THEN** a entrada deixa de aparecer no catálogo dos usuários
- **AND** novas instâncias a partir dela são recusadas

#### Scenario: Desabilitação sem confirmação

- **WHEN** a desabilitação de uma entrada é pedida sem confirmação explícita
- **THEN** o sistema não altera a entrada

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

### Requirement: Admin atualiza a imagem de uma entrada pronta

O sistema DEVE permitir que um administrador dispare o novo download da
referência de imagem de uma entrada do catálogo já pronta (`ready`), para
acompanhar versões publicadas pela origem (tags móveis). Durante o download a
entrada DEVE voltar ao estado em andamento e ao concluir DEVE retornar a
pronta; em falha DEVE seguir o fluxo de retry existente. Entradas de build
seguem o fluxo de rebuild já definido, sem mudança.

#### Scenario: Atualização concluída

- **WHEN** um administrador dispara a atualização de uma entrada pronta e o
  download conclui com sucesso
- **THEN** a entrada registra a versão da imagem recém-baixada
- **AND** a entrada volta ao estado pronta

#### Scenario: Instanciação bloqueada durante a atualização

- **WHEN** a entrada está com download em andamento por atualização
- **THEN** criar instância a partir dela é recusado

#### Scenario: Falha de download durante a atualização

- **WHEN** o download da atualização falha
- **THEN** a entrada fica em falha com a mensagem do erro
- **AND** o fluxo de nova tentativa existente volta a valer para ela

#### Scenario: Re-pull de conteúdo idêntico

- **WHEN** o download conclui e a origem não mudou o conteúdo da referência
- **THEN** a entrada permanece pronta, sem efeito sobre as instâncias
  existentes

#### Scenario: Usuário comum tenta atualizar

- **WHEN** um usuário sem papel de administrador tenta atualizar a imagem de
  uma entrada
- **THEN** o sistema recusa a operação por falta de permissão

### Requirement: Catálogo registra a versão da imagem baixada

Ao concluir um download, o sistema DEVE registrar na entrada do catálogo uma
identificação legível da versão da imagem baixada: o rótulo de versão da
imagem quando disponível (por exemplo, o rótulo de build das imagens
LinuxServer) e, na ausência dele, o identificador curto do conteúdo baixado.
A versão registrada DEVE ser exposta na API e na interface do catálogo. O
download de uma nova versão DEVE substituir a versão registrada.

#### Scenario: Versão capturada no download

- **WHEN** um download conclui com sucesso
- **THEN** a entrada registra a versão legível da imagem baixada

#### Scenario: Imagem sem rótulo de versão

- **WHEN** o download conclui e a imagem não publica rótulo de versão
- **THEN** a entrada registra o identificador curto do conteúdo baixado

### Requirement: Capa carrega somente de origem própria

A interface DEVE exibir a capa de uma entrada do catálogo apenas quando a URL informada aponta para o armazenamento próprio do portal (`/uploads/`); qualquer outra origem cai no mesmo estado visual de capa ausente, sem carregar conteúdo externo.

#### Scenario: Capa válida

- **WHEN** a entrada do catálogo informa `icon_url` iniciada por `/uploads/`
- **THEN** a interface carrega e exibe a capa

#### Scenario: URL externa é recusada

- **WHEN** a entrada do catálogo informa `icon_url` de origem externa ao portal
- **THEN** a interface não requisita essa URL
- **AND** exibe o mesmo tratamento visual de entrada sem capa

### Requirement: Entradas de desktop padrão são garantidas no startup

O sistema DEVE garantir, a cada inicialização, que as entradas de desktop
padrão do produto existam no catálogo, registrando as ausentes com
provisionamento por download iniciado em segundo plano. Uma entrada que já
exista no catálogo DEVE ser mantida como está: o seed NÃO DEVE duplicá-la,
reativá-la, sobrescrever seus limites nem sua capa. Falha no download de uma
entrada NÃO DEVE impedir o startup do portal nem o provisionamento das
demais.

#### Scenario: Banco vazio no primeiro startup

- **WHEN** o portal inicia com um catálogo vazio
- **THEN** as entradas de desktop padrão são registradas com download iniciado
- **AND** cada uma fica observável como em provisionamento, sem bloquear o startup

#### Scenario: Entrada já configurada pelo administrador

- **GIVEN** uma das entradas padrão já existe no catálogo, desabilitada ou com limites editados
- **WHEN** o portal inicia
- **THEN** a entrada permanece exatamente como estava, sem nova linha nem download disparado

#### Scenario: Falha de download isolada

- **WHEN** o download de uma das entradas padrão falha
- **THEN** o estado de falha fica observável na entrada e as demais seguem
- **AND** o portal sobe normalmente, com a entrada recuperável por nova tentativa
