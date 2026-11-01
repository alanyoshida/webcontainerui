# Spec Delta — desktop-instances

## ADDED Requirements

### Requirement: Dono atualiza a própria instância mantendo os arquivos

O sistema DEVE permitir que o dono atualize a instância para a imagem atual
da entrada do catálogo: parar o container em execução, removê-lo sem apagar o
volume e recriá-lo do tag atual, com as mesmas credenciais e injeções da
criação. Os arquivos do volume DEVEM ser preservados e a instância DEVE
voltar a executar ao final. A atualização DEVE ser recusada quando a imagem
do catálogo não está pronta.

#### Scenario: Atualização de instância em execução

- **WHEN** o dono dispara a atualização de uma instância em execução
- **THEN** o sistema para e remove o container atual, recria do tag atual da
  imagem e a instância volta a executar
- **AND** os arquivos do volume são preservados

#### Scenario: Atualização de instância parada

- **WHEN** o dono dispara a atualização de uma instância parada
- **THEN** o sistema recria o container do tag atual da imagem ao iniciar,
  reutilizando volume e credenciais

#### Scenario: Confirmação com aviso de perda de trabalho

- **WHEN** o dono aciona a atualização na interface
- **THEN** a interface pede confirmação avisando que processos em andamento
  na sessão são perdidos
- **AND** a atualização só prossegue após a confirmação

#### Scenario: Falha na recriação

- **WHEN** a recriação do container falha
- **THEN** a instância fica em erro com a mensagem da falha
- **AND** o volume e os arquivos permanecem intactos
- **AND** tentar de novo religa ou recria a instância pelo fluxo existente

#### Scenario: Imagem não está pronta

- **WHEN** o dono tenta atualizar enquanto a entrada do catálogo está em
  download ou falha
- **THEN** o sistema recusa a atualização

#### Scenario: Não-dono tenta atualizar

- **WHEN** um usuário autenticado tenta atualizar instância de outro usuário
- **THEN** o sistema recusa sem revelar se a instância existe

### Requirement: Instância expõe a versão do container e indica desatualização

Ao criar ou recriar o container, o sistema DEVE registrar na instância a
versão da imagem usada na criação, e a interface DEVE apresentá-la ao dono.
Quando a versão registrada da instância for anterior à versão registrada da
entrada do catálogo, a interface DEVE indicar que a instância está
desatualizada. Instâncias criadas antes do registro de versão existir (sem
versão conhecida) NÃO DEVEM ser indicadas como desatualizadas.

#### Scenario: Versão registrada na criação

- **WHEN** uma instância é criada ou recriada com sucesso
- **THEN** ela registra a versão da imagem usada naquele momento

#### Scenario: Instância desatualizada

- **WHEN** a versão da imagem do catálogo passa a ser mais recente que a
  versão registrada da instância
- **THEN** a interface indica a instância como desatualizada, com a versão da
  instância e a versão disponível

#### Scenario: Instância sem versão conhecida

- **WHEN** uma instância criada antes do registro de versão é listada
- **THEN** nenhuma indicação de desatualização é apresentada para ela
