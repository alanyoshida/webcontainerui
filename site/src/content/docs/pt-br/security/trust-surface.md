---
title: Superfície de confiança
description: O que o portal pode fazer no host, o que o usuário pode fazer dentro do próprio desktop e por que nenhuma das duas coisas é contornável por configuração.
sidebar:
  order: 1
---

Esta página descreve, sem atenuar, o que você passa a confiar ao instalar o WebContainerUI. São dois fatos estruturais, que decorrem do que o produto faz e não de um descuido de implementação: o processo do portal tem autoridade equivalente a root no host, e cada usuário tem root dentro do próprio desktop. Leia antes de implantar e antes de expor o portal além da sua própria máquina.

:::danger[O portal equivale a root no host]
O portal precisa do socket do Docker (`/var/run/docker.sock`) para criar os containers de desktop e de agente. Quem pode criar um container pode montar o sistema de arquivos do host dentro dele. Comprometer o processo do portal é comprometer o host.
:::

## O portal equivale a root no host

A composição monta o socket do Docker dentro do container do portal. Não existe modo de operação sem isso: criar, iniciar, parar e remover containers é a função central do sistema.

A consequência é direta. Uma vulnerabilidade de execução de código no portal, o vazamento de uma sessão de administrador combinado com uma falha de autorização, ou acesso de escrita à imagem do portal dão ao atacante o mesmo poder que o daemon do Docker tem — que, na instalação padrão, é root no host.

### Por que `socket-proxy` não mitiga este caso

Uma mitigação comum para "não dar o socket do Docker direto a um processo" é colocar um `socket-proxy` na frente, filtrando quais chamadas da API do Docker passam. Isso **não funciona aqui**.

O portal precisa criar containers (`POST /containers/create`) para atender ao requisito central do produto. Qualquer permissão que permita criar container também permite criar um container com um bind mount de `/` do host:

```text
  socket-proxy com CONTAINERS=1, POST=1
        |
        +--> permite container create
                 |
                 +--> permite -v /:/host
                          |
                          +--> root no host de novo
```

Ou seja: a superfície mínima necessária para o portal funcionar é exatamente a superfície que, nas mãos de quem a controla, equivale a root no host. Um `socket-proxy` que restringisse o suficiente para bloquear isso também bloquearia a criação de containers de desktop, que é a função do sistema.

## O que isso significa na prática

**O processo do portal é um componente de confiança do plano de controle.** Não um sandbox, não um processo isolado do host — um processo que, por necessidade de produto, tem autoridade equivalente a root no host via Docker.

Isso implica:

- Nenhum código de usuário roda dentro do processo do portal. Ele só orquestra containers; não interpreta nem executa nada que venha do usuário final.
- Todo comando que o portal executa dentro de um container (`docker exec`) é fixo no código — por exemplo a remoção de `/config/AGENTS.md` e o `caddy reload` do plano de dados. Nenhum deles é montado a partir de entrada de usuário.
- A imagem do portal é mínima, para reduzir a superfície de uma eventual vulnerabilidade na própria aplicação.
- O banco de dados do portal é tratado como tão sensível quanto o socket do Docker — quem lê um, efetivamente alcança o outro (ver abaixo).
- Backups, acesso ao host e rotação de credenciais do ambiente onde o portal roda devem seguir a mesma política de um host que hospeda segredos de administrador, não a de uma aplicação de usuário comum.

As demais mitigações do projeto — containers de instância sem porta publicada, credencial interna por instância, desligamento dos links de compartilhamento do Selkies — reduzem o que um usuário alcança a partir do próprio container. Elas estão descritas em [Camadas de isolamento](/security/isolation-layers/). Nenhuma delas reduz a autoridade do portal sobre o host.

## O usuário tem root dentro do próprio desktop

As imagens webtop do LinuxServer.io embutem um terminal com `sudo` sem senha. Quem tem uma sessão de desktop tem root dentro daquele container. As imagens de agente de código executam, por definição, comandos arbitrários escolhidos pelo usuário e pelo agente de IA.

A documentação do LinuxServer orienta tratar uma sessão como um login SSH para uma máquina da sua rede. Na prática:

