# http-hardening Specification

## Purpose

Endurece a superfície HTTP do portal com cabeçalhos de segurança nas respostas próprias e exposição mínima de documentação e identificação de stack.

## Requirements

### Requirement: Respostas do portal carregam cabeçalhos de segurança

O sistema DEVE enviar, em toda resposta gerada pelo próprio portal (interface, API e uploads), os cabeçalhos `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `X-Frame-Options: SAMEORIGIN` e uma Content-Security-Policy restritiva com origem padrão própria (`default-src 'self'`).

#### Scenario: Resposta da interface

- **WHEN** um cliente recebe qualquer resposta do portal que não seja encaminhamento de sessão
- **THEN** a resposta carrega `X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options` e `Content-Security-Policy`

#### Scenario: Encaminhamento de sessão não recebe cabeçalhos do portal

- **WHEN** uma resposta é servida pelo caminho de encaminhamento de sessão (`/i/...`)
- **THEN** o portal não adiciona seus cabeçalhos de segurança a ela
- **AND** o conteúdo encaminhado do container chega ao cliente sem alteração de política imposta pelo portal

#### Scenario: A interface permanece embutível e funcional

- **GIVEN** a CSP ativa e o frame same-origin da sessão embutido na interface
- **WHEN** o usuário abre uma sessão dentro do portal
- **THEN** o frame carrega (frame-src da própria origem) e a interface continua operando com estilos e WebSocket da própria origem

### Requirement: Documentação interativa fica desligada por padrão

O sistema NÃO DEVE servir a documentação interativa da API (`/docs`, `/redoc`, `/openapi.json`) a menos que explicitamente habilitada por configuração.

#### Scenario: Desligada por padrão

- **WHEN** um cliente pede `/docs` ou `/openapi.json` sem que a habilitação esteja configurada
- **THEN** o sistema responde que não existe (404), sem revelar o mapa da API

#### Scenario: Habilitada para desenvolvimento

- **GIVEN** a habilitação configurada
- **WHEN** um cliente pede `/docs`
- **THEN** a documentação interativa é servida
