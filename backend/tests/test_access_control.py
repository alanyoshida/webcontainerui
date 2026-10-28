from app.db import connect
from app.services.access_control import is_permitted
from app.services.images import list_catalog_for_user

from .conftest import add_user_to_group, grant_image_to_group, insert_group, insert_image, insert_user


def _login_admin(client, seed_user, email="admin@exemplo.test", password="senha-admin-123"):
    seed_user(email, password, is_admin=True)
    client.post("/api/auth/login", json={"email": email, "password": password})


def test_permissao_vinda_de_um_entre_varios_grupos(db_conn):
    user_id = insert_user(db_conn)
    image_id = insert_image(db_conn)
    grupo_sem_grant = insert_group(db_conn, "sem-grant")
    grupo_com_grant = insert_group(db_conn, "com-grant")
    add_user_to_group(db_conn, user_id, grupo_sem_grant)
    add_user_to_group(db_conn, user_id, grupo_com_grant)
    grant_image_to_group(db_conn, grupo_com_grant, image_id)

    assert is_permitted(db_conn, user_id, image_id) is True


def test_nenhum_grupo_com_concessao(db_conn):
    user_id = insert_user(db_conn)
    image_id = insert_image(db_conn)
    grupo = insert_group(db_conn)
    add_user_to_group(db_conn, user_id, grupo)

    assert is_permitted(db_conn, user_id, image_id) is False


def test_usuario_comum_nao_concede_permissao(client, seed_user, app_settings):
    seed_user("comum@exemplo.test", "senha-comum-123")
    client.post("/api/auth/login", json={"email": "comum@exemplo.test", "password": "senha-comum-123"})

    conn = connect(app_settings.db_path)
    group_id = insert_group(conn)
    image_id = insert_image(conn)
    conn.close()

    resp = client.post(f"/api/admin/groups/{group_id}/images", json={"image_id": image_id})
    assert resp.status_code == 403


def test_concessao_repetida_e_idempotente(client, seed_user, app_settings):
    _login_admin(client, seed_user)
    conn = connect(app_settings.db_path)
    group_id = insert_group(conn)
    image_id = insert_image(conn)
    conn.close()

    primeira = client.post(f"/api/admin/groups/{group_id}/images", json={"image_id": image_id})
    segunda = client.post(f"/api/admin/groups/{group_id}/images", json={"image_id": image_id})
    assert primeira.status_code == segunda.status_code == 204

    conn = connect(app_settings.db_path)
    total = conn.execute(
        "SELECT COUNT(*) FROM group_images WHERE group_id = ? AND image_id = ?", (group_id, image_id)
    ).fetchone()[0]
    conn.close()
    assert total == 1


def test_permissao_reflete_mudanca_de_grupo_sem_novo_login(client, seed_user, app_settings):
    _login_admin(client, seed_user)
    conn = connect(app_settings.db_path)
    user_id = insert_user(conn, "u@exemplo.test")
    image_id = insert_image(conn, pull_state="ready")
    group_id = insert_group(conn)
    conn.close()

    # ainda sem grupo: catálogo vazio
    conn = connect(app_settings.db_path)
    assert list_catalog_for_user(conn, user_id) == []
    conn.close()

    client.post(f"/api/admin/groups/{group_id}/images", json={"image_id": image_id})

    conn = connect(app_settings.db_path)
    add_user_to_group(conn, user_id, group_id)
    catalogo = list_catalog_for_user(conn, user_id)
    conn.close()
    assert len(catalogo) == 1
    assert catalogo[0]["id"] == image_id
