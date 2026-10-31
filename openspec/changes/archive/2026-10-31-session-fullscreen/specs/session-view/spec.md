# Spec Delta

## Purpose

Define como o portal exibe uma sessão em execução e permite expandi-la para a
tela inteira, preservando uma forma clara de sair desse modo.

## ADDED Requirements

### Requirement: Sessão em execução pode ser expandida para tela cheia

Quando uma instância está em execução, a visão da sessão DEVE oferecer uma ação
de tela cheia que expande somente a área da sessão, ocultando o cabeçalho e os
controles do portal.

#### Scenario: Entrar em tela cheia

- **WHEN** o usuário aciona a tela cheia numa sessão em execução
- **THEN** a área da sessão passa a ocupar a tela inteira
- **AND** o cabeçalho e os controles do portal deixam de ser exibidos

#### Scenario: Instância que não está em execução

- **WHEN** a instância não está em execução
- **THEN** a ação de tela cheia não é oferecida

### Requirement: Tela cheia funciona sem a Fullscreen API nativa

O sistema DEVE usar a Fullscreen API nativa quando ela estiver disponível e for
aceita. Quando não estiver disponível ou for recusada, DEVE exibir a sessão num
modo imersivo que ocupa toda a viewport, sem depender da API nativa.

#### Scenario: Fullscreen nativo aceito

- **GIVEN** um navegador com Fullscreen API disponível
- **WHEN** o usuário aciona a tela cheia
- **THEN** a sessão é exibida usando o modo nativo do navegador

#### Scenario: Fullscreen nativo indisponível ou recusado

- **GIVEN** um navegador sem Fullscreen API ou que recusa a solicitação
- **WHEN** o usuário aciona a tela cheia
- **THEN** a sessão é exibida no modo imersivo ocupando toda a viewport

### Requirement: Usuário consegue sair da tela cheia

O sistema DEVE permitir sair da tela cheia por um controle explícito visível no
modo expandido e pela tecla `ESC` no modo imersivo. A saída DEVE restaurar o
layout normal da visão da sessão.

#### Scenario: Sair pelo controle explícito

- **WHEN** o usuário aciona o controle de sair da tela cheia
- **THEN** o layout normal da visão da sessão é restaurado

#### Scenario: Sair pela tecla ESC no modo imersivo

- **GIVEN** a sessão exibida no modo imersivo
- **WHEN** o usuário pressiona `ESC`
- **THEN** o layout normal da visão da sessão é restaurado

#### Scenario: Saída automática

- **WHEN** o usuário volta para a listagem, a sessão deixa de estar em execução
  ou a visão da sessão é desmontada
- **THEN** a tela cheia é encerrada

### Requirement: Teclado permanece utilizável na tela cheia

Ao entrar em tela cheia, o foco DEVE ser direcionado à sessão para que a
digitação continue funcionando sem exigir um clique adicional.

#### Scenario: Digitar após entrar em tela cheia

- **WHEN** o usuário entra em tela cheia numa sessão em execução
- **THEN** o foco do teclado vai para a área da sessão
- **AND** a digitação é recebida pela sessão
