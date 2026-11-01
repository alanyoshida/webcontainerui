# desktop-instances Specification

## Purpose

Governa as sessões de desktop de cada usuário: quando um container nasce, para e
é removido, onde seus arquivos persistem entre execuções, quantas sessões uma
pessoa pode manter, e como sessões abandonadas deixam de consumir memória do
host.

## Requirements

### Requirement: Instância pertence a exatamente um usuário

Toda instância DEVE registrar o usuário que a criou como seu único dono, e esse
vínculo NÃO DEVE poder ser transferido.

#### Scenario: Dono registrado na criação

- **WHEN** um usuário cria uma instância
- **THEN** a instância registra esse usuário como dono

### Requirement: Instância expõe três estados de execução

O sistema DEVE representar a execução de uma instância pelos estados ausente,
em execução e parada, além de estados transitórios de inicialização e de erro.
NÃO DEVE existir estado de pausa.

#### Scenario: Estados oferecidos ao usuário

- **WHEN** um usuário consulta suas instâncias
- **THEN** cada uma apresenta um estado entre em execução, parada, iniciando ou erro
- **AND** nenhuma ação de pausa é oferecida

### Requirement: Usuário mantém no máximo uma instância por imagem

O sistema DEVE recusar a criação de uma segunda instância da mesma imagem para o
mesmo usuário, permitindo instâncias simultâneas de imagens diferentes.

#### Scenario: Segunda instância da mesma imagem

- **GIVEN** um usuário com instância existente de uma imagem
- **WHEN** esse usuário pede uma nova instância da mesma imagem
- **THEN** o sistema não cria uma segunda instância
- **AND** devolve a instância já existente

#### Scenario: Instâncias de imagens diferentes

- **GIVEN** um usuário com permissão sobre duas imagens distintas
- **WHEN** esse usuário cria uma instância de cada uma
- **THEN** ambas as instâncias existem simultaneamente

### Requirement: Container da instância não publica porta no host

O sistema DEVE criar o container sem nenhuma porta publicada, acessível somente
pela rede interna usada pelo portal, para que não exista endereço alternativo de
acesso à instância.

#### Scenario: Inspeção do container criado

- **WHEN** uma instância é criada
- **THEN** o container não possui nenhuma porta mapeada no host
- **AND** está conectado à rede interna do portal

### Requirement: Container recebe credencial interna própria

O sistema DEVE gerar uma credencial de acesso aleatória e distinta por instância,
configurá-la no container e armazená-la para uso do encaminhamento, de modo que o
container nunca fique sem autenticação.

#### Scenario: Credencial por instância

- **WHEN** duas instâncias são criadas
- **THEN** cada uma possui credencial própria e diferente da outra

### Requirement: Container tem o compartilhamento de sessão desligado

O sistema DEVE criar o container com os recursos nativos de compartilhamento de
sessão desabilitados, pois tais links concedem controle total da sessão sem
autenticação própria.

#### Scenario: Configuração do container criado

- **WHEN** uma instância é criada
- **THEN** o compartilhamento de sessão está desabilitado na configuração do container

### Requirement: Container tem o transporte alternativo de mídia desligado

O sistema DEVE criar o container sem o transporte de mídia que trafega fora do
encaminhamento do portal, para que todo o tráfego da sessão passe pela
autorização.

#### Scenario: Configuração do container criado

- **WHEN** uma instância é criada
- **THEN** o transporte de mídia que contorna o encaminhamento está desabilitado

### Requirement: Arquivos do usuário persistem em volume por usuário e imagem

O sistema DEVE montar um volume dedicado ao par usuário e imagem no diretório
pessoal do container, de modo que os arquivos sobrevivam a paradas e reinícios.

#### Scenario: Reinício após parada

- **GIVEN** um usuário que criou arquivos na sua instância e a parou
- **WHEN** esse usuário inicia a instância novamente
- **THEN** os arquivos criados anteriormente continuam presentes

#### Scenario: Isolamento entre usuários

- **GIVEN** dois usuários com instâncias da mesma imagem
- **WHEN** cada um grava arquivos na sua instância
- **THEN** nenhum deles vê os arquivos do outro

### Requirement: Parar instância preserva o volume

A ação de parar DEVE encerrar o container e DEVE manter o volume do usuário
intacto.

