# Superfície de confiança do portal

## Por que `socket-proxy` não mitiga este caso

Uma mitigação comum para "não dar o socket do Docker direto a um processo" é
colocar um `socket-proxy` na frente, filtrando quais chamadas da API do Docker
passam. Isso **não funciona aqui**.

O portal precisa criar containers (`POST /containers/create`) para atender ao
requisito central do produto. Qualquer permissão que permita criar container
também permite criar um container com um bind mount de `/` do host:

```
  socket-proxy com CONTAINERS=1, POST=1
        |
        +--> permite container create
                 |
                 +--> permite -v /:/host
                          |
                          +--> root no host de novo
```

Ou seja: a superfície mínima necessária para o portal funcionar é exatamente a
superfície que, nas mãos de quem a controla, equivale a root no host. Um
`socket-proxy` que restringisse o suficiente para bloquear isso também
bloquearia a criação de containers de desktop, que é a função do sistema.

## O que isso significa na prática

**O processo do portal é um componente de confiança do plano de controle.**
Não um sandbox, não um processo isolado do host — um processo que, por
necessidade de produto, tem autoridade equivalente a root no host via Docker.

Isso implica:

- Nenhum código de usuário roda dentro do processo do portal. Ele só orquestra
  containers; não interpreta nem executa nada que venha do usuário final.
- A imagem do portal é mínima, para reduzir a superfície de uma eventual
  vulnerabilidade na própria aplicação.
- O arquivo SQLite do portal é tratado como tão sensível quanto o socket do
  Docker — quem lê um, efetivamente alcança o outro.
- Backups, acesso ao host e rotação de credenciais do ambiente onde o portal
  roda devem seguir a mesma política de um host que hospeda segredos de
  administrador, não a de uma aplicação de usuário comum.

Ver `design.md` da change `webtop-portal`, seção de riscos, para a árvore de
decisão completa e as demais mitigações do projeto (isolamento de rede dos
containers de desktop, credencial interna por instância, desligamento dos
links de compartilhamento do Selkies).
