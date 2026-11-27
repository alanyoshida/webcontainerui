# Superfície de confiança do portal

**O processo do portal equivale a root no host.** Ele precisa do socket do
Docker para criar containers, e qualquer permissão que permita criar container
também permite criar um com `-v /:/host`. Um `socket-proxy` não mitiga este
caso: a superfície mínima para o portal funcionar é exatamente a perigosa.
Trate o portal como componente de confiança do plano de controle.

**O usuário tem root dentro do próprio desktop.** As imagens webtop trazem um
terminal com `sudo` sem senha. Trate cada sessão como um login SSH numa máquina
da sua rede.

Na prática:

- nenhum código de usuário roda dentro do processo do portal;
- o banco de dados é tão sensível quanto o socket do Docker, e os backups
  também;
- não exponha o portal à internet sem autenticação robusta à frente.

## Documentação completa

O texto completo vive no site do projeto, para existir num só lugar:

| Assunto | Português | English |
|---|---|---|
| Superfície de confiança | [Ler](https://alanyoshida.github.io/webcontainerui/pt-br/security/trust-surface/) | [Read](https://alanyoshida.github.io/webcontainerui/security/trust-surface/) |
| Camadas de isolamento e plano de dados | [Ler](https://alanyoshida.github.io/webcontainerui/pt-br/security/isolation-layers/) | [Read](https://alanyoshida.github.io/webcontainerui/security/isolation-layers/) |
| Login, cabeçalhos e limitador | [Ler](https://alanyoshida.github.io/webcontainerui/pt-br/security/login-hardening/) | [Read](https://alanyoshida.github.io/webcontainerui/security/login-hardening/) |
| Trilha de eventos de segurança | [Ler](https://alanyoshida.github.io/webcontainerui/pt-br/security/audit-log/) | [Read](https://alanyoshida.github.io/webcontainerui/security/audit-log/) |
| Auditorias e status de cada achado | [Ler](https://alanyoshida.github.io/webcontainerui/pt-br/security/audits/) | [Read](https://alanyoshida.github.io/webcontainerui/security/audits/) |

Sem acesso à internet, os mesmos textos estão em Markdown no repositório:
`site/src/content/docs/pt-br/security/` (origem, em português) e
`site/src/content/docs/security/` (tradução para o inglês). Os relatórios
originais das auditorias estão em [`docs/`](../docs/).
