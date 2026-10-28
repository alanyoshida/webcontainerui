from app.db import connect

from .conftest import add_user_to_group, grant_image_to_group, insert_group, insert_image


def _login_admin(client, seed_user, email="admin@exemplo.test", password="senha-admin-123"):
    seed_user(email, password, is_admin=True)
    client.post("/api/auth/login", json={"email": email, "password": password})


def _login_as(client, seed_user, email, password="senha-usuario-123"):
    seed_user(email, password)
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["id"]


def test_preview_informa_impacto_sem_alterar_nada(client, seed_user, app_settings):
    from fastapi.testclient import TestClient

    _login_admin(client, seed_user)
    with TestClient(client.app, base_url="http://testserver") as client_usuario:
        user_id = _login_as(client_usuario, seed_user, "prever@exemplo.test")
        conn = connect(app_settings.db_path)
        image_id = insert_image(conn)
        group_id = insert_group(conn)
        add_user_to_group(conn, user_id, group_id)
        grant_image_to_group(conn, group_id, image_id)
        conn.close()
        client_usuario.post("/api/instances", json={"image_id": image_id})

        preview = client.get(f"/api/admin/groups/{group_id}/images/{image_id}/revoke-preview")
        assert preview.status_code == 200
        assert preview.json()["affected_instance_count"] == 1

        # nada muda sem confirmação: o grant continua valendo
        conn = connect(app_settings.db_path)
        total_grants = conn.execute(
            "SELECT COUNT(*) FROM group_images WHERE group_id = ? AND image_id = ?",
            (group_id, image_id),
        ).fetchone()[0]
        conn.close()
        assert total_grants == 1

        instancias = client_usuario.get("/api/instances").json()
        assert instancias[0]["state"] == "running"


def test_revogacao_com_instancia_em_execucao_para_e_preserva_volume(client, seed_user, app_settings, fake_runtime):
    from fastapi.testclient import TestClient

    _login_admin(client, seed_user)
    with TestClient(client.app, base_url="http://testserver") as client_usuario:
        user_id = _login_as(client_usuario, seed_user, "revogado@exemplo.test")
        conn = connect(app_settings.db_path)
        image_id = insert_image(conn)
        group_id = insert_group(conn)
        add_user_to_group(conn, user_id, group_id)
        grant_image_to_group(conn, group_id, image_id)
        conn.close()
        instance_id = client_usuario.post("/api/instances", json={"image_id": image_id}).json()["id"]
        conn = connect(app_settings.db_path)
        volume_name = conn.execute(
            "SELECT volume_name FROM instances WHERE id = ?", (instance_id,)
        ).fetchone()["volume_name"]
        conn.close()

        resp = client.delete(f"/api/admin/groups/{group_id}/images/{image_id}?confirm=true")
        assert resp.status_code == 204

        conn = connect(app_settings.db_path)
        row = conn.execute("SELECT state FROM instances WHERE id = ?", (instance_id,)).fetchone()
        conn.close()
        assert row["state"] == "stopped"
        assert volume_name in fake_runtime._volumes

        # e o acesso é recusado depois da revogação
        resp_me = client_usuario.get("/api/catalog")
        assert resp_me.json() == []


def test_sem_confirmacao_revogacao_nao_e_aplicada(client, seed_user, app_settings):
    _login_admin(client, seed_user)
    conn = connect(app_settings.db_path)
    image_id = insert_image(conn)
    group_id = insert_group(conn)
    grant_image_to_group(conn, group_id, image_id)
    conn.close()

    resp = client.delete(f"/api/admin/groups/{group_id}/images/{image_id}")
    assert resp.status_code == 400

    conn = connect(app_settings.db_path)
    total = conn.execute(
        "SELECT COUNT(*) FROM group_images WHERE group_id = ? AND image_id = ?", (group_id, image_id)
    ).fetchone()[0]
    conn.close()
    assert total == 1


def test_permissao_remanescente_por_outro_grupo_nao_para_a_instancia(
    client, seed_user, app_settings, fake_runtime
):
    from fastapi.testclient import TestClient

    _login_admin(client, seed_user)
    with TestClient(client.app, base_url="http://testserver") as client_usuario:
        user_id = _login_as(client_usuario, seed_user, "duplogrupo@exemplo.test")
        conn = connect(app_settings.db_path)
        image_id = insert_image(conn)
        grupo_a = insert_group(conn, "grupo-a")
        grupo_b = insert_group(conn, "grupo-b")
        add_user_to_group(conn, user_id, grupo_a)
        add_user_to_group(conn, user_id, grupo_b)
        grant_image_to_group(conn, grupo_a, image_id)
        grant_image_to_group(conn, grupo_b, image_id)
        conn.close()
        instance_id = client_usuario.post("/api/instances", json={"image_id": image_id}).json()["id"]

        resp = client.delete(f"/api/admin/groups/{grupo_a}/images/{image_id}?confirm=true")
        assert resp.status_code == 204

        conn = connect(app_settings.db_path)
        row = conn.execute("SELECT state FROM instances WHERE id = ?", (instance_id,)).fetchone()
        conn.close()
        assert row["state"] == "running"  # não foi parada: grupo_b ainda concede

        assert len(client_usuario.get("/api/catalog").json()) == 1
