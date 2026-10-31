# Spec Delta

## Purpose

Mantém, dentro do catálogo existente, um conjunto fixo de imagens que dão
acesso em navegador a agentes de código de linha de comando, pelo mesmo
mecanismo de sessão usado pelos desktops, sem depender de ação manual do
administrador para existir.

## ADDED Requirements

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
imagem de agente já registrada em execução anterior NÃO DEVE ser
duplicada nem reconstruída a cada inicialização do portal.

#### Scenario: Primeira inicialização do portal

- **WHEN** o portal inicia e nenhuma imagem de agente existe ainda no catálogo
- **THEN** o sistema constrói e registra as imagens de agente definidas

#### Scenario: Reinicialização do portal

- **GIVEN** as imagens de agente já registradas no catálogo
- **WHEN** o portal reinicia
- **THEN** o catálogo continua com uma única entrada por agente, sem duplicação

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

- **WHEN** o usuário para e, em seguida, exclui uma instância criada a
  partir de uma imagem de agente
- **THEN** o container é encerrado e removido como em qualquer outra
  instância
- **AND** o volume do usuário é preservado ao parar e removido ao excluir
