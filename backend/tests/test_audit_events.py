"""Change security-audit-log: eventos emitidos pelas rotas, por família, e
contrato de segredos fora da trilha."""

import json
import logging

import pytest

from app.db import connect, init_db
from app.runtime.errors import RuntimeOperationError
from app.services.audit_log import install_handler
from app.services.passwords import hash_password


@pytest.fixture
def audit_capture(caplog):
    """Anexa o handler do caplog direto ao logger `wcui.audit` (propagate=False)."""
    install_handler()
    logger = logging.getLogger("wcui.audit")
    logger.addHandler(caplog.handler)
    try:
        yield caplog
    finally:
        logger.removeHandler(caplog.handler)


def _eventos(audit_capture):
    return [
        json.loads(r.message)
        for r in audit_capture.records
        if r.name == "wcui.audit" and r.message.startswith("{")
    ]


def _por_evento(audit_capture, nome):
    return [e for e in _eventos(audit_capture) if e["event"] == nome]


def _monta_catalogo(app_settings, *, email):
    """Usuário comum + imagem pronta + grant de grupo, no banco do app."""
    conn = connect(app_settings.db_path)
    init_db(conn)
    user_id = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()[0]
    cur = conn.execute(
        """INSERT INTO images
               (display_name, repository, tag, shm_size_mb, mem_limit_mb, cpu_limit, pull_state)
           VALUES ('Webtop', 'exemplo/webtop', 'latest', 1024, 2048, 2.0, 'ready')"""
    )
    image_id = cur.lastrowid
    group_id = conn.execute("INSERT INTO groups (name) VALUES ('g') RETURNING id").fetchone()[0]
    conn.execute("INSERT INTO user_groups (user_id, group_id) VALUES (?, ?)", (user_id, group_id))
    conn.execute("INSERT INTO group_images (group_id, image_id) VALUES (?, ?)", (group_id, image_id))
    conn.commit()
    conn.close()
    return user_id, image_id


def _image_id_de_teste(app_settings):
    """O seed do lifespan já cria as imagens de agente (ids 1..N); o id real
    da imagem criada para o teste é consultado do banco."""
    conn = connect(app_settings.db_path)
    row = conn.execute(
        "SELECT id FROM images WHERE repository = 'exemplo/webtop'"
    ).fetchone()
    conn.close()
    return row["id"]


def _login(client, email):
    resp = client.post("/api/auth/login", json={"email": email, "password": "senha-correta-123"})
    assert resp.status_code == 200


def test_auth_family_emite_login_falha_sucesso_throttled_e_logout(client, seed_user, audit_capture):
    seed_user("gil@exemplo.test", "senha-correta-123")

    client.post("/api/auth/login", json={"email": "gil@exemplo.test", "password": "errada"})
    _login(client, "gil@exemplo.test")
    for _ in range(10):
        client.post("/api/auth/login", json={"email": "gil@exemplo.test", "password": "errada"})
    client.post("/api/auth/logout")

    falhas = _por_evento(audit_capture, "auth.login")
    assert any(e["outcome"] == "failure" and e["actor_email"] == "gil@exemplo.test" for e in falhas)
    assert any(e["outcome"] == "success" and e.get("actor_id") for e in falhas)
    throttled = _por_evento(audit_capture, "auth.login.throttled")
    assert throttled and throttled[-1]["outcome"] == "denied"
    assert _por_evento(audit_capture, "auth.logout")


def test_admin_families_emitem_eventos_com_ator(client, seed_user, audit_capture):
    seed_user("karina@exemplo.test", "senha-admin-123", is_admin=True)
    client.post("/api/auth/login", json={"email": "karina@exemplo.test", "password": "senha-admin-123"})

    resp = client.post("/api/admin/users", json={"email": "novo@x.test", "password": "senha-de-doze-chars"})
    assert resp.status_code == 201
    assert any(e["event"] == "admin.user.created" and e["target"] == "novo@x.test" for e in _eventos(audit_capture))

    uid = resp.json()["id"]
    client.post(f"/api/admin/users/{uid}/disable")
    assert any(e["event"] == "admin.user.disabled" for e in _eventos(audit_capture))

    gid = client.post("/api/admin/groups", json={"name": "grupo-x"}).json()["id"]
    assert any(e["event"] == "admin.group.changed" for e in _eventos(audit_capture))

    img = client.post("/api/admin/images", json={"display_name": "I", "repository": "r/x", "tag": "1"})
    iid = img.json()["id"]
    client.post(f"/api/admin/images/{iid}/disable")
    assert any(e["event"] == "admin.image.changed" for e in _eventos(audit_capture))

    client.post("/api/admin/agents-md", json={"name": "doc-x", "content": "# regras"})
    assert any(e["event"] == "admin.document.changed" for e in _eventos(audit_capture))

    client.post("/api/admin/mcp-servers", json={"display_name": "mcp-x", "transport": "stdio", "command": "cmd"})
    assert any(e["event"] == "admin.mcp.changed" for e in _eventos(audit_capture))

    client.post("/api/admin/agent-skills", json={"display_name": "sk", "repo_owner": "o", "repo_name": "r"})
    assert any(e["event"] == "admin.skill.changed" for e in _eventos(audit_capture))

    client.post(f"/api/admin/groups/{gid}/images", json={"image_id": iid})
    assert any(e["event"] == "admin.grant.changed" for e in _eventos(audit_capture))

    client.delete(f"/api/admin/groups/{gid}/images/{iid}?confirm=true")
    assert any(e["event"] == "admin.grant.revoked" for e in _eventos(audit_capture))

    for e in _eventos(audit_capture):
        if e["event"].startswith("admin."):
            assert e["actor_email"] == "karina@exemplo.test"


def test_instance_family_emite_created_stopped_e_deleted(client, seed_user, app_settings, audit_capture):
    seed_user("helio@exemplo.test", "senha-correta-123")
    _monta_catalogo(app_settings, email="helio@exemplo.test")
    _login(client, "helio@exemplo.test")

    resp = client.post("/api/instances", json={"image_id": _image_id_de_teste(app_settings)})
    assert resp.status_code == 201
    iid = resp.json()["id"]
    client.post(f"/api/instances/{iid}/stop")
    client.delete(f"/api/instances/{iid}?confirm=true")

    nomes = [e["event"] for e in _eventos(audit_capture)]
    for esperado in ("instance.created", "instance.stopped", "instance.deleted"):
        assert esperado in nomes


def test_instance_failed_emite_evento(client, seed_user, app_settings, fake_runtime, audit_capture, monkeypatch):
    seed_user("iona@exemplo.test", "senha-correta-123")
    _monta_catalogo(app_settings, email="iona@exemplo.test")

    async def falha(spec):
        raise RuntimeOperationError("falha simulada de criação")

    monkeypatch.setattr(fake_runtime, "create_container", falha)

    _login(client, "iona@exemplo.test")
    client.post("/api/instances", json={"image_id": _image_id_de_teste(app_settings)})

    falhas = _por_evento(audit_capture, "instance.failed")
    assert falhas and "falha simulada" in falhas[-1]["detail"]


def test_segredos_nao_aparecem_na_trilha(client, seed_user, audit_capture):
    seed_user("joana@exemplo.test", "SENHA-SECRETA-XPTO-9876")

    client.post("/api/auth/login", json={"email": "joana@exemplo.test", "password": "SENHA-SECRETA-XPTO-9876"})
    token = client.cookies.get("wcui_session", "")

    bruto = "\n".join(r.message for r in audit_capture.records)
    assert "SENHA-SECRETA-XPTO-9876" not in bruto
    assert token and token not in bruto