- Dar acesso a uma imagem do catálogo a um usuário é dar a ele uma máquina Linux com root, dentro da sua rede interna de containers, com saída para onde o host tiver saída.
- Root dentro do container não é root no host: os containers de instância são criados sem modo privilegiado, sem capacidades adicionais e sem bind mount do host — só o volume nomeado da própria instância, montado em `/config`. Um escape de container (falha no kernel ou no runtime) quebraria essa fronteira, como em qualquer uso de Docker.
- Os links nativos de compartilhamento do Selkies concederiam controle total da sessão — incluindo o terminal com `sudo` — sem autenticação própria. O portal os desliga em toda instância (`SELKIES_ENABLE_SHARING=false`, `SELKIES_ENABLE_SHARED=false`).
- O que um container alcança na rede interna, e o que o impede de entrar na sessão de outro usuário, está em [Camadas de isolamento](/security/isolation-layers/). Um ponto em aberto relevante — todas as instâncias compartilham a mesma rede Docker — está registrado em [Auditorias](/security/audits/).

:::caution
Não exponha o portal à internet sem autenticação robusta à frente. O login do portal tem limitador de tentativas e cookie protegido (ver [Endurecimento do login](/security/login-hardening/)), mas não tem segundo fator nem integração com provedor de identidade. Uma senha de usuário vazada é um shell com root dentro da sua rede de containers; uma senha de administrador vazada é o controle do catálogo, dos usuários e de tudo o que o portal propaga para as instâncias.
:::

## Sensibilidade do banco de dados

Em produção o banco é PostgreSQL, rodando como serviço da composição na rede interna `wcui_net`, sem porta publicada no host — só o portal o alcança. Em desenvolvimento e testes é um arquivo SQLite no volume `/data`. Detalhes de motor e migração em [Banco de dados](/architecture/database/).

O banco guarda:

- hashes de senha (Argon2) e hashes de token de sessão (SHA-256);
- as chaves privadas SSH dos usuários, cifradas com Fernet;
- variáveis de ambiente e cabeçalhos dos servidores MCP, cifrados com a mesma chave Fernet;
- a credencial interna de cada instância (usuário e senha aleatórios que o container exige) — esta em claro, porque o portal precisa apresentá-la a cada requisição encaminhada.

Quem lê o banco não obtém senhas de usuário nem chaves privadas em claro (desde que não tenha também `WCUI_SSH_KEY_ENCRYPTION_KEY`), mas obtém as credenciais internas das instâncias e material suficiente para ataques offline contra os hashes. Quem **escreve** no banco pode se promover a administrador. Por isso:

- Trate backups (`pg_dump`) com a mesma política do socket do Docker. O procedimento está em [Backup e restauração](/operations/backup-and-restore/).
- A credencial do banco vem de `WCUI_POSTGRES_PASSWORD`, no ambiente, nunca no repositório; a URL completa é montada na composição. Ver [Variáveis de ambiente](/operations/environment-variables/).
- A senha do banco não é usada por nenhum container de instância; ela existe só no processo do portal e no serviço `postgres`.
- Guarde a chave Fernet separada dos backups do banco. Um backup acompanhado da chave equivale às chaves privadas SSH de todos os usuários e aos segredos de todos os servidores MCP.
- O portal só inicia depois do healthcheck do banco; um banco fora do ar impede o portal de subir — falha explícita, sem estado parcial.

:::note
O banco fica na mesma rede interna em que os containers de instância são criados. Um usuário, de dentro do próprio container, consegue alcançar a porta do PostgreSQL; o que o separa dos dados é a senha do banco. Use um valor longo e aleatório para `WCUI_POSTGRES_PASSWORD`, como o instalador gera.
:::

## O que fazer com essa informação

- Rode o portal em um host dedicado a ele, ou em um host cujo comprometimento você aceite tratar como comprometimento total.
- Restrinja quem tem acesso de administrador ao portal como restringiria quem tem `sudo` no host.
- Conceda imagens a grupos pensando que cada concessão entrega um shell com root na rede interna.
- Antes de abrir o portal para fora da sua máquina, siga [Implantação manual](/operations/manual-deployment/) e confira o [Checklist pós-deploy](/operations/post-deploy-checklist/).
- Leia [Auditorias](/security/audits/) para saber o que já foi testado, o que foi corrigido e o que permanece em aberto.
