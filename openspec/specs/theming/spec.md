# theming Specification

## Purpose

Define a identidade visual do portal: os três temas de cores disponíveis, o
tema padrão, a persistência da escolha do usuário e as famílias tipográficas
e de ícones que uniformizam toda a interface.

## Requirements

### Requirement: Portal oferece três temas de cores

O portal DEVE oferecer os temas light, dark e pastel, e o usuário DEVE poder
alternar entre eles por um controle visível na barra superior.

#### Scenario: Alternância de tema

- **WHEN** o usuário escolhe um dos três temas no controle da barra superior
- **THEN** toda a interface passa a ser exibida no tema escolhido, sem recarregar a página

#### Scenario: Controle lista as três opções

- **WHEN** o usuário abre o controle de tema
- **THEN** as opções light, dark e pastel são apresentadas

### Requirement: Dark é o tema padrão na primeira visita

O portal DEVE apresentar o tema dark a um visitante que ainda não tenha feito
uma escolha de tema. A escolha explícita DEVE prevalecer sobre o padrão.

#### Scenario: Primeira visita sem escolha registrada

- **WHEN** um visitante abre o portal pela primeira vez
- **THEN** a interface é exibida no tema dark

#### Scenario: Escolha registrada prevalece

- **GIVEN** um usuário que escolheu o tema pastel
- **WHEN** ele abre o portal novamente
- **THEN** a interface é exibida no tema pastel

### Requirement: Escolha de tema persiste entre sessões

O sistema DEVE persistir o tema escolhido no dispositivo do usuário, de modo
que a escolha sobreviva ao fechamento do navegador e ao fim da sessão de
autenticação.

#### Scenario: Persistência após encerrar sessão

- **GIVEN** um usuário autenticado que escolheu o tema light
- **WHEN** ele encerra a sessão e abre a tela de entrada
- **THEN** a tela de entrada é exibida no tema light

### Requirement: Tema escuro usa superfície carvão e pastel usa primário pêssego

O tema dark DEVE usar superfícies em tom carvão, e não preto puro. O tema
pastel DEVE usar um tom pêssego como cor primária sobre fundo claro suave.

#### Scenario: Identificação do dark

- **WHEN** o tema dark está ativo
- **THEN** as superfícies da interface usam tom carvão distinto do preto puro

#### Scenario: Identificação do pastel

- **WHEN** o tema pastel está ativo
- **THEN** a cor primária da interface é o tom pêssego sobre fundo claro suave

### Requirement: Todos os elementos seguem o tema ativo

Todos os componentes da interface, incluindo tabelas, diálogos, alertas e
gráficos, DEVEM seguir a paleta do tema ativo, sem áreas em cores fixas que
contradigam o tema.

#### Scenario: Gráficos seguem o tema

- **WHEN** o usuário troca de tema com a seção de métricas de uso aberta
- **THEN** os gráficos passam a usar as cores do tema escolhido

### Requirement: Tipografia própria para interface e para conteúdo técnico

A interface DEVE usar a família tipográfica Inter para textos e a família
JetBrains Mono para conteúdo técnico monoespaçado — como a chave pública SSH,
a referência de imagem e dados de log —, carregadas pelo próprio portal sem
depender de serviço externo.

#### Scenario: Chave pública em fonte monoespaçada

- **WHEN** o usuário consulta sua identidade SSH
- **THEN** a chave pública é exibida em fonte monoespaçada

#### Scenario: Funcionamento sem acesso à internet

- **GIVEN** um portal sem acesso à internet
- **WHEN** qualquer tela é carregada
- **THEN** as fontes próprias são aplicadas normalmente

### Requirement: Ícones pertencem a um único conjunto visual

Os ícones da interface DEVEM pertencer a um único conjunto de ícones de traço,
aplicando o mesmo estilo, tamanho e espessura em todas as telas, sem misturar
conjuntos de origens diferentes.

#### Scenario: Consistência entre telas

- **WHEN** o usuário navega entre a home, a identidade SSH e o console
  administrativo
- **THEN** os ícones mantêm o mesmo estilo de traço e o mesmo tamanho
