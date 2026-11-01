# mcp-servers Specification

## Purpose

Mantém uma biblioteca de servidores MCP (Model Context Protocol) cadastrados
pelo administrador, permite vincular cada imagem de agente de código a N
servidores, e garante que as instâncias dessas imagens tenham os servidores
vinculados configurados, sem exigir rebuild da imagem.

## Requirements

### Requirement: Biblioteca de servidores MCP é gerenciada somente pelo administrador

O sistema DEVE oferecer criação, edição, listagem e remoção de servidores
MCP cadastrados, restritas a usuários com papel de administrador.

#### Scenario: Administrador cadastra um servidor MCP

- **WHEN** um administrador envia nome de exibição, tipo de transporte e os
  campos correspondentes (comando e argumentos para `stdio`, ou URL para
  `http`/`sse`)
- **THEN** o servidor passa a existir na biblioteca, listável e editável

#### Scenario: Usuário comum tenta gerenciar servidores MCP

- **WHEN** um usuário sem papel de administrador tenta criar, editar ou
  remover um servidor MCP
- **THEN** o sistema recusa a operação por falta de permissão
- **AND** a biblioteca permanece inalterada

### Requirement: Nome de exibição é único e os campos exigidos dependem do transporte

O sistema DEVE recusar o cadastro de um servidor MCP cujo nome de exibição
já exista na biblioteca. O sistema DEVE recusar um cadastro `stdio` sem
comando, e um cadastro `http`/`sse` sem URL.

#### Scenario: Nome duplicado

- **WHEN** um administrador tenta cadastrar um servidor MCP com nome de
  exibição já usado por outro
- **THEN** o sistema recusa a operação e informa o conflito

#### Scenario: Transporte stdio sem comando

- **WHEN** um administrador tenta cadastrar um servidor `stdio` sem
  informar o comando
- **THEN** o sistema recusa a operação

#### Scenario: Transporte remoto sem URL

- **WHEN** um administrador tenta cadastrar um servidor `http` ou `sse`
  sem informar a URL
- **THEN** o sistema recusa a operação

### Requirement: Variáveis de ambiente e headers não são reexibidos em claro depois de salvos

O sistema DEVE armazenar os valores de variáveis de ambiente e headers de
forma que não possam ser lidos de volta em claro depois de salvos — só
reutilizados internamente para configurar as instâncias.

#### Scenario: Consulta ao cadastro após salvar segredo

- **GIVEN** um servidor MCP cadastrado com uma variável de ambiente ou
  header
- **WHEN** um administrador consulta esse cadastro depois de salvo
- **THEN** o valor original não é devolvido em claro

### Requirement: Somente imagem de agente de código pode receber vínculo de servidor MCP

O sistema DEVE permitir vincular um servidor MCP a uma imagem do catálogo
apenas quando essa imagem for provisionada por build local (as imagens de
agente de código). O sistema NÃO DEVE permitir esse vínculo em imagens
provisionadas por download de registry.

#### Scenario: Vincular MCP a imagem de agente

- **GIVEN** uma imagem de agente de código e um servidor MCP existente na
  biblioteca
- **WHEN** um administrador vincula o servidor à imagem
- **THEN** a imagem passa a referenciar aquele servidor, além de
  quaisquer outros já vinculados a ela

#### Scenario: Tentativa de vincular MCP a imagem webtop

- **WHEN** um administrador tenta vincular um servidor MCP a uma imagem
  provisionada por download de registry
- **THEN** o sistema recusa a operação e informa o motivo

### Requirement: Uma imagem pode ter N servidores MCP e um servidor pode estar em N imagens

O sistema DEVE permitir que uma imagem de agente tenha qualquer número de
servidores MCP vinculados, e que o mesmo servidor esteja vinculado a
qualquer número de imagens.

#### Scenario: Múltiplos servidores na mesma imagem

- **GIVEN** uma imagem de agente com um servidor MCP já vinculado
- **WHEN** um administrador vincula um segundo servidor à mesma imagem
- **THEN** a imagem passa a referenciar os dois servidores

#### Scenario: Mesmo servidor em múltiplas imagens

- **GIVEN** um servidor MCP vinculado a uma imagem de agente
- **WHEN** um administrador vincula o mesmo servidor a uma segunda imagem
- **THEN** as duas imagens passam a referenciar aquele servidor
- **AND** desvincular de uma delas não afeta a outra

### Requirement: Vincular, editar ou desvincular um servidor MCP propaga sem rebuild de imagem

Ao vincular, editar ou desvincular um servidor MCP de uma imagem de agente,
o sistema DEVE atualizar a configuração das instâncias vivas dessa imagem
imediatamente, sem reconstruir a imagem.

#### Scenario: Vínculo propaga para instância viva

- **GIVEN** uma instância em execução de uma imagem de agente
- **WHEN** um administrador vincula um servidor MCP a essa imagem
- **THEN** a instância em execução passa a ter o servidor configurado,
  sem reiniciar

