# app-shell Specification

## Purpose

Define a moldura visível do portal: a barra superior com o menu do usuário e
a navegação administrativa, a estrutura de páginas do console administrativo
e as regras de feedback e estados vazios que orientam quem usa o console.

## Requirements

### Requirement: Menu do usuário fica em botão expansível de avatar na barra superior

O portal DEVE agrupar o e-mail do usuário autenticado, o acesso à identidade
SSH e a ação de sair num menu que se abre ao acionar um botão de avatar com
as iniciais do usuário na extremidade direita da barra superior.

#### Scenario: Abrir o menu do usuário

- **WHEN** o usuário aciona o botão de avatar na barra superior
- **THEN** um menu se abre exibindo o e-mail no cabeçalho e as ações
  identidade SSH e sair

#### Scenario: Avatar identifica o usuário

- **WHEN** um usuário autenticado observa a barra superior
- **THEN** o botão do usuário exibe as iniciais do seu e-mail com indicador
  de expansão

### Requirement: Navegação administrativa fica à esquerda da barra superior

O portal DEVE posicionar a navegação entre áreas administrativas na
extremidade esquerda da barra superior, como um botão rotulado
"Administração" que expande o menu das seções internas. Esse botão NÃO DEVE
aparecer para usuários sem papel de administrador.

#### Scenario: Administrador vê o menu de seções

- **WHEN** um administrador aciona o botão "Administração"
- **THEN** um menu se abre listando as seções internas do console, como
  usuários, grupos, catálogo e servidores MCP

#### Scenario: Usuário comum não vê navegação administrativa

- **WHEN** um usuário sem papel de administrador observa a barra superior
- **THEN** o botão "Administração" não é exibido

### Requirement: Cada seção administrativa é uma página com título próprio

Cada seção do console administrativo DEVE ser acessível por um endereço
próprio e DEVE ser apresentada com o nome da seção como título da página.

#### Scenario: Título acompanha a seção selecionada

- **WHEN** o administrador seleciona a seção de servidores MCP no menu
- **THEN** a página exibida tem "MCP" como título

#### Scenario: Recarregar mantém a seção

- **GIVEN** o administrador navegando na seção de usuários
- **WHEN** ele recarrega a página no mesmo endereço
- **THEN** a seção de usuários volta a ser exibida

### Requirement: Ações que alteram dados confirmam o resultado visivelmente

No console administrativo, toda ação que altera dados — criação, edição,
vínculo ou desvínculo — DEVE produzir uma confirmação visível de que o
resultado foi aplicado, sem exigir que o administrador infira pelo estado
da tela.

#### Scenario: Confirmação de vínculo salvo

- **WHEN** um administrador altera o documento vinculado a uma imagem
- **THEN** a interface confirma visivelmente que o novo vínculo foi aplicado

#### Scenario: Falha é distinta de sucesso

- **WHEN** uma ação de alteração de dados falha
- **THEN** a interface informa a falha de forma distinta da confirmação de
  sucesso

### Requirement: Seções que dependem de seleção instruem antes da primeira escolha

Uma seção do console cujo conteúdo principal só aparece após o administrador
selecionar um elemento DEVE exibir uma instrução do que fazer enquanto
nenhuma seleção foi feita, em vez de uma área vazia.

#### Scenario: Seção de acessos sem grupo selecionado

- **WHEN** o administrador abre a seção de acessos sem ter escolhido um grupo
- **THEN** a página exibe a instrução de selecionar um grupo para ver e
  editar as permissões

### Requirement: Barra superior não transborda em telas estreitas

Em janelas estreitas, a barra superior DEVE manter todos os seus controles
acessíveis na largura da janela, ajustando seu conteúdo — como omitir o
e-mail do usuário e compactar os rótulos — sem gerar rolagem horizontal do
documento.

#### Scenario: Barra em janela de celular

- **WHEN** o portal é aberto numa janela de 375 pixels de largura
- **THEN** o documento não apresenta rolagem horizontal
- **AND** o menu do usuário permanece acessível

#### Scenario: E-mail sai da barra em telas estreitas

- **WHEN** a janela é estreita
- **THEN** o e-mail do usuário deixa de ser exibido diretamente na barra,
  permanecendo acessível no menu do usuário
