---
title: Alvo de escala
description: Onde está o limite de sessões simultâneas, a ordem de grandeza esperada num host dedicado e a ressalva de que os números são estimativa.
sidebar:
  order: 5
---

Com o plano de dados no Caddy, o teto de sessões simultâneas deixa de ser o processo do portal. O limite passa a ser o **host Docker**: a CPU e a RAM de cada desktop e a banda do link.

:::caution[Estimativa, não medição]
Os números desta página são estimativa de arquitetura. Valide com carga real, no seu hardware e com o seu perfil de uso, antes de prometer um teto.
:::

## Ordem de grandeza

Numa máquina dedicada com 32 vCPU, 64 GB de RAM e link de 1 Gbps, a ordem de grandeza é de **cerca de 60 a 100 sessões ativas**. O número é dominado pela CPU e pela RAM dos containers: cada webtop usa de 1 a 2 GB e parte de um núcleo em uso real.

O Caddy encaminha milhares de conexões WebSocket sem ser o gargalo.

## O que limita cada componente

| Componente | Papel na carga | Limite prático |
|---|---|---|
| Containers de instância | Executam os desktops e os agentes | CPU e RAM do host; é o fator dominante |
| Link de rede | Transporta o vídeo das sessões de desktop | Banda disponível |
| Caddy | Transporta os frames das sessões | Não é gargalo nessa ordem de grandeza |
| Portal | Decide autorização e orquestra containers | Não transporta frames |

O portal continua com **um worker** e usa `aiodocker` sem chamadas bloqueantes. A autorização do plano de dados é uma chamada curta por requisição HTTP; o canal WebSocket abre uma vez e não é autorizado por frame. O mecanismo está descrito em [Plano de dados das sessões](/architecture/session-data-plane/).

## Limites por instância

Cada entrada do catálogo define os limites de recurso dos containers criados a partir dela. Os padrões para uma entrada nova são:

| Recurso | Padrão | Variável |
|---|---|---|
| Memória | 2048 MB | `WCUI_DEFAULT_MEM_LIMIT_MB` |
| CPU | 2.0 | `WCUI_DEFAULT_CPU_LIMIT` |
| Memória compartilhada (`/dev/shm`) | 1024 MB | `WCUI_DEFAULT_SHM_SIZE_MB` |

O administrador pode editar esses valores por entrada. Somados ao limite de uma instância por imagem para cada usuário e à parada automática de instâncias ociosas (30 minutos por padrão), eles são os controles disponíveis para dimensionar o consumo do host.

## Crescer além de um host

Para crescer além de um host, a estratégia é usar mais de um host. O PostgreSQL de produção já permite vários portais sobre os mesmos dados; veja [Banco de dados](/architecture/database/) e a spec [`database-persistence`](https://github.com/alanyoshida/webcontainerui/blob/main/openspec/specs/database-persistence/spec.md).

:::note
A composição distribuída no repositório é de host único. Uma topologia com vários hosts não é entregue pronta nem foi validada com carga.
:::
