from app.db import connect

from .conftest import add_user_to_group, grant_image_to_group, insert_group, insert_image, insert_user


def _login_admin(client, seed_user, email="admin@exemplo.test", password="senha-admin-123"):
    seed_user(email, password, is_admin=True)
    client.post("/api/auth/login", json={"email": email, "password": password})


def test_lista_usuarios(client, seed_user, app_settings):
    _login_admin(client, seed_user)
    conn = connect(app_settings.db_path)
    insert_user(conn, "a@exemplo.test")
    conn.close()

    resp = client.get("/api/admin/users")
    assert resp.status_code == 200
    emails = {u["email"] for u in resp.json()}
    assert {"admin@exemplo.test", "a@exemplo.test"} <= emails


def test_lista_grupos_membros_e_imagens_concedidas(client, seed_user, app_settings):
    _login_admin(client, seed_user)
    conn = connect(app_settings.db_path)
    user_id = insert_user(conn, "membro@exemplo.test")
    image_id = insert_image(conn)
    group_id = insert_group(conn, "equipe")
    add_user_to_group(conn, user_id, group_id)
    grant_image_to_group(conn, group_id, image_id)
    conn.close()

    grupos = client.get("/api/admin/groups").json()
    assert any(g["id"] == group_id and g["name"] == "equipe" for g in grupos)

    membros = client.get(f"/api/admin/groups/{group_id}/members").json()
    assert membros == [{"id": user_id, "email": "membro@exemplo.test"}]

    imagens = client.get(f"/api/admin/groups/{group_id}/images").json()
    assert len(imagens) == 1
    assert imagens[0]["id"] == image_id


def test_listagens_exigem_admin(client, seed_user):
    seed_user("comum@exemplo.test", "senha-comum-123")
    client.post("/api/auth/login", json={"email": "comum@exemplo.test", "password": "senha-comum-123"})

    assert client.get("/api/admin/users").status_code == 403
    assert client.get("/api/admin/groups").status_code == 403