#### Scenario: Parada de instância

- **WHEN** um usuário para sua instância
- **THEN** o container deixa de executar
- **AND** o volume associado continua existindo

### Requirement: Excluir instância remove o volume após confirmação

A ação de excluir DEVE remover o container e o volume do usuário, e DEVE exigir
confirmação explícita por envolver perda definitiva de dados.

#### Scenario: Exclusão confirmada

- **WHEN** um usuário confirma a exclusão da sua instância
- **THEN** o container e o volume são removidos
- **AND** o usuário pode criar uma nova instância daquela imagem

#### Scenario: Exclusão sem confirmação

- **WHEN** a exclusão é pedida sem confirmação explícita
- **THEN** o sistema não remove nada

### Requirement: Usuário só controla as próprias instâncias

O sistema DEVE recusar qualquer ação de ciclo de vida sobre instância que não
pertença ao usuário que a solicita, sem revelar se ela existe.

#### Scenario: Ação sobre instância de outro usuário

- **WHEN** um usuário tenta parar ou excluir instância pertencente a outro
- **THEN** o sistema recusa a operação
- **AND** a instância alvo permanece inalterada

### Requirement: Usuário vê apenas as próprias instâncias

A listagem de instâncias DEVE conter somente as instâncias pertencentes ao usuário
que consulta.

#### Scenario: Listagem com instâncias de vários usuários

- **GIVEN** vários usuários com instâncias em execução ao mesmo tempo
- **WHEN** um deles consulta sua listagem
- **THEN** apenas as instâncias desse usuário são retornadas

### Requirement: Operações de container não bloqueiam as sessões em curso

As operações de ciclo de vida DEVEM ser executadas sem interromper o tráfego das
sessões ativas de outros usuários atendidas pelo mesmo processo.

#### Scenario: Criação concorrente com sessões ativas

- **GIVEN** sessões ativas transmitindo tela para outros usuários
- **WHEN** um usuário dispara a criação de uma instância
- **THEN** as sessões ativas continuam recebendo tráfego durante a operação

### Requirement: Falha na criação deixa estado de erro observável

Quando a criação ou o início de uma instância falhar, o sistema DEVE registrar o
estado de erro com o motivo e NÃO DEVE deixar container órfão em execução.

#### Scenario: Falha ao iniciar container

- **WHEN** o início do container falha
- **THEN** a instância fica em estado de erro com o motivo disponível ao usuário
- **AND** nenhum container daquela instância permanece em execução

### Requirement: Instância ociosa é parada automaticamente

O sistema DEVE parar instâncias em execução que não recebam acesso por um período
de inatividade configurável, preservando o volume do usuário.

#### Scenario: Inatividade além do limite

- **GIVEN** uma instância em execução sem nenhum acesso há mais tempo que o limite
- **WHEN** o sistema avalia a ociosidade
- **THEN** a instância é parada
- **AND** o volume do usuário é preservado

#### Scenario: Sessão em uso contínuo

- **GIVEN** uma instância com sessão ativa recebendo tráfego
- **WHEN** o sistema avalia a ociosidade
- **THEN** a instância não é parada

### Requirement: Estado real do container reconcilia com o registrado

O sistema DEVE corrigir o estado registrado de uma instância quando ele divergir
do estado real do container, de modo que um container encerrado por fora não
apareça como em execução. Essa correção DEVE acontecer periodicamente durante
a operação normal do portal, não apenas na inicialização do processo, para que
um container encerrado por fora enquanto o portal está no ar seja detectado
sem exigir um reinício.

#### Scenario: Container encerrado externamente

- **GIVEN** uma instância registrada como em execução cujo container foi encerrado por fora
- **WHEN** o sistema reconcilia os estados
- **THEN** a instância passa a constar como parada

#### Scenario: Container encerrado externamente durante a operação normal do portal

- **GIVEN** o portal em execução há mais tempo que um ciclo de reconciliação,
  com uma instância registrada como em execução
- **WHEN** o container dessa instância é encerrado por fora enquanto o portal
  continua no ar, sem reinício
- **THEN** a instância passa a constar como parada no ciclo de reconciliação
  seguinte, sem exigir um reinício do portal

### Requirement: Instâncias de usuário desabilitado são paradas

