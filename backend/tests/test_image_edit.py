"""Change edit-catalog-image: edição parcial do catálogo e reativação."""

import json
import logging

import pytest

from app.db import connect
from app.services.audit_log import install_handler


@pytest.fixture
def audit_capture(caplog):
    install_handler()
    logger = logging.getLogger("wcui.audit")
    logger.addHandler(caplog.handler)
    try:
        yield caplog
    finally:
        logger.removeHandler(caplog.handler)


def _cria_imagem(client, seed_user, **overrides):
    seed_user("admin-edi@exemplo.test", "senha-admin-123", is_admin=True)
    client.post("/api/auth/login", json={"email": "admin-edi@exemplo.test", "password": "senha-admin-123"})
    payload = {"display_name": "Webtop", "repository": "exemplo/webtop", "tag": "latest"}
    payload.update(overrides)
    resp = client.post("/api/admin/images", json=payload)
    assert resp.status_code == 201
    return resp.json()["id"]


def _enabled(app_settings, image_id):
    conn = connect(app_settings.db_path)
    valor = conn.execute("SELECT enabled FROM images WHERE id = ?", (image_id,)).fetchone()[0]
    conn.close()
    return valor


def test_edicao_parcial_preserva_campos_nao_enviados(client, seed_user, app_settings):
    image_id = _cria_imagem(client, seed_user)
    conn = connect(app_settings.db_path)
    antes = dict(conn.execute("SELECT * FROM images WHERE id = ?", (image_id,)).fetchone())
    conn.close()

    resp = client.patch(
        f"/api/admin/images/{image_id}", json={"display_name": "Webtop Editado", "mem_limit_mb": 4096}
    )

    assert resp.status_code == 200
    corpo = resp.json()
    assert corpo["display_name"] == "Webtop Editado"
    assert corpo["mem_limit_mb"] == 4096
    # não enviados permanecem (incluído o estado de pull, que o pull em
    # fundo pode mover — mas a edição não move)
    assert corpo["repository"] == "exemplo/webtop"
    assert corpo["shm_size_mb"] == antes["shm_size_mb"]
    assert corpo["cpu_limit"] == antes["cpu_limit"]
    assert corpo["pull_state"] == antes["pull_state"]


def test_identidade_e_imutavel_mesmo_com_campos_desconhecidos(client, seed_user):
    image_id = _cria_imagem(client, seed_user)

    resp = client.patch(
        f"/api/admin/images/{image_id}",
        json={"repository": "malicioso/imagem", "provision_kind": "build", "display_name": "Ainda Webtop"},
    )

    assert resp.status_code == 200
    corpo = resp.json()
    assert corpo["repository"] == "exemplo/webtop"
    assert corpo["provision_kind"] == "pull"


@pytest.mark.parametrize(
    "corpo",
    [
        {"mem_limit_mb": 0},
        {"shm_size_mb": -1},
        {"cpu_limit": 0},
        {"port": 0},
        {"port": 70000},
        {"display_name": "   "},
        {},
    ],
)
def test_edicao_invalida_responde_400(client, seed_user, corpo):
    image_id = _cria_imagem(client, seed_user)

    resp = client.patch(f"/api/admin/images/{image_id}", json=corpo)

    assert resp.status_code == 400


def test_edicao_de_imagem_inexistente_responde_404(client, seed_user):
    _cria_imagem(client, seed_user)

    resp = client.patch("/api/admin/images/999999", json={"display_name": "X"})

    assert resp.status_code == 404


def test_edicao_emite_evento_de_auditoria(client, seed_user, audit_capture):
    image_id = _cria_imagem(client, seed_user)

    client.patch(f"/api/admin/images/{image_id}", json={"display_name": "Com trilha"})

    eventos = [
        json.loads(r.message)
        for r in audit_capture.records
        if r.name == "wcui.audit" and r.message.startswith("{")
    ]
    edicoes = [e for e in eventos if e.get("detail") == "op=editar"]
    assert edicoes and edicoes[-1]["target"] == f"imagem {image_id}"


def test_enable_reativa_entrada_desabilitada(client, seed_user, app_settings):
    image_id = _cria_imagem(client, seed_user)
    client.post(f"/api/admin/images/{image_id}/disable?confirm=true")
    assert _enabled(app_settings, image_id) == 0

    resp = client.post(f"/api/admin/images/{image_id}/enable")

    assert resp.status_code == 204
    assert _enabled(app_settings, image_id) == 1


def test_enable_de_entrada_ativa_e_idempotente(client, seed_user, app_settings):
    image_id = _cria_imagem(client, seed_user)

    resp = client.post(f"/api/admin/images/{image_id}/enable")

    assert resp.status_code == 204
    assert _enabled(app_settings, image_id) == 1


def test_enable_de_imagem_inexistente_responde_404(client, seed_user):
    _cria_imagem(client, seed_user)

    resp = client.post("/api/admin/images/999999/enable")

    assert resp.status_code == 404


def test_harden_desktop_some_da_api(client, seed_user):
    image_id = _cria_imagem(client, seed_user)

    resp = client.get("/api/admin/images")

    assert resp.status_code == 200
    entrada = next(i for i in resp.json() if i["id"] == image_id)
    assert "harden_desktop" not in entrada
