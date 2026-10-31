# coding-agent-images Specification

## Purpose

Mantém, dentro do catálogo existente, um conjunto fixo de imagens que dão
acesso em navegador a agentes de código de linha de comando, pelo mesmo
mecanismo de sessão usado pelos desktops, sem depender de ação manual do
administrador para existir.

## Requirements

### Requirement: Catálogo mantém um conjunto definido de imagens de agentes de código

O catálogo DEVE conter uma entrada para cada um dos seguintes agentes de
código em linha de comando: Claude Code CLI, Hermes, Agy, OpenCode e
oh-my-pi.

#### Scenario: Consulta ao catálogo lista as imagens de agente

- **WHEN** um usuário com permissão sobre essas imagens consulta o catálogo
- **THEN** uma entrada para cada agente de código aparece na listagem

### Requirement: Imagens de agente são provisionadas automaticamente pelo portal

O sistema DEVE construir e registrar as imagens de agente de código ao
iniciar, sem exigir que um administrador as registre manualmente. Uma
imagem de agente já registrada NÃO DEVE ser duplicada, e só DEVE ser
reconstruída quando o conteúdo do seu contexto de build — incluindo a
imagem base — mudar.

#### Scenario: Primeira inicialização do portal

- **WHEN** o portal inicia e nenhuma imagem de agente existe ainda no catálogo
- **THEN** o sistema constrói e registra as imagens de agente definidas

#### Scenario: Reinicialização sem mudança de contexto

- **GIVEN** as imagens de agente já registradas no catálogo e o contexto de
  build inalterado
- **WHEN** o portal reinicia
- **THEN** o catálogo continua com uma única entrada por agente, sem
  duplicação
- **AND** nenhuma imagem de agente é reconstruída

#### Scenario: Mudança no contexto de build

- **GIVEN** uma imagem de agente já registrada no catálogo
- **WHEN** o conteúdo do Dockerfile ou do contexto de build (incluindo a
  imagem base) muda
- **THEN** o sistema reconstrói essa imagem de agente
- **AND** o catálogo continua com uma única entrada para ela

### Requirement: Imagem base é construída antes das imagens de agente

O sistema DEVE construir e marcar a imagem base comum antes de construir as
imagens de agente que dependem dela.

#### Scenario: Ordem de construção no startup

- **WHEN** o portal inicia e a imagem base ainda não existe
- **THEN** a imagem base é construída antes das imagens de agente
- **AND** as imagens de agente conseguem partir dela

### Requirement: Falha ao provisionar uma imagem de agente não impede o portal de iniciar

Quando a construção de uma imagem de agente falhar durante a inicialização,
o sistema DEVE registrar a falha nessa entrada e NÃO DEVE impedir o portal
de iniciar nem a inicialização das demais imagens de agente.

#### Scenario: Uma imagem de agente falha ao construir

- **WHEN** a construção de uma das imagens de agente falha durante a
  inicialização do portal
- **THEN** o portal conclui sua inicialização normalmente
- **AND** as demais imagens de agente são provisionadas normalmente
- **AND** a entrada da imagem que falhou fica no estado de falha

### Requirement: Imagem de agente expõe um terminal web da ferramenta correspondente

Uma instância criada a partir de uma imagem de agente DEVE expor, pelo
encaminhamento de sessão do portal, um terminal acessível pelo navegador que
inicia a ferramenta de linha de comando daquele agente.

#### Scenario: Usuário abre uma sessão de agente

- **WHEN** o usuário abre a sessão de uma instância criada a partir de uma
  imagem de agente
- **THEN** o navegador exibe um terminal com a ferramenta do agente em
  execução

### Requirement: Instância de imagem de agente segue o mesmo ciclo de vida de qualquer instância

Uma instância criada a partir de uma imagem de agente DEVE seguir os mesmos
estados, ações de iniciar, parar e excluir, e a mesma persistência de volume
por usuário e imagem já definidos para qualquer instância do portal, sem
caminho de código divergente por ser uma imagem de agente.

#### Scenario: Parar e excluir uma instância de agente

- **WHEN** o usuário para e, em seguida, exclui uma instância criada
  a partir de uma imagem de agente
- **THEN** o container é encerrado e removido como em qualquer outra
  instância
- **AND** o volume do usuário é preservado ao parar e removido ao excluir

### Requirement: Imagens de agente recebem capa padrão com o logo da ferramenta

Cada entrada de imagem de agente DEVE receber, no startup, uma capa padrão que
usa o logo da ferramenta correspondente, sem exigir upload do administrador.
Quando houver uma capa enviada pelo administrador, ela prevalece.

#### Scenario: Primeira inicialização das imagens de agente

- **GIVEN** as imagens de agente são provisionadas sem capa do administrador
- **WHEN** o portal inicia
- **THEN** cada entrada de agente recebe uma capa padrão com o logo da sua
  ferramenta

#### Scenario: Administrador envia capa própria

- **GIVEN** uma entrada de agente com capa enviada pelo administrador
- **WHEN** o portal inicia
- **THEN** a capa do administrador continua sendo exibida

#### Scenario: Logo versionado do agente muda

- **GIVEN** uma entrada de agente que ainda usa a capa padrão
- **AND** o arquivo versionado do logo dessa ferramenta mudou
- **WHEN** o portal inicia
- **THEN** a entrada passa a usar a nova capa padrão
