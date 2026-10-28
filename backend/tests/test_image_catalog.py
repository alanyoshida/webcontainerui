import time

import pytest

from app.config import Settings
from app.db import connect
from app.services.errors import ValidationFailedError
from app.services.images import set_image_icon

from .conftest import add_user_to_group, grant_image_to_group, insert_group, insert_image, insert_user

_PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
    b"\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00"
    b"\x00IEND\xaeB`\x82"
)


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


def test_upload_de_capa_valido_grava_arquivo_e_associa_a_entrada(db_conn, tmp_path):
    settings = Settings(uploads_dir=tmp_path / "uploads")
    image_id = insert_image(db_conn)

    set_image_icon(db_conn, image_id, _PNG_1X1, settings=settings)

    row = db_conn.execute("SELECT icon_path FROM images WHERE id = ?", (image_id,)).fetchone()
    assert row["icon_path"] is not None
    assert (settings.uploads_dir / row["icon_path"]).read_bytes() == _PNG_1X1


def test_upload_de_capa_substitui_e_remove_arquivo_anterior(db_conn, tmp_path):
    settings = Settings(uploads_dir=tmp_path / "uploads")
    image_id = insert_image(db_conn)

    set_image_icon(db_conn, image_id, _PNG_1X1, settings=settings)
    primeiro_path = db_conn.execute(
        "SELECT icon_path FROM images WHERE id = ?", (image_id,)
    ).fetchone()["icon_path"]
    arquivo_antigo = settings.uploads_dir / primeiro_path
    assert arquivo_antigo.exists()

    set_image_icon(db_conn, image_id, _PNG_1X1, settings=settings)
    segundo_path = db_conn.execute(
        "SELECT icon_path FROM images WHERE id = ?", (image_id,)
    ).fetchone()["icon_path"]

    assert segundo_path != primeiro_path
    assert not arquivo_antigo.exists()
    assert (settings.uploads_dir / segundo_path).exists()


def test_upload_de_capa_com_tipo_invalido_e_recusado_e_entrada_fica_intacta(db_conn, tmp_path):
    settings = Settings(uploads_dir=tmp_path / "uploads")
    image_id = insert_image(db_conn)

    with pytest.raises(ValidationFailedError):
        set_image_icon(db_conn, image_id, b"nao e uma imagem", settings=settings)

    row = db_conn.execute("SELECT icon_path FROM images WHERE id = ?", (image_id,)).fetchone()
    assert row["icon_path"] is None


def test_upload_de_capa_maior_que_o_limite_e_recusado(db_conn, tmp_path):
    settings = Settings(uploads_dir=tmp_path / "uploads", max_icon_upload_mb=1)
    image_id = insert_image(db_conn)
    conteudo_grande = _PNG_1X1 + b"\x00" * (2 * 1024 * 1024)

    with pytest.raises(ValidationFailedError):
        set_image_icon(db_conn, image_id, conteudo_grande, settings=settings)

    row = db_conn.execute("SELECT icon_path FROM images WHERE id = ?", (image_id,)).fetchone()
    assert row["icon_path"] is None


def test_upload_de_icone_via_endpoint_retorna_icon_url(client, seed_user):
    _login_admin(client, seed_user)
    criada = client.post(
        "/api/admin/images",
        json={"display_name": "Webtop", "repository": "lscr.io/linuxserver/webtop", "tag": "latest"},
    ).json()
    assert criada["icon_url"] is None

    resp = client.post(
        f"/api/admin/images/{criada['id']}/icon",
        files={"file": ("capa.png", _PNG_1X1, "image/png")},
    )

    assert resp.status_code == 200
    assert resp.json()["icon_url"] is not None
    assert resp.json()["icon_url"].startswith("/uploads/")


def test_upload_de_icone_com_tipo_invalido_retorna_400(client, seed_user):
    _login_admin(client, seed_user)
    criada = client.post(
        "/api/admin/images",
        json={"display_name": "Webtop", "repository": "lscr.io/linuxserver/webtop", "tag": "latest"},
    ).json()

    resp = client.post(
        f"/api/admin/images/{criada['id']}/icon",
        files={"file": ("capa.txt", b"nao e imagem", "text/plain")},
    )

    assert resp.status_code == 400


def test_upload_de_icone_sobre_imagem_inexistente_retorna_404(client, seed_user):
    _login_admin(client, seed_user)

    resp = client.post(
        "/api/admin/images/999999/icon",
        files={"file": ("capa.png", _PNG_1X1, "image/png")},
    )

    assert resp.status_code == 404


def test_usuario_comum_nao_envia_icone(client, seed_user):
    seed_user("comum2@exemplo.test", "senha-comum-123")
    client.post("/api/auth/login", json={"email": "comum2@exemplo.test", "password": "senha-comum-123"})

    resp = client.post(
        "/api/admin/images/1/icon",
        files={"file": ("capa.png", _PNG_1X1, "image/png")},
    )

    assert resp.status_code == 403


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
