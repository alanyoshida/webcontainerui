import time

from app.db import connect

from .conftest import add_user_to_group, grant_image_to_group, insert_group, insert_image, insert_user


def _login_admin(client, seed_user, email="admin@exemplo.test", password="senha-admin-123"):
    seed_user(email, password, is_admin=True)
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200


def test_usuario_comum_nao_registra_imagem(client, seed_user):
    seed_user("comum@exemplo.test", "senha-comum-123")
    client.post("/api/auth/login", json={"email": "comum@exemplo.test", "password": "senha-comum-123"})

    resp = client.post(
        "/api/admin/images",
        json={"display_name": "Webtop", "repository": "lscr.io/linuxserver/webtop", "tag": "latest"},
    )

    assert resp.status_code == 403


def test_registro_com_limites_padrao_quando_omitidos(client, seed_user):
    _login_admin(client, seed_user)

    resp = client.post(
        "/api/admin/images",
        json={"display_name": "Webtop", "repository": "lscr.io/linuxserver/webtop", "tag": "latest"},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["shm_size_mb"] == 1024
    assert body["mem_limit_mb"] == 2048
    assert body["cpu_limit"] == 2.0


def test_registro_com_limites_explicitos_nao_usa_o_padrao(client, seed_user):
    _login_admin(client, seed_user)

    resp = client.post(
        "/api/admin/images",
        json={
            "display_name": "Webtop pesado",
            "repository": "lscr.io/linuxserver/webtop",
            "tag": "alpine-kde",
            "shm_size_mb": 2048,
            "mem_limit_mb": 4096,
            "cpu_limit": 4.0,
        },
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["shm_size_mb"] == 2048
    assert body["mem_limit_mb"] == 4096
    assert body["cpu_limit"] == 4.0


def test_repositorio_e_tag_duplicados_sao_recusados(client, seed_user):
    _login_admin(client, seed_user)
    payload = {"display_name": "Webtop", "repository": "lscr.io/linuxserver/webtop", "tag": "latest"}

    client.post("/api/admin/images", json=payload)
    resp = client.post("/api/admin/images", json=payload)

    assert resp.status_code == 409


def test_registro_responde_imediatamente_sem_esperar_o_download(client, seed_user, fake_runtime):
    fake_runtime.set_delay("pull_image", 2.0)
    _login_admin(client, seed_user)

    inicio = time.monotonic()
    resp = client.post(
        "/api/admin/images",
        json={"display_name": "Webtop", "repository": "lscr.io/linuxserver/webtop", "tag": "latest"},
    )
    elapsed = time.monotonic() - inicio

    assert resp.status_code == 201
    assert resp.json()["pull_state"] == "pulling"
    assert elapsed < 1.0  # bem abaixo do atraso de 2s simulado no download


async def test_run_pull_leva_a_entrada_ao_estado_pronta(app_settings):
    from app.db import init_db
    from app.runtime.fake import FakeContainerRuntime
    from app.services.image_pull import run_pull
    from app.services.images import create_image

    setup_conn = connect(app_settings.db_path)
    init_db(setup_conn)
    image_id = create_image(
        setup_conn, "Webtop", "lscr.io/linuxserver/webtop", "latest", settings=app_settings
    )
    setup_conn.close()

    runtime = FakeContainerRuntime()
    await run_pull(app_settings.db_path, runtime, image_id, "lscr.io/linuxserver/webtop", "latest")

    conn = connect(app_settings.db_path)
    row = conn.execute("SELECT pull_state FROM images WHERE id = ?", (image_id,)).fetchone()
    conn.close()
    assert row["pull_state"] == "ready"


async def test_run_pull_leva_a_entrada_ao_estado_falha(app_settings):
    from app.db import init_db
    from app.runtime.errors import RuntimeOperationError
    from app.runtime.fake import FakeContainerRuntime
    from app.services.image_pull import run_pull
    from app.services.images import create_image

    setup_conn = connect(app_settings.db_path)
    init_db(setup_conn)
    image_id = create_image(
        setup_conn, "Webtop", "lscr.io/linuxserver/webtop", "latest", settings=app_settings
    )
    setup_conn.close()

    runtime = FakeContainerRuntime()
    runtime.fail_next("pull_image", RuntimeOperationError("registro indisponível"))
    await run_pull(app_settings.db_path, runtime, image_id, "lscr.io/linuxserver/webtop", "latest")

    conn = connect(app_settings.db_path)
    row = conn.execute(
        "SELECT pull_state, pull_error FROM images WHERE id = ?", (image_id,)
    ).fetchone()
    conn.close()
    assert row["pull_state"] == "failed"
    assert "registro indisponível" in row["pull_error"]


def test_retry_pull_sobre_entrada_em_falha_nao_recria(client, seed_user, app_settings):
    _login_admin(client, seed_user)
    criada = client.post(
        "/api/admin/images",
        json={"display_name": "Webtop", "repository": "lscr.io/linuxserver/webtop", "tag": "latest"},
    ).json()

    conn = connect(app_settings.db_path)
    conn.execute(
        "UPDATE images SET pull_state = 'failed', pull_error = 'erro' WHERE id = ?", (criada["id"],)
    )
    conn.close()

    resp = client.post(f"/api/admin/images/{criada['id']}/retry-pull")

    assert resp.status_code == 200
    assert resp.json()["pull_state"] == "pulling"
    assert resp.json()["id"] == criada["id"]


def test_imagem_permitida_mas_em_download_nao_aparece_no_catalogo_do_usuario(db_conn):
    from app.services.images import list_catalog_for_user

    user_id = insert_user(db_conn, "u@exemplo.test")
    image_id = insert_image(db_conn, pull_state="pulling")
    group_id = insert_group(db_conn)
    add_user_to_group(db_conn, user_id, group_id)
    grant_image_to_group(db_conn, group_id, image_id)

    assert list_catalog_for_user(db_conn, user_id) == []


def test_imagem_desabilitada_sai_do_catalogo_do_usuario(client, seed_user, app_settings):
    """A recusa de criar instância a partir de imagem desabilitada é
    verificada em 8.4, quando a criação de instância existir; aqui só se
    cobre o efeito sobre a listagem, que é o que 6.4 pede."""
    _login_admin(client, seed_user)
    conn = connect(app_settings.db_path)
    user_id = insert_user(conn, "u3@exemplo.test")
    image_id = insert_image(conn, pull_state="ready")
    group_id = insert_group(conn)
    add_user_to_group(conn, user_id, group_id)
    grant_image_to_group(conn, group_id, image_id)
    conn.close()

    resp = client.post(f"/api/admin/images/{image_id}/disable")
    assert resp.status_code == 204

    from app.services.images import list_catalog_for_user

    conn = connect(app_settings.db_path)
    catalogo = list_catalog_for_user(conn, user_id)
    conn.close()
    assert catalogo == []