Ao desabilitar uma conta, o sistema DEVE parar as instâncias em execução desse
usuário, preservando seus volumes.

#### Scenario: Desabilitação com instância em execução

- **GIVEN** um usuário com instância em execução
- **WHEN** o administrador desabilita essa conta
- **THEN** a instância é parada
- **AND** o volume é preservado

### Requirement: Listagem de instâncias é apresentada em tabela com ações por linha

A listagem de instâncias do usuário DEVE apresentar uma linha por instância,
com nome do template, referência da imagem, estado e as ações disponíveis
alinhadas na mesma linha, em vez de cartões em grade. Em janelas estreitas, a
listagem DEVE compactar-se para que as ações permaneçam alcançáveis na largura
da janela, sem gerar rolagem horizontal do documento.

#### Scenario: Ações de uma instância em execução

- **WHEN** um usuário consulta a listagem e uma de suas instâncias está em execução
- **THEN** a linha dessa instância oferece as ações abrir sessão, parar e excluir

#### Scenario: Ações de uma instância parada ou em erro

- **WHEN** um usuário consulta a listagem e uma de suas instâncias está parada ou em erro
- **THEN** a linha dessa instância oferece as ações iniciar e excluir

#### Scenario: Listagem em janela estreita

- **WHEN** um usuário consulta a listagem numa janela de largura de celular
- **THEN** as ações de cada instância permanecem visíveis e acionáveis na
  largura da janela
- **AND** o documento não apresenta rolagem horizontal

### Requirement: Parar instância exige confirmação

A ação de parar uma instância — na listagem ou na visão dedicada da sessão —
DEVE exigir confirmação explícita antes de encerrar o container, informando
que os processos em execução são interrompidos e que os arquivos permanecem
salvos.

#### Scenario: Parada confirmada

- **WHEN** um usuário confirma a parada da instância
- **THEN** o container é encerrado

#### Scenario: Parada sem confirmação

- **WHEN** a parada é pedida sem confirmação explícita
- **THEN** o sistema não encerra o container

### Requirement: Home apresenta resumo das instâncias em execução

A página inicial DEVE apresentar, em área visível sem rolagem, um resumo das
instâncias do usuário que estão em execução, com atalho direto para abrir a
sessão de cada uma.

#### Scenario: Resumo com instância em execução

- **GIVEN** um usuário com uma instância em execução
- **WHEN** ele abre a página inicial
- **THEN** a instância em execução aparece no resumo visível sem rolagem
- **AND** o resumo oferece o atalho para abrir a sessão dela

#### Scenario: Resumo sem instâncias em execução

- **GIVEN** um usuário sem nenhuma instância em execução
- **WHEN** ele abre a página inicial
- **THEN** o resumo indica que não há instâncias em execução

### Requirement: Abrir sessão troca a página para uma visão dedicada

Ao abrir a sessão de uma instância, o sistema DEVE substituir a listagem pela
visão dessa sessão como conteúdo central da página, sem navegar para outro
endereço. O usuário DEVE poder voltar à listagem a partir da visão da sessão.

#### Scenario: Abertura de sessão

- **WHEN** um usuário abre a sessão de uma instância em execução
- **THEN** a listagem deixa de ser exibida
- **AND** a sessão passa a ocupar a área central da página

#### Scenario: Retorno à listagem

- **GIVEN** a visão dedicada de uma sessão aberta
- **WHEN** o usuário aciona a ação de voltar
- **THEN** a listagem volta a ser exibida no lugar da visão da sessão

### Requirement: Visão da sessão aberta oferece parar e excluir

A visão dedicada de uma sessão aberta DEVE oferecer as mesmas ações de parar
e excluir disponíveis na listagem, sem exigir que o usuário volte à listagem
para executá-las.

#### Scenario: Parar pela visão da sessão

- **GIVEN** a visão dedicada de uma sessão aberta
- **WHEN** o usuário aciona a ação de parar
- **THEN** a instância passa a parada
- **AND** o usuário permanece na visão dedicada, que passa a refletir o
  estado parado em vez da sessão incorporada

#### Scenario: Excluir pela visão da sessão

- **GIVEN** a visão dedicada de uma sessão aberta
- **WHEN** o usuário confirma a exclusão da instância
- **THEN** a instância e seu volume são removidos
- **AND** o usuário retorna à listagem
