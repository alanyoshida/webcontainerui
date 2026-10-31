# session-proxy Specification

## Purpose

Entrega a sessão de desktop ao navegador do dono e de mais ninguém, autorizando
cada requisição pela propriedade da instância antes de encaminhá-la ao container,
e carregando o tráfego interativo da sessão em ambos os sentidos.

## Requirements

### Requirement: Cada instância tem endereço próprio sob a origem do portal

O sistema DEVE atribuir a cada instância um caminho de acesso derivado do seu
identificador, servido na mesma origem do portal, para que a sessão possa ser
embutida na interface sem relaxar a política de origem do container.

#### Scenario: Endereço da instância

- **WHEN** uma instância entra em execução
- **THEN** ela passa a ser acessível por um caminho próprio sob a origem do portal

#### Scenario: Sessão embutida na interface

- **WHEN** o usuário abre sua instância na interface do portal
- **THEN** a sessão é exibida embutida, sem exigir outra origem

### Requirement: Encaminhamento exige sessão autenticada

O sistema DEVE recusar qualquer requisição ao caminho de uma instância que não
apresente sessão válida, sem encaminhar nada ao container.

#### Scenario: Requisição anônima ao caminho da instância

- **WHEN** uma requisição sem sessão válida atinge o caminho de uma instância
- **THEN** o sistema responde como não autenticado
- **AND** nada é encaminhado ao container

### Requirement: Encaminhamento exige propriedade da instância

O sistema DEVE recusar o acesso ao caminho de uma instância quando o usuário
autenticado não for seu dono, sem revelar se aquela instância existe.

#### Scenario: Usuário acessa instância de outro

- **GIVEN** dois usuários autenticados ao mesmo tempo, cada um com sua instância
- **WHEN** um deles requisita o caminho da instância do outro
- **THEN** o sistema recusa o acesso
- **AND** nada é encaminhado ao container do outro usuário

#### Scenario: Identificador de instância inexistente

- **WHEN** um usuário autenticado requisita o caminho de uma instância que não existe
- **THEN** a resposta é indistinguível da resposta dada a uma instância de outro dono

### Requirement: Autorização é verificada também na abertura do canal persistente

O sistema DEVE aplicar as mesmas verificações de autenticação e de propriedade ao
estabelecer o canal persistente que transporta a sessão interativa.

#### Scenario: Abertura de canal sobre instância de outro usuário

- **WHEN** um usuário tenta abrir o canal persistente da instância de outro
- **THEN** o sistema recusa o estabelecimento do canal

#### Scenario: Abertura de canal sem sessão válida

- **WHEN** uma requisição sem sessão válida tenta abrir o canal persistente
- **THEN** o sistema recusa o estabelecimento do canal

### Requirement: Credencial interna é injetada pelo encaminhamento

O sistema DEVE adicionar a credencial interna da instância à requisição
encaminhada, de modo que o usuário autenticado no portal não enfrente um segundo
pedido de autenticação.

#### Scenario: Acesso do dono à sua instância

- **WHEN** o dono acessa o caminho da sua instância
- **THEN** a requisição encaminhada carrega a credencial daquela instância
- **AND** o usuário não recebe pedido de autenticação do container

### Requirement: Credencial enviada pelo cliente não é repassada

O sistema DEVE descartar credenciais de autenticação presentes na requisição do
cliente antes de encaminhá-la, substituindo-as pela credencial da instância.

#### Scenario: Cliente envia credencial própria

- **WHEN** uma requisição do cliente traz credencial de autenticação
- **THEN** essa credencial é descartada
- **AND** a requisição encaminhada carrega apenas a credencial da instância

### Requirement: Tráfego interativo é transportado nos dois sentidos

O sistema DEVE transportar as mensagens do canal persistente do cliente para o
container e do container para o cliente, preservando seu conteúdo.

#### Scenario: Troca de mensagens na sessão

- **GIVEN** um canal persistente estabelecido pelo dono da instância
- **WHEN** cliente e container trocam mensagens
- **THEN** cada mensagem chega ao outro lado com o conteúdo preservado

### Requirement: Sessões longas não são encerradas por tempo de espera

O sistema DEVE manter o canal persistente aberto durante períodos prolongados sem
tráfego, para não interromper sessões de desktop ociosas antes do limite de
inatividade definido para as instâncias.

#### Scenario: Sessão sem tráfego por período prolongado

- **GIVEN** um canal persistente estabelecido e sem tráfego
- **WHEN** decorre um período prolongado abaixo do limite de inatividade
- **THEN** o canal continua aberto e utilizável

### Requirement: Encaminhamento não acumula o conteúdo em buffer

O sistema NÃO DEVE retardar o repasse acumulando o conteúdo da resposta, para que
a sessão interativa não acumule latência.

#### Scenario: Repasse de fluxo contínuo

- **WHEN** o container emite um fluxo contínuo de dados
- **THEN** os dados são repassados ao cliente conforme chegam

### Requirement: Acesso registra atividade da instância sem sobrecarregar o armazenamento

O sistema DEVE registrar a atividade da instância para alimentar a detecção de
ociosidade, e NÃO DEVE gravar no armazenamento persistente a cada mensagem
trafegada.

#### Scenario: Sessão com tráfego intenso

- **GIVEN** uma sessão trocando muitas mensagens por segundo
- **WHEN** o tráfego é encaminhado
- **THEN** a marca de atividade é persistida com frequência limitada
- **AND** a instância não é considerada ociosa

### Requirement: Acesso a instância não em execução não é encaminhado

O sistema DEVE recusar o encaminhamento quando a instância do dono não estiver em
execução, informando o estado em vez de tentar alcançar o container.

#### Scenario: Dono acessa instância parada

- **WHEN** o dono requisita o caminho da sua instância parada
- **THEN** o sistema não encaminha ao container
- **AND** informa que a instância não está em execução

### Requirement: Indisponibilidade do container é reportada ao cliente

Quando o container não responder ao encaminhamento, o sistema DEVE responder com
erro indicando indisponibilidade, sem expor detalhes internos de endereçamento.

#### Scenario: Container inalcançável

- **WHEN** o encaminhamento não consegue alcançar o container de uma instância
- **THEN** o sistema responde com erro de indisponibilidade
- **AND** a resposta não revela endereço ou nome interno do container

### Requirement: Encaminhamento direciona à porta definida pela entrada do catálogo

O sistema DEVE encaminhar a requisição e o canal persistente de uma instância
à porta de encaminhamento registrada na entrada do catálogo da sua imagem, em
vez de uma porta fixa única para todas as imagens. A porta usada no
encaminhamento DEVE ser a mesma injetada como `PORT` no container da
instância.

#### Scenario: Imagem com porta própria

- **GIVEN** uma instância cuja imagem registra uma porta de encaminhamento
  diferente da porta padrão
- **WHEN** uma requisição é encaminhada a essa instância
- **THEN** o sistema a encaminha à porta registrada na imagem
- **AND** o container foi iniciado com essa mesma porta em `PORT`

#### Scenario: Imagem com porta padrão

- **GIVEN** uma instância cuja imagem não define uma porta de encaminhamento
  diferente da padrão
- **WHEN** uma requisição é encaminhada a essa instância
- **THEN** o sistema a encaminha à porta padrão, como hoje
