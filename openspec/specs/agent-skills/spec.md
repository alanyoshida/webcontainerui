# agent-skills Specification

## Purpose

Mantém uma biblioteca de skills (conhecimento procedural reutilizável, no
formato distribuído pelo skills.sh) gerenciada pelo administrador, permite
vincular cada imagem de agente de código a N skills, e garante que o build
de cada imagem instale as skills vinculadas a ela.

## Requirements

### Requirement: Biblioteca de skills é gerenciada somente pelo administrador

O sistema DEVE oferecer criação, edição, listagem e remoção de skills
cadastradas, restritas a usuários com papel de administrador.

#### Scenario: Administrador cadastra uma skill

- **WHEN** um administrador envia nome de exibição, `owner/repo` do GitHub
  e, opcionalmente, um caminho dentro do repositório
- **THEN** a skill passa a existir na biblioteca, listável e editável

#### Scenario: Usuário comum tenta gerenciar skills

- **WHEN** um usuário sem papel de administrador tenta criar, editar ou
  remover uma skill
- **THEN** o sistema recusa a operação por falta de permissão
- **AND** a biblioteca permanece inalterada

### Requirement: Nome de exibição e referência do repositório são únicos

O sistema DEVE recusar o cadastro de uma skill cujo nome de exibição já
exista na biblioteca, e DEVE recusar o cadastro de uma skill cujo
`owner/repo` combinado com o caminho dentro dele já exista.

#### Scenario: Nome duplicado

- **WHEN** um administrador tenta cadastrar uma skill com nome de exibição
  já usado por outra
- **THEN** o sistema recusa a operação e informa o conflito

#### Scenario: Repositório e caminho duplicados

- **WHEN** um administrador tenta cadastrar uma skill cujo `owner/repo` e
  caminho já estão cadastrados em outra skill
- **THEN** o sistema recusa a operação e informa o conflito

### Requirement: Somente imagem de agente de código pode receber vínculo de skill

O sistema DEVE permitir vincular uma skill a uma imagem do catálogo apenas
quando essa imagem for provisionada por build local (as imagens de agente
de código). O sistema NÃO DEVE permitir esse vínculo em imagens
provisionadas por download de registry.

#### Scenario: Vincular skill a imagem de agente

- **GIVEN** uma imagem de agente de código e uma skill existente na
  biblioteca
- **WHEN** um administrador vincula a skill à imagem
- **THEN** a imagem passa a referenciar aquela skill, além de quaisquer
  outras já vinculadas a ela

#### Scenario: Tentativa de vincular skill a imagem webtop

- **WHEN** um administrador tenta vincular uma skill a uma imagem
  provisionada por download de registry
- **THEN** o sistema recusa a operação e informa o motivo
- **AND** o vínculo não é criado

### Requirement: Uma imagem pode ter N skills e uma skill pode estar em N imagens

O sistema DEVE permitir que uma imagem de agente tenha qualquer número de
skills vinculadas, e que a mesma skill esteja vinculada a qualquer número
de imagens.

#### Scenario: Múltiplas skills na mesma imagem

- **GIVEN** uma imagem de agente com uma skill já vinculada
- **WHEN** um administrador vincula uma segunda skill à mesma imagem
- **THEN** a imagem passa a referenciar as duas skills

#### Scenario: Mesma skill em múltiplas imagens

- **GIVEN** uma skill vinculada a uma imagem de agente
- **WHEN** um administrador vincula a mesma skill a uma segunda imagem
- **THEN** as duas imagens passam a referenciar aquela skill
- **AND** desvincular de uma delas não afeta a outra

### Requirement: Vincular ou desvincular skill dispara rebuild imediato da imagem

Ao vincular ou desvincular uma skill de uma imagem de agente, o sistema
DEVE disparar imediatamente um novo build dessa imagem em segundo plano,
sem bloquear a resposta ao administrador, com o progresso consultável
como em qualquer outro build.

#### Scenario: Vínculo dispara rebuild

- **GIVEN** uma imagem de agente já pronta
- **WHEN** um administrador vincula uma skill a essa imagem
- **THEN** o sistema responde imediatamente
- **AND** a entrada passa ao estado de build em andamento
- **AND**, ao concluir, a imagem resultante tem a skill instalada

#### Scenario: Desvínculo dispara rebuild

- **GIVEN** uma imagem de agente pronta com uma skill vinculada
- **WHEN** um administrador desvincula essa skill da imagem
- **THEN** o sistema dispara um novo build da imagem
- **AND**, ao concluir, a imagem resultante não tem mais a skill instalada

### Requirement: Build de uma imagem instala todas as skills vinculadas a ela no momento do build

O sistema DEVE, ao construir uma imagem de agente por qualquer motivo
(inicialização do portal, vínculo/desvínculo de skill, ou nova tentativa
após falha), instalar dentro da imagem todas as skills vinculadas a ela
no momento do build — não um estado anterior.

#### Scenario: Rebuild por outro motivo preserva as skills vinculadas

- **GIVEN** uma imagem de agente com skills vinculadas, já refletidas num
  build anterior
- **WHEN** a imagem é reconstruída por um motivo não relacionado a skills
  (ex: mudança no Dockerfile)
- **THEN** a imagem resultante continua com todas as skills vinculadas
  instaladas

### Requirement: Falha ao instalar uma skill não impede o build da imagem

Quando a instalação de uma skill vinculada falhar durante o build, o
sistema NÃO DEVE impedir a conclusão do build nem a instalação das demais
skills vinculadas e da ferramenta do agente.

#### Scenario: Uma skill falha ao instalar

- **GIVEN** uma imagem com duas ou mais skills vinculadas
- **WHEN** a instalação de uma delas falha durante o build (ex:
  repositório inexistente ou indisponível)
- **THEN** o build da imagem conclui normalmente
- **AND** as demais skills vinculadas ficam instaladas
- **AND** a ferramenta do agente continua funcional

### Requirement: Instância já em execução não recebe skills de um rebuild posterior

Uma instância criada antes de um rebuild de sua imagem DEVE continuar
executando com as skills da imagem no momento em que foi criada, até ser
parada e reiniciada.

#### Scenario: Rebuild após instância já estar rodando

- **GIVEN** uma instância em execução, criada a partir de uma imagem de
  agente
- **WHEN** um administrador vincula uma nova skill a essa imagem,
  disparando um rebuild
- **THEN** a instância em execução continua sem a skill nova
- **AND** uma nova instância criada depois do rebuild já tem a skill

### Requirement: Remoção de skill da biblioteca desvincula automaticamente, sem rebuild

O sistema DEVE permitir remover uma skill da biblioteca mesmo vinculada a
uma ou mais imagens, removendo o vínculo de todas elas na mesma operação.
Essa remoção, por si só, NÃO DEVE disparar rebuild das imagens afetadas.

#### Scenario: Remover skill vinculada

- **GIVEN** uma skill vinculada a uma ou mais imagens de agente
- **WHEN** um administrador remove essa skill da biblioteca
- **THEN** a skill deixa de existir na biblioteca
- **AND** todas as imagens que a referenciavam deixam de referenciá-la
- **AND** nenhum build é disparado só por essa remoção
