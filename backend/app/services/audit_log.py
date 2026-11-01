"""Trilha estruturada de eventos de segurança (change security-audit-log, I4).

Um evento = uma linha JSON no logger `wcui.audit`, capturada pelo coletor de
logs do operador via saída padrão (`docker logs`) — sem dependência nova, sem
tabela no banco. O handler é instalado no lifespan de `main.py`; aqui só o
emissor vive.

Campos convencionais (D2 do design): `actor_id`/`actor_email` (quem fez, via
sessão), `ip` (origem, real atrás de proxy confiável desde harden-login),
`target` (objeto da ação), `outcome` ("success" | "failure" | "denied") e
`detail` (curto, sem segredo). Catálogo de nomes: `auth.*`, `admin.*`,
`instance.*`.

Contrato de segredos (D4): o emissor só aceita campos explícitos — nenhum
ponto de emissão passa senha, token de sessão, credencial interna de
instância, chave privada ou valores de env/headers de MCP.
"""

import json
import logging

logger = logging.getLogger("wcui.audit")


def audit(event: str, **fields) -> None:
    """Emite um evento de segurança como linha JSON.

    `default=str` garante que um valor não-serializável vire string em vez de
    derrubar o caminho da requisição — a trilha é best-effort por contrato.
    """
    logger.info(json.dumps({"event": event, **fields}, ensure_ascii=False, default=str))


def install_handler() -> None:
    """Instala o handler de saída padrão do logger de auditoria.

    Idempotente: múltiplos apps (testes criam vários) não acumulam handlers
    — a checagem é pelo marcador próprio, não pela presença de handler
    qualquer (fixtures de teste anexam os seus). Formato puro
    `%(message)s` — a linha JÁ é o JSON do evento; sem timestamp duplicado
    (o coletor do operador adiciona o dele).
    """
    if not any(getattr(h, "_wcui_audit", False) for h in logger.handlers):
        handler = logging.StreamHandler()
        handler._wcui_audit = True
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
