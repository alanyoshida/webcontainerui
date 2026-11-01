# Spec Delta

## MODIFIED Requirements

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

## ADDED Requirements

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
