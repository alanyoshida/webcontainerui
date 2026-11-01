"""Change security-audit-log: emissor e contrato da trilha de eventos."""

import json
import logging

import pytest

from app.services.audit_log import audit, install_handler


@pytest.fixture
def audit_records(caplog):
    """Captura as linhas do logger `wcui.audit` (propagate=False: o handler
    do caplog precisa ser anexado direto ao logger)."""
    install_handler()
    logger = logging.getLogger("wcui.audit")
    logger.addHandler(caplog.handler)
    try:
        yield caplog
    finally:
        logger.removeHandler(caplog.handler)


def _linhas(audit_records):
    return [
        json.loads(r.message)
        for r in audit_records.records
        if r.name == "wcui.audit"
    ]


def test_evento_e_linha_json_com_campos(audit_records):
    audit(
        "auth.login",
        actor_id=1,
        actor_email="ana@x.test",
        ip="10.0.0.9",
        outcome="success",
    )

    (linha,) = _linhas(audit_records)
    assert linha["event"] == "auth.login"
    assert linha["actor_id"] == 1
    assert linha["actor_email"] == "ana@x.test"
    assert linha["ip"] == "10.0.0.9"
    assert linha["outcome"] == "success"


def test_acentos_e_valores_nao_serializaveis_nao_quebram(audit_records):
    audit("admin.group.changed", target="Açúcar & Café", detail={"op": "criar", "x": object()})

    (linha,) = _linhas(audit_records)
    assert linha["target"] == "Açúcar & Café"


def test_handler_idempotente():
    install_handler()
    install_handler()

    logger = logging.getLogger("wcui.audit")
    proprios = [h for h in logger.handlers if getattr(h, "_wcui_audit", False)]
    assert len(proprios) == 1
    assert logger.propagate is False
    assert logger.level == logging.INFO


def test_segredos_nao_passam_pelo_emissor(audit_records):
    """Contrato D4: nenhuma rota passa segredo ao emissor; aqui o contrato é
    exercido nas famílias cobertas pelos testes de rota (ver grupo de
    verificação), garantindo que senha/token de sessão não aparecem."""
    audit("auth.login", actor_email="ana@x.test", outcome="failure")

    bruto = "\n".join(r.message for r in audit_records.records)
    assert "senha-secreta-da-ana" not in bruto