#### Scenario: Edição propaga para instâncias vivas

- **GIVEN** um servidor MCP vinculado a uma ou mais imagens, com
  instâncias vivas
- **WHEN** um administrador edita os campos desse servidor
- **THEN** cada instância viva afetada passa a usar a configuração nova

#### Scenario: Desvínculo propaga para instância viva

- **GIVEN** uma instância em execução com um servidor MCP configurado
- **WHEN** um administrador desvincula esse servidor da imagem
- **THEN** a configuração desse servidor deixa de existir na instância em
  execução
- **AND** os demais servidores configurados na mesma instância continuam
  intactos

### Requirement: Injeção de servidores MCP preserva o restante da configuração da ferramenta

Ao configurar os servidores MCP vinculados numa instância, o sistema NÃO
DEVE apagar nenhuma outra configuração da ferramenta que já exista na
instância.

#### Scenario: Instância com configuração própria da ferramenta

- **GIVEN** uma instância cuja ferramenta já tem configuração própria
  gravada (não relacionada a MCP)
- **WHEN** o sistema configura um servidor MCP vinculado à imagem
- **THEN** essa outra configuração continua intacta

### Requirement: Nova instância já nasce com os servidores MCP vinculados à imagem

Ao criar uma instância de uma imagem de agente, o sistema DEVE configurar
nela todos os servidores MCP vinculados à imagem naquele momento.

#### Scenario: Criação de instância com MCPs vinculados

- **GIVEN** uma imagem de agente com um ou mais servidores MCP vinculados
- **WHEN** uma instância dela é criada
- **THEN** a instância nasce com esses servidores já configurados

#### Scenario: Criação de instância sem MCPs vinculados

- **GIVEN** uma imagem de agente sem servidor MCP vinculado
- **WHEN** uma instância dela é criada
- **THEN** nenhum servidor MCP é configurado nela

### Requirement: Falha ao configurar um servidor MCP não impede a instância nem os demais servidores

Quando configurar um servidor MCP vinculado falhar — na criação da
instância ou numa propagação posterior — o sistema NÃO DEVE impedir a
instância de ficar pronta, nem impedir a configuração dos demais
servidores vinculados.

#### Scenario: Falha isolada na criação

- **GIVEN** uma imagem com dois ou mais servidores MCP vinculados
- **WHEN** configurar um deles falha durante a criação da instância
- **THEN** a instância fica pronta normalmente
- **AND** os demais servidores vinculados ficam configurados

### Requirement: Sistema valida o contrato do arquivo depois de configurar um servidor MCP

Depois de escrever a configuração de MCP numa instância — na criação ou
numa propagação —, o sistema DEVE verificar se o resultado ainda segue o
formato esperado pela ferramenta daquela imagem. Quando a verificação
encontrar uma quebra de contrato, o sistema DEVE reportar ao administrador
quais campos estão inválidos e em qual servidor MCP, sem encobrir a falha
como sucesso.

#### Scenario: Configuração válida não gera aviso

- **GIVEN** um servidor MCP com todos os campos exigidos pelo transporte
  escolhido
- **WHEN** o sistema configura esse servidor numa instância
- **THEN** nenhuma quebra de contrato é reportada

#### Scenario: Quebra de contrato é reportada com o campo específico

- **GIVEN** uma configuração de servidor MCP que, depois de escrita, não
  bate com o formato esperado pela ferramenta da imagem
- **WHEN** o sistema valida o arquivo resultante
- **THEN** a operação (vínculo, edição ou criação de instância) retorna ao
  administrador que houve quebra de contrato
- **AND** a mensagem identifica o servidor MCP e o campo que está inválido
- **AND** o administrador é orientado a corrigir os campos daquele
  servidor

### Requirement: Remoção de servidor MCP da biblioteca desvincula automaticamente, sem rebuild

O sistema DEVE permitir remover um servidor MCP da biblioteca mesmo
vinculado a uma ou mais imagens, removendo o vínculo de todas elas e
atualizando as instâncias vivas afetadas na mesma operação. A remoção DEVE
exigir confirmação explícita que informe que o efeito alcança imediatamente
as instâncias em execução das imagens vinculadas.

#### Scenario: Remoção exige confirmação de efeito imediato

- **WHEN** um administrador aciona a remoção de um servidor MCP vinculado a
  imagens com instâncias vivas
- **THEN** a remoção só acontece após confirmação explícita que informa o
  efeito imediato nessas instâncias

#### Scenario: Remover servidor MCP vinculado

- **GIVEN** um servidor MCP vinculado a uma ou mais imagens de agente,
  com instâncias vivas
- **WHEN** um administrador remove esse servidor da biblioteca
- **THEN** o servidor deixa de existir na biblioteca
- **AND** todas as imagens que o referenciavam deixam de referenciá-lo
- **AND** as instâncias vivas afetadas deixam de ter esse servidor
  configurado
